# Third-party patches

## hlsdk-vibe-life.patch

The VR gameplay changes live in the nested `3rdparty/hlsdk-portable` repository,
which is intentionally ignored by the main repository. The patch captures the
local branch state on top of `FWGS/hlsdk-portable:mobile_hacks` so a clean
checkout can reproduce the server/client DLLs used by Vibe-Life VR.

Apply it after cloning the HLSDK:

```sh
git clone --branch mobile_hacks https://github.com/FWGS/hlsdk-portable 3rdparty/hlsdk-portable
git -C 3rdparty/hlsdk-portable apply ../patches/hlsdk-vibe-life.patch
```

`scripts/configure-ninja.py` applies the patch automatically when the checkout
does not already contain it. Rebuild the HLSDK after applying the patch.

The patch includes 6DoF ballistics, muzzle/aim integration, player prediction,
hand/weapon changes and the staged Glock manual reload.
