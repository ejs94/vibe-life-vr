# Half-Life MMOD — Reanimated Pack: asset audit

## Source

- **Pack:** Half-Life MMOD — Reanimated Pack
- **Author:** the pack author on GameBanana
- **URL:** <https://gamebanana.com/mods/574664>
- **Permission:** the author explicitly allowed this project to use the assets
  with credit (reported by the project owner).

## Status

Not bundled in `assets/valve_vr/`. The pack is a reference for VR-friendly
weapon animations and fixed 360 weapon models, not a shipped dependency.

## What to evaluate

1. Which viewmodels are **360 / armless** and can replace the 1998 flat
   viewmodels without embedded HEV arms.
2. Whether the crossbow model fixes the missing-elements issue and gives a
   usable scope/rail.
3. Which animations can replace the flat crowbar/weapon attack sequences.
4. Texture resolution and GoldSrc compatibility (palette/indexed BMP limits).
5. Whether the assets are covered by the author's permission or by the
   original Half-Life/MMOD licenses. Do not bundle anything until this is
   confirmed in writing and added to `CREDITS.md`.

## Integration rules

- Keep the original files untouched under `out/` or `tmp/` while evaluating.
- Convert only the assets that are actually used; document every change.
- Add the author and pack URL to `CREDITS.md` before shipping.
- Prefer a drop-in addon (`valve_vr` overlay) over replacing stock `valve`
  files, so users can remove it.
