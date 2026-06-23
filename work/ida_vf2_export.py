import json
import sys

import ida_auto
import ida_bytes
import ida_funcs
import ida_kernwin
import ida_name
import ida_segment
import ida_xref
import idautils
import idc


def s_at(ea, max_len=256):
    raw = ida_bytes.get_strlit_contents(ea, -1, ida_nalt.STRTYPE_C) if False else None
    if raw is None:
        raw = idc.get_strlit_contents(ea, -1, idc.STRTYPE_C)
    if raw is None:
        return None
    try:
        return raw.decode("utf-8", "replace")[:max_len]
    except AttributeError:
        return str(raw)[:max_len]


def func_name(ea):
    f = ida_funcs.get_func(ea)
    if not f:
        return None
    return ida_name.get_ea_name(f.start_ea), f.start_ea, f.end_ea


def xrefs_to(ea, limit=80):
    out = []
    for xr in idautils.XrefsTo(ea):
        info = func_name(xr.frm)
        out.append({
            "from": hex(xr.frm),
            "type": int(xr.type),
            "function": info[0] if info else None,
            "function_start": hex(info[1]) if info else None,
        })
        if len(out) >= limit:
            break
    return out


def main():
    ida_auto.auto_wait()
    out_path = idc.ARGV[1] if len(idc.ARGV) > 1 else "ida-vf2-export.json"
    keywords = [
        "Collect", "Collection", "CommunityEvent", "Event", "Villager",
        "Anim", "Inventory", "Furniture", "StringManager", "stringTable",
        "lookupTable", "ImageList", "ImageIndex",
    ]
    funcs = []
    for ea in idautils.Functions():
        name = ida_name.get_ea_name(ea)
        if any(k.lower() in name.lower() for k in keywords):
            f = ida_funcs.get_func(ea)
            funcs.append({"ea": hex(ea), "end": hex(f.end_ea), "name": name, "size": f.end_ea - ea})

    names = []
    for i in range(ida_name.get_nlist_size()):
        ea = ida_name.get_nlist_ea(i)
        name = ida_name.get_nlist_name(i)
        if any(k.lower() in name.lower() for k in keywords):
            names.append({"ea": hex(ea), "name": name, "xrefs_to": xrefs_to(ea, 30)})

    strings = []
    for st in idautils.Strings():
        text = str(st)
        if any(k.lower() in text.lower() for k in keywords + ["Bottle", "Ornament", "Chaise", "Patio", "Birthday"]):
            strings.append({"ea": hex(st.ea), "text": text[:300], "xrefs_to": xrefs_to(st.ea, 30)})

    segments = []
    for segea in idautils.Segments():
        seg = ida_segment.getseg(segea)
        segments.append({
            "name": ida_segment.get_segm_name(seg),
            "start": hex(seg.start_ea),
            "end": hex(seg.end_ea),
            "size": seg.end_ea - seg.start_ea,
        })

    data = {
        "input": idc.get_input_file_path(),
        "segments": segments,
        "functions": funcs,
        "names": names,
        "strings": strings,
    }
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    idc.qexit(0)


if __name__ == "__main__":
    main()
