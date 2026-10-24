---
description: Deploy v_hand.mdl and vr_weapons.json to a connected Quest
agent: quest-tester
---

Deploy the VR overlay assets to the connected Quest.

1. Check `quest doctor` and `quest state`; stop if no authorized device is
   present.
2. Run `./scripts/deploy_quest_assets.sh valve /sdcard/xash`.
3. Confirm the script's sha256 check for `v_hand.mdl` and that
   `vr_weapons.json` was pushed to `/sdcard/xash/valve/models/`.
4. Report the remote paths and checksum result.

Do not launch the game; this command only deploys assets.
