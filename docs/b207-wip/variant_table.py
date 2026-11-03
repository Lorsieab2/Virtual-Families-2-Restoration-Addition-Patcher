"""Print the variant table (size, SHA-256) of a matrix and the release DLL hashes, and check distinctness.

usage: variant_table.py <outputs dir> <prefix> <exe name> <runtime build dir>
"""
import hashlib
import sys
from pathlib import Path

out, prefix, exe_name, build = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
rows = []
for d in sorted(out.glob(prefix + "-*")):
    exe = d / exe_name
    if d.is_dir() and exe.is_file():
        data = exe.read_bytes()
        rows.append((d.name[len(prefix) + 1:], len(data), hashlib.sha256(data).hexdigest()))
print(f"variants: {len(rows)}; distinct SHA-256: {len({r[2] for r in rows})}")
print()
for dll in sorted(build.glob("*.dll")):
    print(f"- `{dll.name}`: SHA-256 `{hashlib.sha256(dll.read_bytes()).hexdigest()}`.")
print()
print("| Variant | Size (bytes) | SHA-256 |")
print("|---|---|---|")
for name, size, sha in rows:
    print(f"| {name} | {size} | `{sha}` |")
