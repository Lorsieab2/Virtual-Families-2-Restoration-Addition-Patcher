"""Print Owner's Defaults (comma list) and the manifest's default-on ids, from an unzipped bundle.

usage: python -I owners_defaults.py <patcher files folder> <manifest.json> owners|defaults|all
"""
import json
import sys

folder, manifest_path, which = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, folder)
import offline_vf2_patcher as patcher  # noqa: E402
import offline_vf2_patcher_gui as gui  # noqa: E402

with open(manifest_path, encoding="utf-8") as fh:
    manifest = json.load(fh)
settings = patcher.manifest_settings(manifest)
if which == "owners":
    print(",".join(sorted(gui.owners_default_selection(settings))))
elif which == "defaults":
    print(",".join(sorted(k for k, s in settings.items() if s.default)))
else:
    for k, s in sorted(settings.items()):
        print(k, "default=" + str(s.default), "blocked=" + str(s.blocked),
              "category=" + str(getattr(s, "category", None)))

