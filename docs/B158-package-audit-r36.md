# B158 clean package audit r36

The generator now copies only approved runtime/support content from a previous build. It excludes old executables, IDA databases, logs, manifests, object/debug files, backup files, macOS metadata, and `DESKTOP-<identifier>` source files. Generated manifest paths are portable and do not expose local owner paths.

## r36 package

- Folder: `outputs/VF2-B158-Island-Events-Bathroom2-Leaks-20260812-r36`
- Runtime directories: `Assets`, `Images`, `OptionalVisualMods`, `Original Virtual Families 2 Assets`, `Sounds`
- Runtime root files: launcher configuration, `Readme.txt`, six DLLs, `icon.bmp`, manifest, and the patched executable
- Runtime payload validation: 7,242 image files and 316 sound files
- Executable size: 1,742,336 bytes
- Executable SHA-256: `EF9549417A35A9CC194E3E2342556CC59CAACEB18782C4A031A43B6A39B32FB6`

## Audit results

- `DESKTOP-<identifier>` filenames: none
- personal/owner-style filenames: none
- secret/token/private-key pattern matches: none
- macOS metadata files: none
- duplicate root files: none
- byte-identical files inside runtime asset aliases: retained only where separate game, source, restore, or optional paths require them
- complete source suites: 341 tests passed, 2 expected skips

The audit covers static files and package contents. It does not replace player runtime testing.
