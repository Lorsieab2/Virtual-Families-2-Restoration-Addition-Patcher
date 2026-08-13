from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "work" / "desktop_runtime_dlls" / "fmod.dll"
OUT = ROOT / "work" / "generated_import_libs"
DUMPBIN = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x64\dumpbin.exe")
LIB = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86\lib.exe")


def main():
    text = subprocess.check_output([str(DUMPBIN), "/exports", str(DLL)], text=True, errors="replace")
    exports = []
    for line in text.splitlines():
        m = re.match(r"\s*\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(\S+)", line)
        if m:
            exports.append(m.group(1))

    lines = ["LIBRARY fmod.dll", "EXPORTS"]
    for name in exports:
        if name.startswith("_") and "@" in name:
            # x86 import libraries add a C leading underscore. Alias the
            # undecorated spelling to the DLL's already-decorated export so
            # the produced COFF symbol is exactly _Name@N, not __Name@N.
            lines.append(f"  {name[1:]}={name}")
        else:
            lines.append(f"  {name}")

    def_path = OUT / "fmod_alias.def"
    lib_path = OUT / "fmod_alias.lib"
    def_path.write_text("\n".join(lines) + "\n", encoding="ascii")
    subprocess.check_call([str(LIB), f"/DEF:{def_path}", f"/OUT:{lib_path}", "/MACHINE:X86"])
    print(lib_path)


if __name__ == "__main__":
    main()
