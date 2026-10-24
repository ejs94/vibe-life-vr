#!/usr/bin/env python3
"""
Prepare the Rimrook "HEV Arms That Don't Suck" hand for the Xash3D VR port.

The source asset (hev_reference.smd) is a public-domain, properly rigged hand
pair authored in a much larger unit scale than the engine's v_hand.mdl, and its
finger bones use Rimrook's own naming (Bone01..Bone35) rather than the scheme
R_StudioApplyFingerCurling in ref/gl_vr/gl_studio.c matches by name.

This script performs three deterministic, auditable text edits on the SMD:

  1. Rescale every vertex and bone position so the hand matches the engine's
     expected size (derived from the shipped v_hand.mdl bounding box).
  2. Recenter the model so the wrist sits at the origin of the engine's
     controller pose (matching how v_hand.mdl is authored).
  3. Rename the five finger chains of the chosen hand to the engine's expected
     Bone27..Bone45 finger scheme so procedural finger curling works without
     any engine change.

Only one hand of the pair is emitted, selected anatomically. The engine mirrors
it for the other controller (see R_HandEntityNeedsMirror).

Usage:
  python3 scripts/prepare_rimrook_hand.py \
      --input <hev_reference.smd> \
      --output /tmp/opencode/rimrook/v_hand_rimrook.smd
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass, field


# --------------------------------------------------------------------------
# Target geometry
# --------------------------------------------------------------------------
# The engine draws the hand at its native vertex scale (only the controller
# pose is scaled by vr_worldscale), so the model must be authored at the same
# size as the shipped hand.
#
# The bounding-box span is a poor size anchor here: the Rimrook thumb points
# back toward the wrist, so the box is dominated by the thumb-to-pinky spread
# rather than the hand's actual reach. The wrist-to-middle-fingertip distance
# is the meaningful metric and is measured from the recursive rest skeleton
# of each SMD:
#
#   shipped v_hand.mdl (new_lhand.smd)  wrist->middle tip = 3.78
#
# The Rimrook hand is scaled so its wrist-to-middle-fingertip distance matches.
TARGET_WRIST_MIDDLE_TIP = 3.78

# --------------------------------------------------------------------------
# Curl behaviour
# --------------------------------------------------------------------------
# R_StudioApplyFingerCurling in ref/gl_vr/gl_studio.c post-multiplies every
# finger bone's rotation by a quaternion about its own LOCAL Z axis. The
# Rimrook rig is authored so that this already folds the fingers into the palm
# (verified: with the local-Z curl the fingertip sweeps from perpendicular to
# the palm normal round to pointing along it, i.e. a natural fist). No
# rest-pose realignment is therefore applied; describe_curl() records the
# behaviour so a future asset swap can be checked the same way.

# --------------------------------------------------------------------------
# Finger mapping
# --------------------------------------------------------------------------
# Verified from the source SMD's skeleton: the root is "Right Hand", which
# splits into two mirrored wrists (Bone01 / Bone19). Each wrist leads to a
# palm (Bone17 / Bone21) that carries five finger chains.
#
# Anatomical identification for the Bone01 hand, ordered by lateral X:
#   Bone02->Bone03        (2 joints, shortest reach, offset)  -> thumb
#   Bone05->Bone06->Bone07                                    -> index
#   Bone08->Bone09->Bone10                                    -> middle (longest)
#   Bone11->Bone12->Bone13                                    -> ring
#   Bone14->Bone15->Bone16                                    -> pinky (outermost)
#
# The engine matches exact names in ref/gl_vr/gl_studio.c (~1096-1139):
#   thumb   Bone27, Bone28, Bone29
#   index   Bone31, Bone32, Bone33
#   middle  Bone35, Bone36, Bone37
#   ring    Bone39, Bone40, Bone41
#   pinky   Bone43, Bone44, Bone45
#
# The Rimrook thumb has only two joints, so only the first two engine names are
# used for it; the third stays unused, which is harmless.
HAND_A_FINGER_MAP = {
    "thumb":  ["Bone02", "Bone03"],
    "index":  ["Bone05", "Bone06", "Bone07"],
    "middle": ["Bone08", "Bone09", "Bone10"],
    "ring":   ["Bone11", "Bone12", "Bone13"],
    "pinky":  ["Bone14", "Bone15", "Bone16"],
}

# Mirrored (Bone19) hand, so either hand can be emitted identically.
HAND_B_FINGER_MAP = {
    "thumb":  ["Bone22", "Bone23"],
    "index":  ["Bone24", "Bone25", "Bone26"],
    "middle": ["Bone27", "Bone28", "Bone29"],
    "ring":   ["Bone30", "Bone31", "Bone32"],
    "pinky":  ["Bone33", "Bone34", "Bone35"],
}

ENGINE_FINGER_NAMES = {
    "thumb":  ["Bone27", "Bone28", "Bone29"],
    "index":  ["Bone31", "Bone32", "Bone33"],
    "middle": ["Bone35", "Bone36", "Bone37"],
    "ring":   ["Bone39", "Bone40", "Bone41"],
    "pinky":  ["Bone43", "Bone44", "Bone45"],
}

# Every finger bone, for the curl simulation in describe_curl().
FINGER_BONE_NAMES = {bone for chain in ENGINE_FINGER_NAMES.values() for bone in chain}

# Root/palm bones renamed to match the hierarchy the engine's shipped hand uses.
# The engine's finger curling only matches finger bone names, but aligning the
# wrist/palm keeps the model consistent with v_hand.mdl.
HAND_ROOT_RENAME = {
    "hand_a": {"Right Hand": "Bone24", "Bone01": "Bone25", "Bone17": "Bone26"},
    "hand_b": {"Bone19": "Bone25", "Bone21": "Bone26"},
}


# --------------------------------------------------------------------------
# SMD parsing
# --------------------------------------------------------------------------
@dataclass
class Node:
    index: int
    name: str
    parent: int


@dataclass
class BoneFrame:
    index: int
    pos: tuple[float, float, float]
    rot: tuple[float, float, float]


@dataclass
class TriangleVertex:
    parent: int
    pos: tuple[float, float, float]
    normal: tuple[float, float, float]
    uv: tuple[float, float]


@dataclass
class Triangle:
    material: str
    verts: list[TriangleVertex] = field(default_factory=list)


@dataclass
class Smd:
    version: int
    nodes: list[Node]
    skeleton: list[BoneFrame]           # rest frame only
    triangles: list[Triangle]
    tail_lines: list[str] = field(default_factory=list)


NODE_RE = re.compile(r'^\s*(\d+)\s+"([^"]*)"\s+(-?\d+)\s*$')


def parse_smd(path: str) -> Smd:
    with open(path, encoding="latin1") as handle:
        raw = handle.read().replace("\r", "")
    lines = raw.splitlines()

    version = 1
    nodes: list[Node] = []
    skeleton: list[BoneFrame] = []
    triangles: list[Triangle] = []

    section = None
    current_tri: Triangle | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("version"):
            version = int(stripped.split()[1])
            continue
        if stripped in ("nodes", "skeleton", "triangles"):
            section = stripped
            continue
        if stripped == "end":
            if section == "triangles" and current_tri is not None:
                triangles.append(current_tri)
                current_tri = None
            section = None
            continue

        if section == "nodes":
            match = NODE_RE.match(line)
            if not match:
                raise ValueError(f"unparsable node line: {line!r}")
            nodes.append(Node(int(match.group(1)), match.group(2), int(match.group(3))))
        elif section == "skeleton":
            parts = stripped.split()
            if parts[0] == "time":
                continue  # only the single rest frame is used
            if len(parts) != 7:
                raise ValueError(f"unparsable skeleton line: {line!r}")
            idx = int(parts[0])
            x, y, z, rx, ry, rz = (float(v) for v in parts[1:])
            skeleton.append(BoneFrame(idx, (x, y, z), (rx, ry, rz)))
        elif section == "triangles":
            parts = stripped.split()
            if len(parts) == 1:
                if current_tri is not None:
                    triangles.append(current_tri)
                current_tri = Triangle(parts[0])
            else:
                parent = int(parts[0])
                pos = tuple(float(v) for v in parts[1:4])   # type: ignore[assignment]
                normal = tuple(float(v) for v in parts[4:7])  # type: ignore[assignment]
                uv = (float(parts[7]), float(parts[8]))
                assert current_tri is not None
                current_tri.verts.append(TriangleVertex(parent, pos, normal, uv))  # type: ignore[arg-type]

    return Smd(version, nodes, skeleton, triangles)


# --------------------------------------------------------------------------
# Geometry analysis
# --------------------------------------------------------------------------
def vertices_of(smd: Smd, parent_indices: set[int] | None = None):
    for tri in smd.triangles:
        for vert in tri.verts:
            if parent_indices is None or vert.parent in parent_indices:
                yield vert


def compute_span(smd: Smd) -> tuple[float, tuple[float, float, float]]:
    xs = [v.pos[0] for v in vertices_of(smd)]
    ys = [v.pos[1] for v in vertices_of(smd)]
    zs = [v.pos[2] for v in vertices_of(smd)]
    spans = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    return max(spans), spans


def reachable(smd: Smd, roots: list[int]) -> set[int]:
    """All bone indices descending from the given roots."""
    children: dict[int, list[int]] = {}
    for node in smd.nodes:
        children.setdefault(node.parent, []).append(node.index)

    seen: set[int] = set()
    stack = list(roots)
    while stack:
        idx = stack.pop()
        if idx in seen:
            continue
        seen.add(idx)
        stack.extend(children.get(idx, []))
    return seen


def wrist_local_position(smd: Smd, wrist_bone: str) -> tuple[float, float, float]:
    by_name = {n.name: n for n in smd.nodes}
    frames = {f.index: f for f in smd.skeleton}
    node = by_name[wrist_bone]
    parent = frames[node.parent]
    # Local rest translation of the wrist bone is the offset from its parent.
    return frames[node.index].pos


def skeleton_world_positions(smd: Smd) -> dict[int, tuple[float, float, float]]:
    """Absolute rest position of every bone, accumulated down the hierarchy.

    SMD skeleton rows store parent-relative translations and Euler rotations;
    the rotation of each parent must be applied to the child offset.
    """
    frames = {f.index: f for f in smd.skeleton}
    children: dict[int, list[int]] = {}
    for node in smd.nodes:
        children.setdefault(node.parent, []).append(node.index)

    def rot(rx: float, ry: float, rz: float):
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)
        rx_m = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
        ry_m = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
        rz_m = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
        mm = lambda a, b: [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        return mm(mm(rz_m, ry_m), rx_m)

    def mul(m, v):
        return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]

    mm = lambda a, b: [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    world: dict[int, tuple[float, float, float]] = {}

    def visit(idx: int, parent_pos, parent_mat) -> None:
        frame = frames[idx]
        offset = mul(parent_mat, list(frame.pos))
        pos = tuple(parent_pos[k] + offset[k] for k in range(3))
        world[idx] = pos
        mat = mm(parent_mat, rot(*frame.rot))
        for child in children.get(idx, []):
            visit(child, pos, mat)

    for node in smd.nodes:
        if node.parent == -1:
            visit(node.index, (0.0, 0.0, 0.0), identity)

    return world


def wrist_to_middle_tip(smd: Smd, wrist_bone: str, middle_tip_bone: str) -> float:
    world = skeleton_world_positions(smd)
    by_name = {n.name: n for n in smd.nodes}
    a = world[by_name[wrist_bone].index]
    b = world[by_name[middle_tip_bone].index]
    return math.dist(a, b)


def _euler_to_matrix(rx: float, ry: float, rz: float):
    """Rotation matrix for the SMD's Rz * Ry * Rx Euler convention."""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    rx_m = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    ry_m = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    rz_m = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    return _mat_mul(_mat_mul(rz_m, ry_m), rx_m)


def _mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _mat_mul_vec(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def describe_curl(smd: Smd) -> dict:
    """Quantify how much the engine's local-Z curl bends each finger.

    The engine post-multiplies every finger bone by a rotation about its local
    Z. What matters physically is that the finger *bends* - the first phalanx
    must swing by a large angle, not merely twist about its own axis. This
    returns the angle, in degrees, between the first phalanx at rest and at a
    full curl, per finger, so a future asset swap can be checked against the
    same numbers.
    """
    frames = {f.index: f for f in smd.skeleton}
    name_of = {n.index: n.name for n in smd.nodes}
    children: dict[int, list[int]] = {}
    for node in smd.nodes:
        children.setdefault(node.parent, []).append(node.index)

    def evaluate(curl: float) -> dict[int, list[float]]:
        positions: dict[int, list[float]] = {}

        def walk(idx: int, parent_pos, parent_mat) -> None:
            frame = frames[idx]
            local = _euler_to_matrix(*frame.rot)
            if curl and name_of[idx] in FINGER_BONE_NAMES:
                c, s = math.cos(curl), math.sin(curl)
                local = _mat_mul(local, [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
            positions[idx] = [
                parent_pos[k] + _mat_mul_vec(parent_mat, list(frame.pos))[k]
                for k in range(3)
            ]
            for child in children.get(idx, []):
                walk(child, positions[idx], _mat_mul(parent_mat, local))

        eye = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        for root in children.get(-1, []):
            walk(root, [0.0, 0.0, 0.0], eye)
        return positions

    by_name = {n.name: n.index for n in smd.nodes}
    rest = evaluate(0.0)
    curled = evaluate(1.5)

    def phalanx(positions, head, neck) -> list[float]:
        a = positions[by_name[head]]
        b = positions[by_name[neck]]
        d = [b[k] - a[k] for k in range(3)]
        n = math.sqrt(sum(c * c for c in d)) or 1.0
        return [c / n for c in d]

    result: dict = {}
    for finger, chain in ENGINE_FINGER_NAMES.items():
        d0 = phalanx(rest, chain[0], chain[1])
        d1 = phalanx(curled, chain[0], chain[1])
        cosine = max(-1.0, min(1.0, sum(d0[k] * d1[k] for k in range(3))))
        result[finger] = round(math.degrees(math.acos(cosine)), 1)
    return result


# --------------------------------------------------------------------------
# Transformation
# --------------------------------------------------------------------------
def transform(smd: Smd, hand: str, dry_run: bool) -> tuple[Smd, dict]:
    hand_key = "hand_a" if hand == "a" else "hand_b"
    finger_map = HAND_A_FINGER_MAP if hand_key == "hand_a" else HAND_B_FINGER_MAP
    wrist_bone = "Bone01" if hand_key == "hand_a" else "Bone19"
    palm_bone = "Bone17" if hand_key == "hand_a" else "Bone21"

    # Keep only the chosen hand plus bone 0 (the shared root).
    keep = reachable(smd, [0, next(n.index for n in smd.nodes if n.name == wrist_bone)])
    # Bone 0 ("Right Hand") is the authored root of both hands; keep it as the
    # single root so the model has exactly one parentless bone.
    root_index = next(n.index for n in smd.nodes if n.parent == -1)
    keep.add(root_index)

    report: dict = {"hand": hand_key, "wrist_bone": wrist_bone, "palm_bone": palm_bone}

    # ---- 1. scale ----
    # Anchor on the wrist-to-middle-fingertip reach so the emitted hand matches
    # the shipped v_hand.mdl on-screen size after recompilation.
    middle_tip_bone = finger_map["middle"][-1]
    source_reach = wrist_to_middle_tip(smd, wrist_bone, middle_tip_bone)
    scale = TARGET_WRIST_MIDDLE_TIP / source_reach
    report["source_wrist_to_middle_tip"] = round(source_reach, 4)
    report["target_wrist_to_middle_tip"] = TARGET_WRIST_MIDDLE_TIP
    report["scale"] = round(scale, 6)

    # ---- 2. recenter at wrist ----
    # The engine places the hand entity at the controller pose; the model's
    # wrist must sit at the local origin, exactly like the shipped v_hand.mdl.
    frames = {f.index: f for f in smd.skeleton}
    wrist_idx = next(n.index for n in smd.nodes if n.name == wrist_bone)
    wrist_local = frames[wrist_idx].pos
    report["wrist_local_before"] = tuple(round(v, 2) for v in wrist_local)

    # In the source the root "Right Hand" is at the origin and the wrist is a
    # parentless sibling. Reparenting the wrist under the root with zero offset
    # makes the wrist the local origin of the emitted single-hand model.
    recenter = wrist_local

    def new_pos(p):
        return (
            (p[0] - recenter[0]) * scale,
            (p[1] - recenter[1]) * scale,
            (p[2] - recenter[2]) * scale,
        )

    def scale_only(p):
        return (p[0] * scale, p[1] * scale, p[2] * scale)

    # ---- 3. rename fingers ----
    rename: dict[str, str] = {}
    for finger, chain in finger_map.items():
        targets = ENGINE_FINGER_NAMES[finger]
        for source_name, target_name in zip(chain, targets):
            rename[source_name] = target_name
    rename.update(HAND_ROOT_RENAME[hand_key])
    report["renames"] = dict(sorted(rename.items()))

    if dry_run:
        return smd, report

    # ---- build the new SMD ----
    new_nodes: list[Node] = []
    # Root first, parentless.
    new_nodes.append(Node(0, "Bone24", -1))

    # Remap indices for the kept bones.
    kept_nodes = [n for n in smd.nodes if n.index in keep and n.index != root_index]
    index_map: dict[int, int] = {root_index: 0}
    for new_idx, node in enumerate(kept_nodes, start=1):
        index_map[node.index] = new_idx

    wrist_new_index = index_map[wrist_idx]
    for node in kept_nodes:
        name = rename.get(node.name, node.name)
        if node.index == wrist_idx:
            parent = 0  # wrist attaches to the root at the origin
        elif node.parent == root_index:
            parent = wrist_new_index  # the "Right Hand" sibling folds into the wrist
        else:
            parent = index_map[node.parent]
        new_nodes.append(Node(index_map[node.index], name, parent))

    new_skeleton: list[BoneFrame] = []
    for node in smd.nodes:
        if node.index not in index_map:
            continue
        frame = frames[node.index]
        if node.index == wrist_idx:
            # The wrist becomes the local origin of the emitted model.
            pos = (0.0, 0.0, 0.0)
        elif node.index == root_index:
            pos = (0.0, 0.0, 0.0)
        elif node.parent == root_index:
            # The authored "Right Hand" root is folded away; this bone's former
            # parent-relative offset from that origin becomes its offset from
            # the wrist, which now sits at that same origin.
            pos = scale_only(frame.pos)
        else:
            # Skeleton rows are parent-relative translations: scale only.
            pos = scale_only(frame.pos)
        new_skeleton.append(BoneFrame(index_map[node.index], pos, frame.rot))
    # Root frame.
    new_skeleton.insert(0, BoneFrame(0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))

    new_triangles: list[Triangle] = []
    dropped = 0
    for tri in smd.triangles:
        kept_verts = [v for v in tri.verts if v.parent in index_map]
        if not kept_verts:
            dropped += 1
            continue
        new_tri = Triangle(tri.material)
        for vert in kept_verts:
            new_tri.verts.append(
                TriangleVertex(
                    index_map[vert.parent],
                    new_pos(vert.pos),
                    vert.normal,
                    vert.uv,
                )
            )
        new_triangles.append(new_tri)
    report["triangles_kept"] = len(new_triangles)
    report["triangles_dropped"] = dropped

    result = Smd(smd.version, new_nodes, new_skeleton, new_triangles)

    # Report how the engine's local-Z curl moves each fingertip. The authored
    # rig already folds the fingers into the palm, so no rest-pose realignment
    # is applied; this is recorded so a future asset swap can be checked.
    report["curl_check"] = describe_curl(result)

    return result, report


# --------------------------------------------------------------------------
# Serialization
# --------------------------------------------------------------------------
def serialize_smd(smd: Smd) -> str:
    out: list[str] = [f"version {smd.version}", "nodes"]
    for node in smd.nodes:
        out.append(f'{node.index} "{node.name}" {node.parent}')
    out.append("end")
    out.append("skeleton")
    out.append("time 0")
    for frame in smd.skeleton:
        out.append(
            f"{frame.index} {frame.pos[0]:.6f} {frame.pos[1]:.6f} {frame.pos[2]:.6f}"
            f" {frame.rot[0]:.6f} {frame.rot[1]:.6f} {frame.rot[2]:.6f}"
        )
    out.append("end")
    out.append("triangles")
    for tri in smd.triangles:
        out.append(tri.material)
        for vert in tri.verts:
            out.append(
                f"{vert.parent} {vert.pos[0]:.6f} {vert.pos[1]:.6f} {vert.pos[2]:.6f}"
                f" {vert.normal[0]:.6f} {vert.normal[1]:.6f} {vert.normal[2]:.6f}"
                f" {vert.uv[0]:.6f} {vert.uv[1]:.6f}"
            )
    out.append("end")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="source hev_reference.smd")
    parser.add_argument("--output", help="write the prepared SMD here")
    parser.add_argument("--hand", choices=["a", "b"], default="a")
    parser.add_argument("--dry-run", action="store_true", help="report only")
    args = parser.parse_args()

    smd = parse_smd(args.input)
    print(f"parsed {args.input}: {len(smd.nodes)} nodes, {len(smd.skeleton)} rest frames, "
          f"{len(smd.triangles)} triangles")

    result, report = transform(smd, args.hand, args.dry_run)

    print("\n--- preparation report ---")
    for key, value in report.items():
        print(f"  {key}: {value}")

    if args.output and not args.dry_run:
        with open(args.output, "w", encoding="latin1", newline="\n") as handle:
            handle.write(serialize_smd(result))
        print(f"\nwrote {args.output}")

        span, spans = compute_span(result)
        print(f"  output dominant span = {span:.3f} (spans {tuple(round(s, 2) for s in spans)})")
        print(f"  output nodes = {len(result.nodes)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
