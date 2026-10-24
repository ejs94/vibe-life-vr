#!/usr/bin/env python3
"""
Compile a GoldSrc studio model (MDL v10) from a prepared SMD + textures.

The environment has no GoldSrc studiomdl (the Black Mesa toolchain ships a
Source compiler, and PrimeXT's pxstudiomdl needs a full external build), so
this writer emits the MDL v10 byte layout directly. The layout follows the
GoldSrc structs in mcp-tools/halflife-tools/src/studio.h.

The output matches the structure of the shipped
assets/valve_vr/models/v_hand.mdl: a single body group, a single model, one
mesh per texture material, a single-frame rest skeleton, and a two-sequence
dummy table. Finger motion is procedural in the engine, so only the rest pose
needs to be stored.

Usage:
  python3 scripts/compile_goldsrc_mdl.py \
      --smd <prepared.smd> \
      --textures <glove.bmp> <sleeve.bmp> \
      --name v_hand.mdl \
      --output <v_hand.mdl>
"""

from __future__ import annotations

import argparse
import math
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

IDST = 0x54534449  # "IDST" little-endian
VERSION = 10
MAXSTUDIOBONES = 128
MAXSTUDIOTRIANGLES = 65536


def align4(n: int) -> int:
    return (n + 3) & ~3


# --------------------------------------------------------------------------
# SMD input
# --------------------------------------------------------------------------
NODE_RE = re.compile(r'^\s*(\d+)\s+"([^"]*)"\s+(-?\d+)\s*$')


@dataclass
class SmdNode:
    index: int
    name: str
    parent: int


@dataclass
class SmdVertex:
    parent: int
    pos: tuple[float, float, float]
    normal: tuple[float, float, float]
    uv: tuple[float, float]


@dataclass
class SmdTriangle:
    material: str
    verts: list[SmdVertex]


@dataclass
class Smd:
    nodes: list[SmdNode]
    rest: dict[int, tuple[tuple[float, float, float], tuple[float, float, float]]]
    triangles: list[SmdTriangle]


def parse_smd(path: Path) -> Smd:
    raw = path.read_text(encoding="latin1").replace("\r", "")
    nodes: list[SmdNode] = []
    rest: dict[int, tuple[tuple[float, float, float], tuple[float, float, float]]] = {}
    triangles: list[SmdTriangle] = []
    section = None
    current: SmdTriangle | None = None

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in ("nodes", "skeleton", "triangles"):
            section = stripped
            continue
        if stripped == "end":
            if section == "triangles" and current is not None:
                triangles.append(current)
                current = None
            section = None
            continue

        if section == "nodes":
            m = NODE_RE.match(line)
            if not m:
                raise ValueError(f"bad node line: {line!r}")
            nodes.append(SmdNode(int(m.group(1)), m.group(2), int(m.group(3))))
        elif section == "skeleton":
            parts = stripped.split()
            if parts[0] == "time":
                continue
            if len(parts) != 7:
                raise ValueError(f"bad skeleton line: {line!r}")
            idx = int(parts[0])
            v = [float(x) for x in parts[1:]]
            rest[idx] = (tuple(v[0:3]), tuple(v[3:6]))  # type: ignore[assignment]
        elif section == "triangles":
            parts = stripped.split()
            if len(parts) == 1:
                if current is not None:
                    triangles.append(current)
                current = SmdTriangle(parts[0], [])
            else:
                assert current is not None
                current.verts.append(
                    SmdVertex(
                        int(parts[0]),
                        (float(parts[1]), float(parts[2]), float(parts[3])),
                        (float(parts[4]), float(parts[5]), float(parts[6])),
                        (float(parts[7]), float(parts[8])),
                    )
                )
    return Smd(nodes, rest, triangles)


# --------------------------------------------------------------------------
# Textures (8-bit indexed BMP)
# --------------------------------------------------------------------------
@dataclass
class Texture:
    name: str
    width: int
    height: int
    pixels: bytes
    palette: bytes  # 256*3 RGB


def load_texture(path: Path, ref_name: str) -> Texture:
    data = path.read_bytes()
    if data[:2] != b"BM":
        raise ValueError(f"{path} is not a BMP")
    pix_off = struct.unpack_from("<I", data, 10)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    if bpp != 8:
        raise ValueError(f"{path}: expected 8-bit indexed BMP, got {bpp}bpp")
    bottom_up = h > 0
    h = abs(h)

    palette = data[pix_off - 1024:pix_off]
    pal = bytearray(768)
    for i in range(256):
        b, g, r = palette[i * 4], palette[i * 4 + 1], palette[i * 4 + 2]
        pal[i * 3 + 0] = r
        pal[i * 3 + 1] = g
        pal[i * 3 + 2] = b

    row_size = (w + 3) & ~3
    rows = [data[pix_off + y * row_size:pix_off + y * row_size + w] for y in range(h)]
    if bottom_up:
        rows.reverse()
    return Texture(ref_name, w, h, b"".join(rows), bytes(pal))


# --------------------------------------------------------------------------
# Quaternion (SMD Euler -> quat, R = Rz * Ry * Rx)
# --------------------------------------------------------------------------
def quat_from_euler(rx: float, ry: float, rz: float):
    cx, sx = math.cos(rx * 0.5), math.sin(rx * 0.5)
    cy, sy = math.cos(ry * 0.5), math.sin(ry * 0.5)
    cz, sz = math.cos(rz * 0.5), math.sin(rz * 0.5)
    x = sx * cy * cz - cx * sy * sz
    y = cx * sy * cz + sx * cy * sz
    z = cx * cy * sz - sx * sy * cz
    w = cx * cy * cz + sx * sy * sz
    return (x, y, z, w)


# --------------------------------------------------------------------------
# MDL layout
# --------------------------------------------------------------------------
@dataclass
class Bone:
    name: str
    parent: int
    pos: tuple[float, float, float]
    rot: tuple[float, float, float]


@dataclass
class Mesh:
    skinref: int
    tris: list[tuple[int, int, float, float]]  # (vertidx, normidx, s, t)


@dataclass
class Layout:
    """Bytes plus header field offsets to patch after assembly."""
    data: bytearray = field(default_factory=bytearray)

    def tell(self) -> int:
        return len(self.data)

    def write(self, payload: bytes) -> int:
        off = len(self.data)
        self.data.extend(payload)
        return off

    def pad4(self) -> None:
        while len(self.data) % 4:
            self.data.append(0)


def build(smd: Smd, textures: list[Texture], name: str) -> bytes:
    # ---- bones ----
    order = {n.index: i for i, n in enumerate(smd.nodes)}
    bones: list[Bone] = []
    for n in smd.nodes:
        pos, rot = smd.rest.get(n.index, ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
        bones.append(Bone(n.name, order[n.parent] if n.parent in order else -1, pos, rot))

    # ---- group triangles by material ----
    materials = sorted({t.material for t in smd.triangles})
    tex_by_stem = {}
    for t in textures:
        tex_by_stem[Path(t.name).stem.lower()] = t
        tex_by_stem[Path(t.name).name.lower()] = t

    meshes: list[Mesh] = []
    for mat in materials:
        skinref = -1
        stem = Path(mat).stem.lower()
        if stem not in tex_by_stem:
            raise SystemExit(f"material {mat!r} has no matching texture")
        skinref = textures.index(tex_by_stem[stem])
        tris = []
        for tri in smd.triangles:
            if tri.material != mat:
                continue
            for v in tri.verts:
                tris.append((v.parent, v.normal, v.uv[0], v.uv[1]))
        meshes.append(Mesh(skinref, tris))

    # ---- unique vertices / normals ----
    vert_key: dict = {}
    verts: list[tuple[float, float, float]] = []
    vert_bone: list[int] = []
    norm_key: dict = {}
    norms: list[tuple[float, float, float]] = []
    norm_bone: list[int] = []
    mesh_tris: list[list[tuple[int, int, float, float]]] = [[] for _ in meshes]

    mat_to_mesh = {m: i for i, m in enumerate(materials)}
    for tri in smd.triangles:
        mi = mat_to_mesh[tri.material]
        for v in tri.verts:
            bx, by, bz = bones[v.parent].pos
            rel = (v.pos[0] - bx, v.pos[1] - by, v.pos[2] - bz)
            vk = (v.parent, round(rel[0], 4), round(rel[1], 4), round(rel[2], 4))
            if vk not in vert_key:
                vert_key[vk] = len(verts)
                verts.append(rel)
                vert_bone.append(v.parent)
            vi = vert_key[vk]

            nk = (round(v.normal[0], 4), round(v.normal[1], 4), round(v.normal[2], 4))
            if nk not in norm_key:
                norm_key[nk] = len(norms)
                norms.append(v.normal)
                norm_bone.append(v.parent)
            ni = norm_key[nk]

            mesh_tris[mi].append((vi, ni, v.uv[0], v.uv[1]))

    # ---- assemble ----
    lay = Layout()
    # Header placeholder (studiohdr_t = 244 bytes for GoldSrc).
    HEADER_SIZE = 244
    lay.write(b"\x00" * HEADER_SIZE)

    # ---- bones (mstudiobone_t = 112 bytes) ----
    # GoldSrc stores the bone rest pose as value[0..2] = position and
    # value[3..5] = rotation quaternion (x, y, z).
    bone_block = bytearray()
    for b in bones:
        q = quat_from_euler(*b.rot)
        bone_block.extend(struct.pack("<32s", b.name[:31].encode("latin1")))
        bone_block.extend(struct.pack("<i", b.parent))
        bone_block.extend(struct.pack("<i", 0))              # flags
        bone_block.extend(struct.pack("<6i", *([-1] * 6)))   # bonecontroller
        bone_block.extend(struct.pack("<3f", *b.pos))        # value[0..2]
        bone_block.extend(struct.pack("<3f", q[0], q[1], q[2]))  # value[3..5]
        bone_block.extend(struct.pack("<6f", *([1.0] * 6)))  # scale
    boneindex = HEADER_SIZE  # bones immediately follow the header
    lay.data = bytearray(b"\x00" * HEADER_SIZE)
    lay.data.extend(bone_block)
    lay.pad4()

    # ---- bonecontrollers: none ----
    numbonecontrollers = 0
    bonecontrollerindex = HEADER_SIZE

    # ---- hitboxes: none ----
    numhitboxes = 0
    hitboxindex = HEADER_SIZE

    # ---- pivots: none ----
    # ---- attachments: none ----
    numattachments = 0
    attachmentindex = HEADER_SIZE

    # ---- textures + texture data ----
    tex_block = bytearray()
    tex_data = bytearray()
    # Reserve texture index; data offsets are patched once data offsets known.
    textureindex = 0
    texturedataindex = 0

    # We need to know where texture data lands, so lay out in two passes:
    # first append texture header block, then the pixel/palette payloads.
    # Build the whole texture section here with correct relative offsets.
    tex_entries = []
    data_cursor = 0
    for t in textures:
        tex_entries.append((t, data_cursor))
        data_cursor += t.width * t.height + 768

    for (t, data_off) in tex_entries:
        tex_block.extend(struct.pack("<64s", (t.name[:63]).encode("latin1")))
        tex_block.extend(struct.pack("<i", 0))           # flags
        tex_block.extend(struct.pack("<i", t.width))
        tex_block.extend(struct.pack("<i", t.height))
        tex_block.extend(struct.pack("<i", data_off))
    textureindex = lay.tell()
    lay.write(tex_block)
    lay.pad4()
    texturedataindex = lay.tell()
    for (t, _) in tex_entries:
        lay.data.extend(t.pixels)
        lay.data.extend(t.palette)
    lay.pad4()

    # ---- skinref / skinfamily ----
    numskinref = len(textures)
    numskinfamilies = 1
    skinindex = lay.tell()
    lay.write(struct.pack(f"<{numskinref}h", *range(numskinref)))
    lay.pad4()

    # ---- bodyparts ----
    numbodyparts = 1
    bodypartindex = lay.tell()
    # mstudiobodyparts_t: name[64], nummodels, base, modelindex
    # modelindex is an absolute file offset to the mstudiomodel_t array.
    # The model struct is emitted immediately after this bodypart entry.
    bodypart_modelindex = bodypartindex + 76
    lay.write(struct.pack("<64siii", b"hand", 1, 0, bodypart_modelindex))
    lay.pad4()

    # ---- model ----
    # mstudiomodel_t: name[64], type, boundingradius, nummesh, meshindex,
    #   numverts, vertinfoindex, vertindex, numnorms, norminfoindex, normindex,
    #   numgroups, groupindex  -> 64 + 4*12 = 112 bytes
    modelindex = lay.tell()
    # meshindex points to mstudiomesh_t array; placed after the model struct.
    meshindex = modelindex + 112
    nummesh = len(meshes)
    # vertinfo/vert arrays follow meshes.
    pending = []
    lay.write(b"\x00" * 112)  # patched later
    lay.pad4()

    # ---- meshes ----
    for i, mesh in enumerate(meshes):
        numtris = len(mesh_tris[i]) // 3
        triindex = 0  # patched
        pending.append((i, numtris))
        lay.write(struct.pack("<5i", numtris, 0, mesh.skinref, 0, 0))
    lay.pad4()

    # ---- triangles (mstudiotrivert_t = short vertindex, short normindex, short s, short t) ----
    tri_offsets = []
    for i, tris in enumerate(mesh_tris):
        off = lay.tell()
        tri_offsets.append(off)
        for (vi, ni, s, t) in tris:
            lay.write(struct.pack("<4h",
                                  vi,
                                  ni,
                                  int(round(s * 256.0)) & 0xFFFF,
                                  int(round(t * 256.0)) & 0xFFFF))
    lay.pad4()

    # ---- vertex bone info (byte per vertex) + vertex positions ----
    vertinfoindex = lay.tell()
    lay.write(bytes(vert_bone))
    lay.pad4()
    vertindex = lay.tell()
    for v in verts:
        lay.write(struct.pack("<3f", *v))
    lay.pad4()

    # ---- normals: norminfoindex + normindex ----
    norminfoindex = lay.tell()
    lay.write(bytes(norm_bone))
    lay.pad4()
    normindex = lay.tell()
    for n in norms:
        lay.write(struct.pack("<3f", *n))
    lay.pad4()

    # ---- sequences ----
    # Two sequences matching the shipped model: idle and use, both 1 frame.
    numseq = 2
    seqindex = lay.tell()
    seq_block = bytearray()
    seqgroupindex = 0

    # sequence group data (a tiny anim block) is placed after the seq descs.
    # mstudioseqdesc_t is 176 bytes in GoldSrc.
    SEQDESC_SIZE = 176
    # Reserve space for two sequence descriptors; patch after we know anim offset.
    seq_start = lay.tell()
    lay.write(b"\x00" * (SEQDESC_SIZE * numseq))
    lay.pad4()

    # ---- sequence groups ----
    numseqgroups = 1
    seqgroupindex = lay.tell()
    seqgroup = struct.pack("<32s64sii", b"default", b"", 0, 0)
    lay.write(seqgroup)
    lay.pad4()

    # ---- bbox ----
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    bbmin = (min(xs), min(ys), min(zs))
    bbmax = (max(xs), max(ys), max(zs))
    # Include bone offsets so the box covers the animated model.
    for b in bones:
        for pt in (b.pos,):
            bbmin = (min(bbmin[0], pt[0]), min(bbmin[1], pt[1]), min(bbmin[2], pt[2]))
            bbmax = (max(bbmax[0], pt[0]), max(bbmax[1], pt[1]), max(bbmax[2], pt[2]))

    # ---- patch header ----
    # Build the 244-byte studiohdr_t field by field to avoid format mismatch.
    hdr = bytearray(HEADER_SIZE)
    struct.pack_into("<ii", hdr, 0, IDST, VERSION)
    struct.pack_into("<64s", hdr, 8, name[:63].encode("latin1"))
    struct.pack_into("<i", hdr, 72, 0)                                  # length (patched below)
    struct.pack_into("<3f", hdr, 76, 0.0, 0.0, 0.0)                     # eyeposition
    struct.pack_into("<3f", hdr, 88, *bbmin)                            # min
    struct.pack_into("<3f", hdr, 100, *bbmax)                           # max
    struct.pack_into("<3f", hdr, 112, *bbmin)                           # bbmin
    struct.pack_into("<3f", hdr, 124, *bbmax)                           # bbmax
    struct.pack_into("<i", hdr, 136, 0)                                 # flags
    struct.pack_into("<i", hdr, 140, len(bones))                        # numbones
    struct.pack_into("<i", hdr, 144, boneindex)                         # boneindex
    struct.pack_into("<i", hdr, 148, numbonecontrollers)
    struct.pack_into("<i", hdr, 152, bonecontrollerindex)
    struct.pack_into("<i", hdr, 156, numhitboxes)
    struct.pack_into("<i", hdr, 160, hitboxindex)
    struct.pack_into("<i", hdr, 164, numseq)
    struct.pack_into("<i", hdr, 168, seqindex)
    struct.pack_into("<i", hdr, 172, numseqgroups)
    struct.pack_into("<i", hdr, 176, seqgroupindex)
    struct.pack_into("<i", hdr, 180, len(textures))                     # numtextures
    struct.pack_into("<i", hdr, 184, textureindex)
    struct.pack_into("<i", hdr, 188, texturedataindex)
    struct.pack_into("<i", hdr, 192, numskinref)
    struct.pack_into("<i", hdr, 196, numskinfamilies)
    struct.pack_into("<i", hdr, 200, skinindex)
    struct.pack_into("<i", hdr, 204, numbodyparts)
    struct.pack_into("<i", hdr, 208, bodypartindex)
    struct.pack_into("<i", hdr, 212, numattachments)
    struct.pack_into("<i", hdr, 216, attachmentindex)
    struct.pack_into("<i", hdr, 220, 0)                                 # soundtable
    struct.pack_into("<i", hdr, 224, 0)                                 # soundindex
    struct.pack_into("<i", hdr, 228, 0)                                 # soundgroups
    struct.pack_into("<i", hdr, 232, 0)                                 # soundgroupindex
    struct.pack_into("<i", hdr, 236, 0)                                 # numtransitions
    struct.pack_into("<i", hdr, 240, 0)                                 # transitionindex
    lay.data[0:HEADER_SIZE] = hdr

    # ---- patch model struct ----
    model_block = struct.pack(
        "<64s i f i i i i i i i i i i",
        b"hand",
        0,
        0.5,
        nummesh,
        meshindex,
        len(verts),
        vertinfoindex,
        vertindex,
        len(norms),
        norminfoindex,
        normindex,
        0,
        0,
    )
    lay.data[modelindex:modelindex + len(model_block)] = model_block

    # ---- patch mesh triindex ----
    for i, (mi, numtris) in enumerate(pending):
        off = meshindex + i * 20
        struct.pack_into("<i", lay.data, off + 4, tri_offsets[i])

    # ---- patch sequence descriptors ----
    for s in range(numseq):
        off = seq_start + s * SEQDESC_SIZE
        label = b"idle" if s == 0 else b"use"
        struct.pack_into("<32s", lay.data, off, label)
        struct.pack_into("<f", lay.data, off + 32, 16.0)   # fps
        struct.pack_into("<i", lay.data, off + 36, 0)      # flags
        struct.pack_into("<i", lay.data, off + 40, 0)      # activity
        struct.pack_into("<i", lay.data, off + 44, 0)      # actweight
        struct.pack_into("<i", lay.data, off + 48, 0)      # numevents
        struct.pack_into("<i", lay.data, off + 52, 0)      # eventindex
        struct.pack_into("<i", lay.data, off + 56, 1)      # numframes
        struct.pack_into("<i", lay.data, off + 60, 0)      # numpivots
        struct.pack_into("<i", lay.data, off + 64, 0)      # pivotindex
        struct.pack_into("<i", lay.data, off + 68, 0)      # motiontype
        struct.pack_into("<i", lay.data, off + 72, 0)      # motionbone
        struct.pack_into("<3f", lay.data, off + 76, 0.0, 0.0, 0.0)  # linearmovement
        struct.pack_into("<i", lay.data, off + 88, 0)      # automoveposindex
        struct.pack_into("<i", lay.data, off + 92, 0)      # automoveangleindex
        struct.pack_into("<3f", lay.data, off + 96, *bbmin)   # bbmin
        struct.pack_into("<3f", lay.data, off + 108, *bbmax)  # bbmax
        struct.pack_into("<i", lay.data, off + 120, 1)     # numblends
        struct.pack_into("<i", lay.data, off + 124, 0)     # animindex
        struct.pack_into("<2i", lay.data, off + 128, 0, 0)  # blendtype
        struct.pack_into("<2f", lay.data, off + 136, 0.0, 0.0)  # blendstart
        struct.pack_into("<2f", lay.data, off + 144, 0.0, 0.0)  # blendend
        struct.pack_into("<i", lay.data, off + 152, -1)    # blendparent
        struct.pack_into("<i", lay.data, off + 156, 0)     # seqgroup
        struct.pack_into("<i", lay.data, off + 160, 0)     # entrynode
        struct.pack_into("<i", lay.data, off + 164, 0)     # exitnode
        struct.pack_into("<i", lay.data, off + 168, 0)     # nodeflags
        struct.pack_into("<i", lay.data, off + 172, 0)     # nextseq

    # ---- patch length ----
    struct.pack_into("<i", lay.data, 72, len(lay.data))
    return bytes(lay.data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--smd", required=True, type=Path)
    ap.add_argument("--textures", nargs="+", required=True, type=Path)
    ap.add_argument("--name", default="v_hand.mdl")
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    smd = parse_smd(args.smd)
    textures = [load_texture(p, p.name) for p in args.textures]
    print(f"smd: {len(smd.nodes)} bones, {len(smd.triangles)} triangles")
    print(f"textures: {[(t.name, t.width, t.height) for t in textures]}")

    blob = build(smd, textures, args.name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(blob)
    print(f"wrote {args.output} ({len(blob)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
