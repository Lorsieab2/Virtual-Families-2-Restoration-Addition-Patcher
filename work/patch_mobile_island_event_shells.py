from __future__ import annotations

import csv
import json
import shutil
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "VF2-Mobile-Additive-Furniture-Pack"
TEXT_PACK = Path(
    r"C:\Users\Owner\Downloads\Virtual Families 2 Codex Test Build\VF2 Mod Patchers\mobile_only_event_text_pack.csv"
)
MAPPING_CSV = Path(
    r"C:\Users\Owner\Downloads\Virtual Families 2 Codex Test Build\VF2 Mod Patchers\mobile_event_shell_mapping.csv"
)

IMAGE_BASE_FALLBACK = 0x400000
FILE_ALIGNMENT_FALLBACK = 0x1000
SECTION_ALIGNMENT_FALLBACK = 0x1000
TEXT_RECORD_SIZE = 0x10
MOD_SECTION_NAME = b".vf2ev\0\0"

EVENT_KIND_SUFFIX = {
    "Title": "Title",
    "Desc": "Desc",
    "ChoiceA": "ChoiceA",
    "ChoiceB": "ChoiceB",
    "ResultA": "ResultA",
    "ResultB": "ResultB",
}

EVENT_CHOICE_OVERRIDES = {
    ("GroupOfKidsAtTheDoor", "ChoiceA"): "Take one",
    ("GroupOfKidsAtTheDoor", "ChoiceB"): "No thanks",
    ("HearStrangeSound", "ChoiceA"): "Open the door",
    ("HearStrangeSound", "ChoiceB"): "Walk away",
    ("MenInBlackAtDoor", "ChoiceA"): "Open the door",
    ("MenInBlackAtDoor", "ChoiceB"): "Back away",
    ("MetallicKnockingOnDoor", "ChoiceA"): "Open the door",
    ("MetallicKnockingOnDoor", "ChoiceB"): "Back away",
    ("Volunteer", "ChoiceA"): "Volunteer",
    ("Volunteer", "ChoiceB"): "Sorry, no",
}


def u16(buf: bytes | bytearray, off: int) -> int:
    return struct.unpack_from("<H", buf, off)[0]


def u32(buf: bytes | bytearray, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def p16(buf: bytearray, off: int, value: int) -> None:
    struct.pack_into("<H", buf, off, value)


def p32(buf: bytearray, off: int, value: int) -> None:
    struct.pack_into("<I", buf, off, value)


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def cstr_at(buf: bytes | bytearray, off: int) -> str:
    end = buf.find(b"\0", off)
    if end < 0:
        end = len(buf)
    return buf[off:end].decode("cp1252", "replace")


class PEView:
    def __init__(self, buf: bytes | bytearray):
        self.buf = buf
        self.pe = u32(buf, 0x3C)
        self.section_count = u16(buf, self.pe + 6)
        self.optional_size = u16(buf, self.pe + 20)
        self.optional = self.pe + 24
        self.section_table = self.pe + 24 + self.optional_size
        self.image_base = u32(buf, self.optional + 28) or IMAGE_BASE_FALLBACK
        self.file_alignment = u32(buf, self.optional + 36) or FILE_ALIGNMENT_FALLBACK
        self.section_alignment = u32(buf, self.optional + 32) or SECTION_ALIGNMENT_FALLBACK
        self.sections = []
        for i in range(self.section_count):
            off = self.section_table + i * 40
            name = bytes(buf[off:off + 8]).split(b"\0")[0].decode("ascii", "ignore")
            virtual_size, virtual_addr, raw_size, raw_ptr = struct.unpack_from("<IIII", buf, off + 8)
            self.sections.append((name, virtual_addr, virtual_size, raw_ptr, raw_size))

    def va_to_off(self, va: int) -> int | None:
        rva = va - self.image_base
        for _name, virtual_addr, virtual_size, raw_ptr, raw_size in self.sections:
            span = max(virtual_size, raw_size)
            if virtual_addr <= rva < virtual_addr + span:
                return raw_ptr + (rva - virtual_addr)
        return None

    def off_to_va(self, off: int) -> int | None:
        for _name, virtual_addr, _virtual_size, raw_ptr, raw_size in self.sections:
            if raw_ptr <= off < raw_ptr + raw_size:
                return self.image_base + virtual_addr + (off - raw_ptr)
        return None

    def data_ranges(self):
        for name, _virtual_addr, _virtual_size, raw_ptr, raw_size in self.sections:
            if name in {".data", ".rdata"}:
                yield raw_ptr, raw_ptr + raw_size


def normalize_event_text(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(part.strip() for part in text.split())
    fixes = {
        "electricaloutlet": "electrical outlet",
        "open,ready": "open, ready",
        "There's reward": "There's a reward",
        "it's artificial intelligence": "its artificial intelligence",
        "God love you": "God loves you",
    }
    for old, new in fixes.items():
        text = text.replace(old, new)
    return text


def load_mobile_event_text_rows() -> dict[str, dict[str, str]]:
    events: dict[str, dict[str, str]] = {}
    with TEXT_PACK.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            event_class = row["event_class"]
            kind = row["kind"]
            value = row["value"]
            if not value or kind not in EVENT_KIND_SUFFIX:
                continue
            event_name = event_class.removeprefix("CEvent")
            value = EVENT_CHOICE_OVERRIDES.get((event_name, kind), value)
            events.setdefault(event_name, {})[kind] = normalize_event_text(value)
    return events


def load_shell_mappings() -> list[dict[str, str]]:
    rows = []
    with MAPPING_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # The object rebuild already injects Volunteer as a true extra event.
            # Keep it out of the shell pool to avoid presenting it twice.
            if row["mobile_event"] == "Volunteer":
                continue
            rows.append({"mobile_event": row["mobile_event"], "desktop_shell": row["desktop_shell"]})
    return rows


def find_text_records(buf: bytearray, pe: PEView) -> dict[str, dict[str, int | str]]:
    records: dict[str, dict[str, int | str]] = {}
    for start, end in pe.data_ranges():
        off = start
        while off + TEXT_RECORD_SIZE <= end:
            text_id, key_va, value_va, zero = struct.unpack_from("<IIII", buf, off)
            key_off = pe.va_to_off(key_va)
            value_off = pe.va_to_off(value_va)
            if (
                zero == 0
                and 0 <= text_id < 0x4000
                and key_off is not None
                and value_off is not None
            ):
                key = cstr_at(buf, key_off)
                if key.startswith("eEvent"):
                    records[key] = {
                        "text_id": text_id,
                        "record_off": off,
                        "key": key,
                        "value": cstr_at(buf, value_off),
                    }
                off += TEXT_RECORD_SIZE
            else:
                off += 4
    return records


def add_section(buf: bytearray, payload: bytes) -> tuple[PEView, int]:
    pe = PEView(buf)
    new_header = pe.section_table + pe.section_count * 40
    size_of_headers = u32(buf, pe.pe + 84)
    if new_header + 40 > size_of_headers:
        raise RuntimeError("No room for another PE section header.")
    if any(buf[i] for i in range(new_header, new_header + 40)):
        raise RuntimeError("Section header slot is not empty.")

    last = pe.section_table + (pe.section_count - 1) * 40
    last_virtual_size = u32(buf, last + 8)
    last_virtual_addr = u32(buf, last + 12)
    last_raw_size = u32(buf, last + 16)
    last_raw_ptr = u32(buf, last + 20)

    new_raw_ptr = align(last_raw_ptr + last_raw_size, pe.file_alignment)
    new_virtual_addr = align(last_virtual_addr + last_virtual_size, pe.section_alignment)
    virtual_size = len(payload)
    raw_size = align(len(payload), pe.file_alignment)

    if len(buf) < new_raw_ptr:
        buf.extend(b"\0" * (new_raw_ptr - len(buf)))
    buf.extend(payload)
    buf.extend(b"\0" * (raw_size - len(payload)))

    header = bytearray(40)
    header[0:8] = MOD_SECTION_NAME
    struct.pack_into(
        "<IIIIIIHHI",
        header,
        8,
        virtual_size,
        new_virtual_addr,
        raw_size,
        new_raw_ptr,
        0,
        0,
        0,
        0,
        0xE0000060,
    )
    buf[new_header:new_header + 40] = header
    p16(buf, pe.pe + 6, pe.section_count + 1)
    p32(buf, pe.pe + 80, align(new_virtual_addr + virtual_size, pe.section_alignment))
    return PEView(buf), pe.image_base + new_virtual_addr


def build_payload(mappings: list[dict[str, str]], event_text: dict[str, dict[str, str]]) -> tuple[bytes, dict[str, int]]:
    payload = bytearray(b"VF2EVT01")
    payload.extend(b"\0" * (0x80 - len(payload)))
    offsets: dict[str, int] = {}
    for mapping in mappings:
        mobile_event = mapping["mobile_event"]
        for kind, value in sorted(event_text[mobile_event].items()):
            offsets[f"{mobile_event}:{kind}:key"] = len(payload)
            payload.extend(f"eEvent{mobile_event}{EVENT_KIND_SUFFIX[kind]}".encode("ascii", "ignore") + b"\0")
            offsets[f"{mobile_event}:{kind}:value"] = len(payload)
            payload.extend(value.encode("cp1252", "replace") + b"\0")
    return bytes(payload), offsets


def patch_exe(source: Path, dest: Path) -> dict[str, object]:
    shutil.copy2(source, dest)
    buf = bytearray(dest.read_bytes())
    pe = PEView(buf)
    event_records = find_text_records(buf, pe)
    event_text = load_mobile_event_text_rows()
    mappings = [
        row for row in load_shell_mappings()
        if row["mobile_event"] in event_text
    ]
    payload, offsets = build_payload(mappings, event_text)
    pe, section_va = add_section(buf, payload)

    patched = []
    missing = []
    for mapping in mappings:
        mobile_event = mapping["mobile_event"]
        desktop_shell = mapping["desktop_shell"]
        patched_kinds = 0
        for kind in event_text[mobile_event]:
            shell_key = f"eEvent{desktop_shell}{EVENT_KIND_SUFFIX[kind]}"
            record = event_records.get(shell_key)
            if record is None:
                missing.append({"mobile_event": mobile_event, "desktop_shell": desktop_shell, "kind": kind, "reason": "missing desktop shell key"})
                continue
            record_off = int(record["record_off"])
            p32(buf, record_off + 4, section_va + offsets[f"{mobile_event}:{kind}:key"])
            p32(buf, record_off + 8, section_va + offsets[f"{mobile_event}:{kind}:value"])
            patched_kinds += 1
        patched.append({
            "mobile_event": mobile_event,
            "desktop_shell": desktop_shell,
            "patched_text_records": patched_kinds,
            "mobile_text_records": len(event_text[mobile_event]),
        })

    dest.write_bytes(buf)

    no_text = sorted(
        row["event_class"].removeprefix("CEvent")
        for row in csv.DictReader(TEXT_PACK.open(newline="", encoding="utf-8"))
        if row["kind"] == "no_text_found"
    )
    report = {
        "source": str(source),
        "dest": str(dest),
        "patched_shell_events": patched,
        "shell_event_count": len(patched),
        "true_object_stub_events": ["Volunteer"],
        "mobile_only_without_extracted_text": no_text,
        "missing": missing,
    }
    (dest.with_suffix(".mobile-events.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    source = OUT / "VF2_Added_Pets_and_Events.exe"
    dest = OUT / "Virtual Families 2 - All Mobile Island Events.exe"
    report = patch_exe(source, dest)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
