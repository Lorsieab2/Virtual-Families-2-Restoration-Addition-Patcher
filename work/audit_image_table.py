"""Audit the image descriptor table in every built variant.

Two questions, after Bathroom 1's curtain colour was written into id 615 --
familytree_bg.jpg -- and the only symptom was a screen that quietly stopped
drawing:

  1. Does any build overwrite a STOCK image slot?
  2. Do the images a variant ADDS ever collide with a stock id?

Read from the linked EXEs, so the check covers what actually ships rather
than what the generator believed it was doing.

The table is anchored on a known stock entry rather than by pattern
matching: image ids are not contiguous with their index (index 611 holds
id 615), so a "first dword counts up" heuristic finds a false table.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Owner\repos\Virtual-Families-2-Restoration-Addition-Patcher")
DESC_SIZE = 0x30
ANCHOR_NAME = b"familytree_bg.jpg\x00"
ANCHOR_INDEX = 611          # its index in image-descriptors.json


def stock_records() -> list[dict]:
    recs = json.loads(
        (ROOT / "data" / "vf2" / "image-descriptors.json").read_text(encoding="utf-8-sig")
    )
    return recs["records"] if isinstance(recs, dict) else recs


def reader(data: bytes):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    secs = []
    for i in range(nsec):
        o = pe + 24 + opt + i * 40
        secs.append((base + struct.unpack_from("<I", data, o + 12)[0],
                     struct.unpack_from("<I", data, o + 20)[0],
                     struct.unpack_from("<I", data, o + 16)[0]))

    def va2off(va):
        for v, raw, rsz in secs:
            if v <= va < v + rsz:
                return raw + (va - v)
        return None

    def off2va(off):
        for v, raw, rsz in secs:
            if raw <= off < raw + rsz:
                return v + (off - raw)
        return None

    def cstr(va):
        o = va2off(va)
        if o is None:
            return None
        e = data.find(b"\0", o, o + 300)
        return data[o:e].decode("latin1") if e > 0 else None

    return off2va, cstr


def audit(exe: Path, stock: list[dict]) -> tuple[list[str], list[str]]:
    data = exe.read_bytes()
    off2va, cstr = reader(data)
    name = exe.parent.name.replace("VF2-B169-matrix-20260817-", "")

    soff = data.find(ANCHOR_NAME)
    if soff < 0:
        return [], [f"{name}: anchor string not present"]
    sva = off2va(soff)
    hits = [i for i in range(0, len(data) - 4, 4)
            if struct.unpack_from("<I", data, i)[0] == sva]
    if len(hits) != 1:
        return [], [f"{name}: anchor pointer found {len(hits)} times, expected 1"]
    table = hits[0] - ANCHOR_INDEX * DESC_SIZE

    problems = []
    # 1. every stock slot must still name the same file
    for rec in stock:
        idx = rec["index"]
        ptr = struct.unpack_from("<I", data, table + idx * DESC_SIZE)[0]
        got = cstr(ptr) if ptr else None
        want = rec.get("path")
        if want is None:
            continue
        if got != want:
            problems.append(f"{name}: STOCK index {idx} (id {rec['image_id']}) "
                            f"is {got!r}, expected {want!r}")

    # 2. added entries must sit past the stock table and not reuse a stock id
    stock_ids = {r["image_id"] for r in stock}
    added = 0
    collisions = []
    i = len(stock)
    while True:
        off = table + i * DESC_SIZE
        if off + DESC_SIZE > len(data):
            break
        ptr = struct.unpack_from("<I", data, off)[0]
        got = cstr(ptr) if ptr else None
        if not (got and got.lower().endswith((".png", ".jpg"))):
            break
        image_id = struct.unpack_from("<I", data, off + 0x2C)[0]
        if image_id in stock_ids:
            collisions.append(f"{name}: ADDED entry {i} ({got}) reuses stock id {image_id}")
        added += 1
        i += 1
    problems.extend(collisions)
    return [f"{name}: stock 0..{len(stock)-1} intact, {added} added, no id collisions"], problems


def main() -> int:
    stock = stock_records()
    exes = sorted((ROOT / "outputs").glob("VF2-B169-matrix-20260817-*/*.exe"))
    ok_lines, all_problems = [], []
    for exe in exes:
        good, bad = audit(exe, stock)
        ok_lines.extend(good)
        all_problems.extend(bad)
    for line in ok_lines:
        print("  OK  " + line)
    if all_problems:
        print("\nPROBLEMS:")
        for p in all_problems[:40]:
            print("  !! " + p)
    print(f"\n{len(exes)} variants audited, {len(all_problems)} problem(s)")
    return 1 if all_problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
