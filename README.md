# Virtual Families 2 Restoration/Addition Patcher

Offline patcher and restoration/addition project for the official Windows version of *Virtual Families 2*.

Created with Codex AI in collaboration with Lorsieab2. This is a passion project dedicated to improving the *Virtual Families 2* experience. No copyright infringement is intended; please support the original game creators. :)

## Which copy of the game this supports

**This patcher targets the Windows build of *Virtual Families 2* downloaded from Last Day of Work's own website.** That is the only copy it is developed and tested against.

It has **not** been tested against the Steam release, and whether that build matches has not been established. The patcher validates the installation you point it at and refuses to proceed if it does not recognise it, so an unsupported copy should fail safely rather than be corrupted — but nothing is promised beyond the LDW build.

There is also no practical reason to get the game anywhere else: **all of LDW's PC games are free on their own website.** Download it from there and point the patcher at that installation.



## Download

Download the newest patcher ZIP from the [official releases page](https://github.com/Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher/releases). Release ZIPs and compiled game payloads are intentionally not committed to the source tree.

Vanilla *Virtual Families 2* saves are compatible with the modded version. The patcher creates a separate modded game folder by default and does not overwrite the selected vanilla installation.

## What the patcher does

- Validates a user-selected official VF2 installation before changing files.
- Applies only the patches selected in the manifest-driven GUI.
- Creates or refreshes a clearly named modded copy of the game.
- Supports dry-run validation, backups, restore, and machine-readable logs.
- Uses offline file patching; it does not inject into a running process.

After extracting a release, run `Launch_GUI.bat`. The exported bundle also contains `How to Use.txt` with player-facing instructions.
Release bundles include the instruction-only `vf2_crash_capture.py` helper and
an unfilled exact-build manifest template for optional crash QA. Neither the
patcher nor that helper changes the registry or launches VF2; any generated WER
instructions must be reviewed and run manually by the player.

## Source layout

- `work/offline_vf2_patcher.py` - command-line patcher and validation/apply/restore engine.
- `work/offline_vf2_patcher_gui.py` - Tkinter GUI.
- `work/export_offline_patch_bundle.py` - self-contained release-bundle exporter.
- `work/vf2_crash_capture.py` - exact-build dump/log validation and IDA handoff helper.
- `work/patch_mobile_furniture_pack.py` - native VF2 build/patch pipeline.
- `work/test_*.py` - source, binary-contract, exporter, runner, and GUI tests.
- `work/assets/holiday_collectibles/` - curated Holiday Ornament source art and reproducible runtime assets.
- `docs/offline-patcher.md` - technical patcher documentation.
- `docs/Transparency Log.txt` - implementation and verification disclosures.
- `docs/REQUEST_LEDGER.md` - durable shipped/partial/unverified/deferred request
  inventory and release-completeness gate.
- `docs/discoveries.md` and `docs/TODO.md` - reverse-engineering evidence and remaining manual checks.

## Development

The project is designed to be self-contained. Do not add dependencies on Downloads, Desktop, OneDrive, or another private repository. Build outputs, extracted payloads, executables, caches, and archives stay out of Git and are distributed only through the latest GitHub Release.

Run the Python test modules from the repository root with a compatible Python 3 interpreter, for example:

```powershell
python -m unittest work.test_offline_vf2_patcher work.test_export_offline_patch_bundle work.test_offline_vf2_patcher_gui work.test_patch_mobile_furniture_pack
```
