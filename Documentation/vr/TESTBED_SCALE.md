# Test bed scale

`testbed_scale` is the controlled capture map for hand and weapon evidence. It
is generated from source, not hand-edited in a level editor.

## Build

```sh
python3 scripts/build_testbed_map.py
```

The script uses VHLT `hlcsg`, `hlbsp` and `hlrad`. It defaults to the local
`JACK/halflife` directory relative to the workspace; override it with `VHLT_DIR`.
The BSP is copied to `out/valve_vr/maps/testbed_scale.bsp`. The engine mounts the
`valve_vr` overlay above the read-only `valve` tree. Do not write through
`out/valve/maps`, which is a symlink into the Steam installation.

`hlvis` is intentionally skipped. The one-metre floor grid creates more portals
than `MAX_PORTALS_ON_LEAF` allows; the open room does not need culling for
captures. The engine logs `map maps/testbed_scale.bsp has no visibility`, which
is expected.

## Contents

- 45 m open room, 8 m ceiling.
- One-metre floor grid and a central +X ruler.
- Distance posts at 1, 2, 5, 10 and 20 m.
- Height bars at 1, 2 and 3 m on the north wall.
- Human-height reference pole.
- Nine explicit white `light` entities; no `light_environment`.
- Spawn behind the first distance post, facing +X.

## Captures

`scripts/gate_testbed_hands.cfg` uses the fixed comparison camera for baked and
free-hand views, and the normal eye camera for the unarmed blocky hand. Run it
with:

```sh
CFG_NAME=gate_testbed_hands.cfg OUTPUT_SUBDIR=gate_testbed ./scripts/test_gate0_hands.sh
```

The runner copies `gate*.ppm` files into `out/evidence/gate_testbed/<run>/`.
Evidence is engine eye dumps, not compositor/headset proof.

## Known limits

- The map is not VIS-compiled; do not use it for performance measurements.
- The blocky hand is a presence/grip placeholder, not a natural hand; unarmed
  captures show its actual silhouette.
- The fixed offhand camera falls back to the hand entity when the simulated
  secondary controller has no grip pose.
