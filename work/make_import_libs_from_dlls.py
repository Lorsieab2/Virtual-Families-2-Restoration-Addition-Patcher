from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DLL_DIR = ROOT / "work" / "desktop_runtime_dlls"
OUT = ROOT / "work" / "generated_import_libs"
DUMPBIN = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x64\dumpbin.exe")
LIB = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86\lib.exe")


def exports_for(dll: Path):
    text = subprocess.check_output([str(DUMPBIN), "/exports", str(dll)], text=True, errors="replace")
    names = []
    for line in text.splitlines():
        m = re.match(r"\s*\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(\S+)", line)
        if m:
            name = m.group(1)
            if name and name not in names:
                names.append(name)
    return names


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for dll in sorted(DLL_DIR.glob("*.dll")):
        names = exports_for(dll)
        if not names:
            continue
        stem = dll.stem
        def_path = OUT / f"{stem}.def"
        lib_path = OUT / f"{stem}.lib"
        lines = [f"LIBRARY {dll.name}", "EXPORTS"]
        lines.extend(f"  {name}" for name in names)
        def_path.write_text("\n".join(lines) + "\n", encoding="ascii")
        subprocess.check_call([str(LIB), f"/DEF:{def_path}", f"/OUT:{lib_path}", "/MACHINE:X86"])
        print(f"{dll.name}: {len(names)} exports -> {lib_path.name}")


if __name__ == "__main__":
    main()
