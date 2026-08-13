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
    lines = ["LIBRARY fmod.dll", "EXPORTS"]
    for line in text.splitlines():
        m = re.match(r"\s*(\d+)\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(\S+)", line)
        if not m:
            continue
        ordinal = int(m.group(1))
        export = m.group(2)
        if export.startswith("_") and "@" in export:
            public_name = export[1:]
            lines.append(f"  {public_name} @{ordinal} NONAME")
        else:
            lines.append(f"  {export} @{ordinal}")

    def_path = OUT / "fmod_ordinal.def"
    lib_path = OUT / "fmod_ordinal.lib"
    def_path.write_text("\n".join(lines) + "\n", encoding="ascii")
    subprocess.check_call([str(LIB), f"/DEF:{def_path}", f"/OUT:{lib_path}", "/MACHINE:X86"])
    print(lib_path)


if __name__ == "__main__":
    main()
