#!/usr/bin/env python3
"""Build the fixed-camera VR hand test bed in GoldSrc format.

The map is deliberately plain: one open room, a one-metre floor grid,
distance posts at 1/2/5/10/20 m, and height bars at 1/2/3 m. Lighting is
explicit (no light_environment) so captures are repeatable.

Requires VHLT. Set VHLT_DIR to the directory containing hlcsg/ hlbsp/
hlvis/ hlrad, or keep the tools in the local JACK tree.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
BUILD_DIR = REPO_DIR / "out" / "testbed"
MAP_NAME = "testbed_scale"
UNIT_PER_M = 39.37
HALF = 900.0
CEILING = 320.0
RULER_Y = -300.0


def vhlt_dir() -> Path:
    env = os.environ.get("VHLT_DIR")
    if env:
        return Path(env).expanduser().resolve()
    # repo -> vibe-code-vr-port -> Documentos -> home, then JACK/halflife.
    return REPO_DIR.parents[2] / "JACK" / "halflife"


def face_points(mins: tuple[float, float, float], maxs: tuple[float, float, float]):
    x0, y0, z0 = mins
    x1, y1, z1 = maxs
    return {
        "-x": ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), "0 1 0 0", "0 0 -1 0"),
        "+x": ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), "0 1 0 0", "0 0 -1 0"),
        "-y": ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), "1 0 0 0", "0 0 -1 0"),
        "+y": ((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), "1 0 0 0", "0 0 -1 0"),
        "-z": ((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), "1 0 0 0", "0 -1 0 0"),
        "+z": ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), "1 0 0 0", "0 -1 0 0"),
    }


def brush(mins, maxs, texture="+0~WHITE") -> str:
    lines = ["{"]
    for _side, (p1, p2, p3, uaxis, vaxis) in face_points(mins, maxs).items():
        # VHLT computes the plane normal as (p0-p1) x (p2-p1). Swap the
        # first two points so the normal points out of the brush.
        lines.append(
            f"( {p2[0]:.3f} {p2[1]:.3f} {p2[2]:.3f} ) "
            f"( {p1[0]:.3f} {p1[1]:.3f} {p1[2]:.3f} ) "
            f"( {p3[0]:.3f} {p3[1]:.3f} {p3[2]:.3f} ) "
            f"{texture} [ {uaxis} ] [ {vaxis} ] 0 1 1"
        )
    lines.append("}")
    return "\n".join(lines)


def entity(classname: str, origin=None, extra=None) -> str:
    lines = ["{", f'"classname" "{classname}"']
    if origin is not None:
        lines.append(f'"origin" "{origin[0]:.3f} {origin[1]:.3f} {origin[2]:.3f}"')
    for key, value in (extra or {}).items():
        lines.append(f'"{key}" "{value}"')
    lines.append("}")
    return "\n".join(lines)


def make_map() -> str:
    brushes: list[str] = []

    # Shell. Floor top is z=0.
    brushes.append(brush((-HALF, -HALF, -16.0), (HALF, HALF, 0.0), "-0HFLOOR01"))
    brushes.append(brush((-HALF, -HALF, CEILING), (HALF, HALF, CEILING + 16.0), "-0CRETE4_WALL01"))
    brushes.append(brush((-HALF - 16.0, -HALF, 0.0), (-HALF, HALF, CEILING), "-0CRETE4_WALL01"))
    brushes.append(brush((HALF, -HALF, 0.0), (HALF + 16.0, HALF, CEILING), "-0CRETE4_WALL01"))
    brushes.append(brush((-HALF, -HALF - 16.0, 0.0), (HALF, -HALF, CEILING), "-0CRETE4_WALL01"))
    brushes.append(brush((-HALF, HALF, 0.0), (HALF, HALF + 16.0, CEILING), "-0CRETE4_WALL01"))

    # One-metre floor grid. Keep the lines only a few units above the floor.
    limit = int(HALF / UNIT_PER_M) - 1
    for i in range(-limit, limit + 1):
        p = i * UNIT_PER_M
        if abs(p) < 0.1:
            continue
        brushes.append(brush((p - 0.5, -HALF + 24.0, 0.0), (p + 0.5, HALF - 24.0, 0.8)))
        brushes.append(brush((-HALF + 24.0, p - 0.5, 0.0), (HALF - 24.0, p + 0.5, 0.8)))
    brushes.append(brush((-HALF + 24.0, -1.0, 0.0), (HALF - 24.0, 1.0, 1.2)))
    brushes.append(brush((-1.0, -HALF + 24.0, 0.0), (1.0, HALF - 24.0, 1.2)))

    # Distance ruler along +X, offset to the right of the spawn lane so the
    # posts do not cover the unarmed/offhand hands in first-person captures.
    brushes.append(brush((-HALF + 24.0, RULER_Y - 1.0, 0.0),
                         (HALF - 24.0, RULER_Y + 1.0, 1.2)))
    for metres, height in ((1, 1.0), (2, 2.0), (5, 5.0), (10, 7.5), (20, 7.5)):
        x = metres * UNIT_PER_M
        brushes.append(brush((x - 6.0, RULER_Y - 9.0, 0.0),
                             (x + 6.0, RULER_Y + 9.0, height * UNIT_PER_M)))
        brushes.append(brush((x - 11.0, RULER_Y - 14.0, height * UNIT_PER_M - 4.0),
                             (x + 11.0, RULER_Y + 14.0, height * UNIT_PER_M), "+0~WHITE"))

    # Height ruler on the north wall: 1 m, 2 m, 3 m.
    for metres in (1, 2, 3):
        z = metres * UNIT_PER_M
        brushes.append(brush((-220.0, HALF - 4.0, z - 3.0), (-40.0, HALF - 1.0, z + 3.0)))
    # Human-height reference pole (1.8 m) near spawn.
    brushes.append(brush((-4.0, -210.0, 0.0), (4.0, -202.0, 1.8 * UNIT_PER_M)))

    parts = [entity("worldspawn", extra={"mapversion": "220", "wad": "halflife.wad",
                                         "message": "VR test bed: 1 m grid"})]
    # Insert brushes into the worldspawn entity before closing it.
    parts[0] = parts[0].rstrip()[:-1] + "\n" + "\n".join(brushes) + "\n}"

    # Fixed, explicit lighting. No light_environment.
    for x in (-600.0, 0.0, 600.0):
        for y in (-600.0, 0.0, 600.0):
            parts.append(entity("light", (x, y, CEILING - 28.0),
                                {"_light": "255 255 255 500", "_fade": "0"}))
    # Spawn behind the first distance post so it does not fill the unarmed
    # first-person view; the +X ruler is still straight ahead.
    parts.append(entity("info_player_start", (-200.0, 0.0, 40.0), {"angles": "0 0 0"}))
    parts.append(entity("info_player_deathmatch", (-200.0, 0.0, 40.0), {"angles": "0 0 0"}))
    return "\n\n".join(parts) + "\n"


def run(cmd: list[str], log: Path) -> None:
    print("[map]", " ".join(cmd))
    with log.open("w", encoding="utf-8", errors="replace") as fh:
        proc = subprocess.run(cmd, cwd=BUILD_DIR, stdout=fh, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
        print("\n".join(tail), file=sys.stderr)
        raise SystemExit(f"command failed ({proc.returncode}): {' '.join(cmd)}")


def main() -> int:
    tools = vhlt_dir()
    missing = [str(tools / name) for name in ("hlcsg", "hlbsp", "hlvis", "hlrad")
               if not (tools / name).is_file()]
    if missing:
        print("missing VHLT tools: " + ", ".join(missing), file=sys.stderr)
        print("set VHLT_DIR to the VHLT directory", file=sys.stderr)
        return 1

    wad = REPO_DIR / "valve" / "halflife.wad"
    if not wad.is_file():
        print(f"missing WAD: {wad}", file=sys.stderr)
        return 1

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    map_path = BUILD_DIR / f"{MAP_NAME}.map"
    map_path.write_text(make_map(), encoding="utf-8")

    wad_link = BUILD_DIR / "halflife.wad"
    if wad_link.is_symlink() or wad_link.exists():
        wad_link.unlink()
    wad_link.symlink_to(wad)

    run([str(tools / "hlcsg"), f"{MAP_NAME}.map"], BUILD_DIR / "hlcsg.log")
    run([str(tools / "hlbsp"), f"{MAP_NAME}.map"], BUILD_DIR / "hlbsp.log")
    # The test bed is an open room; full VIS is not needed and a dense grid
    # can exceed MAX_PORTALS_ON_LEAF. Keep it explicit and skip by default.
    if os.environ.get("RUN_VIS") == "1":
        run([str(tools / "hlvis"), "-fast", f"{MAP_NAME}.map"], BUILD_DIR / "hlvis.log")
    run([str(tools / "hlrad"), "-extra", f"{MAP_NAME}.map"], BUILD_DIR / "hlrad.log")

    bsp = BUILD_DIR / f"{MAP_NAME}.bsp"
    if not bsp.is_file():
        print("compiler produced no BSP", file=sys.stderr)
        return 1

    # Install into the local valve_vr overlay. The engine mounts it above the
    # read-only valve tree, and out/valve/maps is a symlink into the Steam
    # installation. Never write generated maps through that symlink.
    extra_dir = REPO_DIR / "out" / "valve_vr" / "maps"
    extra_dir.mkdir(parents=True, exist_ok=True)
    dest = extra_dir / bsp.name
    shutil.copy2(bsp, dest)
    print(f"[map] copied {dest}")

    print(f"[map] source: {map_path}")
    print(f"[map] BSP: {bsp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
