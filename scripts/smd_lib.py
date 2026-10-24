#!/usr/bin/env python3
"""Minimal GoldSrc SMD reader/writer shared by the model build scripts.

SMD v1 is a plain-text interchange format:

    version 1
    nodes
      <index> "<name>" <parent-index>
    end
    skeleton
      time <frame>
      <index> <x> <y> <z> <rx> <ry> <rz>
    end
    triangles
    <material>
      <parent> <x> <y> <z> <nx> <ny> <nz> <u> <v>
      ... (three vertices per triangle)
    end

Translations are parent-relative and rotations are Euler angles in the
Rz * Ry * Rx convention used by GoldSrc.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

NODE_RE = None  # compiled lazily in parse_smd to keep import cheap


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
class Vertex:
    parent: int
    pos: tuple[float, float, float]
    normal: tuple[float, float, float]
    uv: tuple[float, float]


@dataclass
class Triangle:
    material: str
    verts: list[Vertex] = field(default_factory=list)


@dataclass
class Smd:
    nodes: list[Node] = field(default_factory=list)
    skeleton: list[BoneFrame] = field(default_factory=list)
    triangles: list[Triangle] = field(default_factory=list)


def parse_smd(path: str) -> Smd:
    import re

    node_re = re.compile(r'^\s*(\d+)\s+"([^"]*)"\s+(-?\d+)\s*$')
    smd = Smd()

    with open(path, encoding="latin1") as handle:
        lines = handle.read().replace("\r", "").splitlines()

    section = None
    current = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("version"):
            continue
        if stripped in ("nodes", "skeleton", "triangles"):
            section = stripped
            continue
        if stripped == "end":
            if section == "triangles" and current is not None:
                smd.triangles.append(current)
                current = None
            section = None
            continue

        if section == "nodes":
            match = node_re.match(line)
            if not match:
                raise ValueError(f"unparsable node line: {line!r}")
            smd.nodes.append(Node(int(match.group(1)), match.group(2), int(match.group(3))))
        elif section == "skeleton":
            parts = stripped.split()
            if parts[0] == "time":
                continue
            if len(parts) != 7:
                raise ValueError(f"unparsable skeleton line: {line!r}")
            idx = int(parts[0])
            x, y, z, rx, ry, rz = (float(v) for v in parts[1:])
            smd.skeleton.append(BoneFrame(idx, (x, y, z), (rx, ry, rz)))
        elif section == "triangles":
            parts = stripped.split()
            if len(parts) == 1:
                if current is not None:
                    smd.triangles.append(current)
                current = Triangle(parts[0])
            else:
                if current is None:
                    raise ValueError("triangle vertex before material line")
                parent = int(parts[0])
                pos = (float(parts[1]), float(parts[2]), float(parts[3]))
                normal = (float(parts[4]), float(parts[5]), float(parts[6]))
                uv = (float(parts[7]), float(parts[8]))
                current.verts.append(Vertex(parent, pos, normal, uv))

    if current is not None:
        smd.triangles.append(current)
    return smd


def write_smd(path: str, smd: Smd) -> None:
    out: list[str] = ["version 1", "nodes"]
    for node in sorted(smd.nodes, key=lambda n: n.index):
        out.append(f'{node.index} "{node.name}" {node.parent}')
    out.append("end")
    out.append("skeleton")
    out.append("time 0")
    for frame in sorted(smd.skeleton, key=lambda f: f.index):
        x, y, z = frame.pos
        rx, ry, rz = frame.rot
        out.append(f"{frame.index} {x:.6f} {y:.6f} {z:.6f} {rx:.6f} {ry:.6f} {rz:.6f}")
    out.append("end")
    out.append("triangles")
    for tri in smd.triangles:
        out.append(tri.material)
        for v in tri.verts:
            x, y, z = v.pos
            nx, ny, nz = v.normal
            u, vv = v.uv
            out.append(
                f"{v.parent} {x:.6f} {y:.6f} {z:.6f} "
                f"{nx:.6f} {ny:.6f} {nz:.6f} {u:.6f} {vv:.6f}"
            )
    out.append("end")
    with open(path, "w", encoding="latin1") as handle:
        handle.write("\n".join(out) + "\n")


def _euler_to_matrix(rx: float, ry: float, rz: float):
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    rx_m = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    ry_m = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    rz_m = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    return _mat_mul(_mat_mul(rz_m, ry_m), rx_m)


def euler_to_matrix(rx: float, ry: float, rz: float):
    """Public alias for the SMD Rz*Ry*Rx Euler convention."""
    return _euler_to_matrix(rx, ry, rz)


def matrix_to_euler(m) -> tuple[float, float, float]:
    """Decompose an Rz*Ry*Rx matrix back into (rx, ry, rz)."""
    sy = -m[2][0]
    sy = max(-1.0, min(1.0, sy))
    ry = math.asin(sy)
    cy = math.cos(ry)
    if abs(cy) > 1e-6:
        rx = math.atan2(m[2][1], m[2][2])
        rz = math.atan2(m[1][0], m[0][0])
    else:
        # Gimbal lock: the x/z split is arbitrary; keep it deterministic.
        rx = math.atan2(-m[1][2], m[1][1])
        rz = 0.0
    return (rx, ry, rz)


def rot_x(t: float):
    c, s = math.cos(t), math.sin(t)
    return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]


def rot_y(t: float):
    c, s = math.cos(t), math.sin(t)
    return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]


def rot_z(t: float):
    c, s = math.cos(t), math.sin(t)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def mat_mul(a, b):
    return _mat_mul(a, b)


def mat_vec(m, v):
    return tuple(_mat_vec(m, v))



def _mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _mat_vec(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def world_positions(smd: Smd) -> dict[int, tuple[float, float, float]]:
    """Absolute rest position of every bone, accumulated down the hierarchy."""
    frames = {f.index: f for f in smd.skeleton}
    children: dict[int, list[int]] = {}
    for node in smd.nodes:
        children.setdefault(node.parent, []).append(node.index)

    world: dict[int, tuple[float, float, float]] = {}
    identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    def visit(idx: int, parent_pos, parent_mat) -> None:
        frame = frames[idx]
        offset = _mat_vec(parent_mat, list(frame.pos))
        pos = tuple(parent_pos[k] + offset[k] for k in range(3))
        world[idx] = pos
        mat = _mat_mul(parent_mat, _euler_to_matrix(*frame.rot))
        for child in children.get(idx, []):
            visit(child, pos, mat)

    for node in smd.nodes:
        if node.parent == -1:
            visit(node.index, (0.0, 0.0, 0.0), identity)
    return world


def reach(smd: Smd, a: int, b: int) -> float:
    world = world_positions(smd)
    return math.dist(world[a], world[b])


def descendants(smd: Smd, roots: list[int]) -> set[int]:
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
