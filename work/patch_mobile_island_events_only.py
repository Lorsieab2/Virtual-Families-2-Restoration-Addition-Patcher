from pathlib import Path
import json
import shutil
import struct

import patch_mobile_furniture_pack as base


ROOT = Path(__file__).resolve().parents[1]
PATCHED = ROOT / "work" / "patched_mobile_island_events_only_objs"
OUT = ROOT / "outputs" / "VF2-Mobile-Island-Events-Only-B02"


def patch_event_strings_only(manifest):
    obj = base.CoffObject(PATCHED / "theStringManager.obj")
    table_sym = obj.symbol(base.STRINGTABLE)
    insert_off = table_sym.value + base.ORIG_STRING_COUNT * base.STRING_RECORD_SIZE
    new_rows = []
    helper_lines = []
    string_manifest = []

    for event in base.load_mobile_island_events():
        for string_row in event["strings"]:
            string_id = string_row["string_id"]
            key_sym = f"_vf2eventstr_key_{string_id:X}"
            text_sym = f"_vf2eventstr_text_{string_id:X}"
            helper_lines.append(f'const char {key_sym[1:]}[] = "{base.c_string(string_row["key"])}";')
            helper_lines.append(f'const char {text_sym[1:]}[] = "{base.c_string(string_row["text"])}";')
            new_rows.append((string_id, key_sym, text_sym))
            string_manifest.append({
                "pc_string_id": hex(string_id),
                "source": "mobile island event",
                "event": event["class"],
                "slot": hex(event["slot"]),
                "kind": string_row["kind"],
                "key": string_row["key"],
                "text": string_row["text"],
            })

    payload = b"".join(struct.pack("<IIII", string_id, 0, 0, 0) for string_id, _key, _text in new_rows)
    obj.insert_section_bytes(table_sym.section, insert_off, payload)
    for row_idx, (_string_id, key_sym, text_sym) in enumerate(new_rows):
        row_off = insert_off + row_idx * base.STRING_RECORD_SIZE
        key_symidx = obj.append_undefined_symbol(key_sym)
        text_symidx = obj.append_undefined_symbol(text_sym)
        obj.append_relocation(table_sym.section, row_off + 4, key_symidx)
        obj.append_relocation(table_sym.section, row_off + 8, text_symidx)

    new_count = base.ORIG_STRING_COUNT + len(new_rows)
    new_one_past = base.ORIG_STRING_ONE_PAST_MAX + len(new_rows)
    new_get_max_minus_one = new_one_past - 2
    new_lookup_bytes = new_one_past * 4
    count_patches = base.patch_all_in_sections(obj, {".text$mn"}, struct.pack("<I", base.ORIG_STRING_COUNT), struct.pack("<I", new_count))
    max_patches = base.patch_all_in_sections(obj, {".text$mn"}, struct.pack("<I", base.ORIG_STRING_ONE_PAST_MAX), struct.pack("<I", new_one_past))
    get_guard_patches = base.patch_all_in_sections(obj, {".text$mn"}, struct.pack("<I", base.ORIG_STRING_GET_MAX_MINUS_ONE), struct.pack("<I", new_get_max_minus_one))
    lookup_patches = base.patch_all_in_sections(obj, {".text$mn"}, struct.pack("<I", base.ORIG_STRING_LOOKUP_BYTES), struct.pack("<I", new_lookup_bytes))

    lookup_sym = obj.symbol(base.STRINGLOOKUP)
    obj.grow_bss_section(lookup_sym.section, lookup_sym.value + base.ORIG_STRING_LOOKUP_BYTES, new_lookup_bytes - base.ORIG_STRING_LOOKUP_BYTES)
    obj.write(PATCHED / "theStringManager.obj")
    (PATCHED / "vf2_mobile_string_table.c").write_text("\n".join(helper_lines) + "\n", encoding="ascii")
    manifest["theStringManager"] = {
        "added_strings": len(new_rows),
        "new_string_count": hex(new_count),
        "new_one_past_max": hex(new_one_past),
        "strings": string_manifest,
        "patches": {
            "string_count": count_patches,
            "one_past_max": max_patches,
            "get_guard": get_guard_patches,
            "lookup_bytes": lookup_patches,
        },
    }


def main():
    base.PATCHED = PATCHED
    base.OUT = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    if PATCHED.exists():
        shutil.rmtree(PATCHED)
    base.copy_obj_tree()

    manifest = {
        "build": "VF2-Mobile-Island-Events-Only-B02",
        "base": "desktop VF2 furniture/store/image data untouched",
        "items": [],
    }
    patch_event_strings_only(manifest)
    base.patch_island_events(manifest)
    (OUT / "patch-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
