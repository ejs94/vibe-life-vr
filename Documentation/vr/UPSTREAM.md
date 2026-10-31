# Upstream

Vibe-Life VR is a selective fork of
[FWGS/xash3d-fwgs](https://github.com/FWGS/xash3d-fwgs). The upstream
documentation under `Documentation/` (outside `Documentation/vr/`) is read-only.
This project links to it and never rewrites it.

Useful upstream references:

- [`goldsrc-protocol-support.md`](../goldsrc-protocol-support.md)
- [`bug-compatibility.md`](../bug-compatibility.md)
- [`development/`](../development/)
- [`gameinfo.md`](../gameinfo.md)

## Sync policy

Never run a blind `git merge upstream/master` or `git rebase` on the VR branch.
The fork changes the client, server, OpenXR platform layer and the dedicated
`ref_gl_vr` renderer; an automatic merge can silently overwrite VR behavior.

Adopt upstream changes with a surgical cherry-pick and a maturity window:

1. Fetch upstream references.
2. Filter commits by age (60-90 days by default).
3. Classify the change as high value, manual review, or ignore.
4. Cherry-pick into an isolated sandbox branch.
5. Build, run `M1` and `R1`, and only then apply to `feature/openxr-vr`.

### Categories

| Category | Examples | Policy |
|---|---|---|
| High value | networking, filesystem, parser/crash fixes, general audio | cherry-pick after maturity |
| Manual review | renderer, studio models, player movement, entity state | adapt by hand; do not auto-merge |
| Ignore | mobile touch controls, flat Android launcher changes | discard unless needed for Quest |

## Audit commands

```sh
./scripts/upstream_sync_audit.sh status
./scripts/upstream_sync_audit.sh fetch
./scripts/upstream_sync_audit.sh filter 60
./scripts/upstream_sync_audit.sh inspect <commit>
./scripts/upstream_sync_audit.sh test-pick <commit>
```

`test-pick` creates a temporary branch, applies the cherry-pick, builds, and
runs the Monado suite. If the result is not green, it discards the sandbox.

## Current state (2026-10-31)

| Item | Value |
|---|---|
| Branch | `feature/openxr-vr` |
| Upstream remote | `upstream/master` |
| Merge base | `51353ff8d65e58300eeb2bd014867673f1f367c6` |
| Commits ahead of upstream | 80 |
| Commits behind upstream | 0 |
| Upstream docs | untouched |

The HLSDK integration is a local fork of `3rdparty/hlsdk-portable`. Its commits
are not pushed to the FWGS upstream. Keep submodule changes in separate commits
and update the parent pointer when the submodule advances.

## Rules

- Do not write to upstream documentation.
- Do not mix a submodule update with an unrelated change.
- Do not claim an upstream sync passed without running `M1` and `R1` on the
  resulting tree.
