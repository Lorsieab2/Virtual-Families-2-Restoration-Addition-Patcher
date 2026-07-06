# Virtual Families 2 Restoration/Addition Patcher

Offline patcher source for Virtual Families 2 restoration/addition builds.

Created with Codex AI in collaboration with Lorsieab2.

## What It Does

- Verifies a user-selected official Virtual Families 2 PC install before changing anything.
- Applies records from `manifest.json` only when their toggleable settings are enabled.
- Creates a separate clearly labeled modded game folder by default.
- Creates backups and patch logs before writing changed files.
- Provides a restore option for patcher-created backups.
- Avoids runtime injection, process memory editing, packers, obfuscation, and admin requirements.

## Dry Run, ELI5

Dry Run validates that the patcher's working. It checks that the selected VF2 folder looks official, checks that the EXE and payload files match the manifest, and then stops.

It does not actually change or write files.

## Release Artifact

The full B105 patcher ZIP is intentionally not committed to source because it contains the patch payload. It should be attached to a GitHub Release:

`Virtual-Families-2-Restoration-Addition-Patcher-B105.zip`

## Source Layout

- `src/offline_vf2_patcher.py` - CLI patcher, validation, backups, apply/restore logic.
- `src/offline_vf2_patcher_gui.py` - Tkinter GUI wrapper.
- `src/export_offline_patch_bundle.py` - bundle/manifest/payload exporter.
- `src/assets/patcher_icon.png` and `src/assets/patcher_icon.ico` - GUI title picture and shortcut/window icon assets.
- `tests/` - unit tests for the patcher, GUI helpers, and exporter.
- `docs/offline-patcher.md` - technical patcher documentation.
- `Transparency Log.txt` - transparency notes for users.
- `How to Use.txt` - player-facing instructions.

## Run Tests

```powershell
python -m unittest discover -s tests
```

## Use The Patcher

For normal users, download the release ZIP, unzip it, run `Launch_GUI.bat`, select the vanilla VF2 install folder, optionally run `Dry Run (Validate Only)`, then click `Enable/Disable Patches`. Prebuilt `Launch GUI.lnk` shortcuts are not shipped because Windows shortcuts can point at stale paths after ZIP extraction.

Have fun! -Lorsieab2 :)
