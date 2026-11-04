"""Line breaking for scripts written without spaces (UAX #14, the basics): the table the Unicode Text DLL uses when
Windows has no icu.dll, and the rule the patcher's own line wrapping (vf2_game_text.next_justified_line) uses.

The same table as Virtual Families 1's patcher/vf1_line_break.py and native/vf1text/linebreak.inc.
runtime/tools/gen_b200_line_break.py writes it for the DLL (runtime/native/b200unicode/b200linebreak_table.h);
tests/test_line_break.py checks the two are the same.

  IDEOGRAPHIC: a letter of a script written without spaces (ideographs, kana, Hangul, Yi, Thai, Lao, Myanmar, Khmer
               and the other SA scripts, emoji): a line may break before and after it;
  CLOSING:     closing punctuation and the Japanese small kana, iteration marks and the long vowel mark (UAX #14 CL,
               CP, EX, IS, NS, CJ): no line starts with it (kinsoku);
  OPENING:     opening punctuation (UAX #14 OP): no line ends with it.
"""
from __future__ import annotations

import bisect

OTHER, IDEOGRAPHIC, CLOSING, OPENING = 0, 1, 2, 3
ZWSP = 0x200B

# (first, last, class), sorted, not overlapping
FALLBACK_RANGES = (
    (0x0021, 0x0021, CLOSING), (0x0028, 0x0028, OPENING), (0x0029, 0x0029, CLOSING), (0x002C, 0x002C, CLOSING),
    (0x002E, 0x002E, CLOSING), (0x003A, 0x003B, CLOSING), (0x003F, 0x003F, CLOSING), (0x005B, 0x005B, OPENING),
    (0x005D, 0x005D, CLOSING), (0x007B, 0x007B, OPENING), (0x007D, 0x007D, CLOSING), (0x0E00, 0x0EFF, IDEOGRAPHIC),
    (0x1000, 0x109F, IDEOGRAPHIC), (0x1100, 0x115F, IDEOGRAPHIC), (0x1780, 0x17FF, IDEOGRAPHIC),
    (0x1950, 0x19DF, IDEOGRAPHIC), (0x1A20, 0x1AAF, IDEOGRAPHIC), (0x2018, 0x2018, OPENING),
    (0x2019, 0x2019, CLOSING), (0x201C, 0x201C, OPENING), (0x201D, 0x201D, CLOSING), (0x2E80, 0x2FFF, IDEOGRAPHIC),
    (0x3000, 0x3000, IDEOGRAPHIC), (0x3001, 0x3002, CLOSING), (0x3003, 0x3004, IDEOGRAPHIC),
    (0x3005, 0x3005, CLOSING), (0x3006, 0x3007, IDEOGRAPHIC), (0x3008, 0x3008, OPENING), (0x3009, 0x3009, CLOSING),
    (0x300A, 0x300A, OPENING), (0x300B, 0x300B, CLOSING), (0x300C, 0x300C, OPENING), (0x300D, 0x300D, CLOSING),
    (0x300E, 0x300E, OPENING), (0x300F, 0x300F, CLOSING), (0x3010, 0x3010, OPENING), (0x3011, 0x3011, CLOSING),
    (0x3012, 0x3013, IDEOGRAPHIC), (0x3014, 0x3014, OPENING), (0x3015, 0x3015, CLOSING), (0x3016, 0x3016, OPENING),
    (0x3017, 0x3017, CLOSING), (0x3018, 0x3018, OPENING), (0x3019, 0x3019, CLOSING), (0x301A, 0x301A, OPENING),
    (0x301B, 0x301B, CLOSING), (0x301C, 0x301C, CLOSING), (0x301D, 0x301D, OPENING), (0x301E, 0x301F, CLOSING),
    (0x3020, 0x303A, IDEOGRAPHIC), (0x303B, 0x303C, CLOSING), (0x303D, 0x3040, IDEOGRAPHIC),
    (0x3041, 0x3041, CLOSING), (0x3042, 0x3042, IDEOGRAPHIC), (0x3043, 0x3043, CLOSING),
    (0x3044, 0x3044, IDEOGRAPHIC), (0x3045, 0x3045, CLOSING), (0x3046, 0x3046, IDEOGRAPHIC),
    (0x3047, 0x3047, CLOSING), (0x3048, 0x3048, IDEOGRAPHIC), (0x3049, 0x3049, CLOSING),
    (0x304A, 0x3062, IDEOGRAPHIC), (0x3063, 0x3063, CLOSING), (0x3064, 0x3082, IDEOGRAPHIC),
    (0x3083, 0x3083, CLOSING), (0x3084, 0x3084, IDEOGRAPHIC), (0x3085, 0x3085, CLOSING),
    (0x3086, 0x3086, IDEOGRAPHIC), (0x3087, 0x3087, CLOSING), (0x3088, 0x308D, IDEOGRAPHIC),
    (0x308E, 0x308E, CLOSING), (0x308F, 0x3094, IDEOGRAPHIC), (0x3095, 0x3096, CLOSING),
    (0x3097, 0x309A, IDEOGRAPHIC), (0x309B, 0x309E, CLOSING), (0x309F, 0x30A0, IDEOGRAPHIC),
    (0x30A1, 0x30A1, CLOSING), (0x30A2, 0x30A2, IDEOGRAPHIC), (0x30A3, 0x30A3, CLOSING),
    (0x30A4, 0x30A4, IDEOGRAPHIC), (0x30A5, 0x30A5, CLOSING), (0x30A6, 0x30A6, IDEOGRAPHIC),
    (0x30A7, 0x30A7, CLOSING), (0x30A8, 0x30A8, IDEOGRAPHIC), (0x30A9, 0x30A9, CLOSING),
    (0x30AA, 0x30C2, IDEOGRAPHIC), (0x30C3, 0x30C3, CLOSING), (0x30C4, 0x30E2, IDEOGRAPHIC),
    (0x30E3, 0x30E3, CLOSING), (0x30E4, 0x30E4, IDEOGRAPHIC), (0x30E5, 0x30E5, CLOSING),
    (0x30E6, 0x30E6, IDEOGRAPHIC), (0x30E7, 0x30E7, CLOSING), (0x30E8, 0x30ED, IDEOGRAPHIC),
    (0x30EE, 0x30EE, CLOSING), (0x30EF, 0x30F4, IDEOGRAPHIC), (0x30F5, 0x30F6, CLOSING),
    (0x30F7, 0x30FA, IDEOGRAPHIC), (0x30FB, 0x30FE, CLOSING), (0x30FF, 0x31FF, IDEOGRAPHIC),
    (0x3200, 0x4DBF, IDEOGRAPHIC), (0x4E00, 0x9FFF, IDEOGRAPHIC), (0xA000, 0xA4CF, IDEOGRAPHIC),
    (0xA960, 0xA97F, IDEOGRAPHIC), (0xAA60, 0xAADF, IDEOGRAPHIC), (0xAC00, 0xD7FF, IDEOGRAPHIC),
    (0xF900, 0xFAFF, IDEOGRAPHIC), (0xFE30, 0xFE4F, IDEOGRAPHIC), (0xFF01, 0xFF01, CLOSING),
    (0xFF02, 0xFF07, IDEOGRAPHIC), (0xFF08, 0xFF08, OPENING), (0xFF09, 0xFF09, CLOSING),
    (0xFF0A, 0xFF0B, IDEOGRAPHIC), (0xFF0C, 0xFF0C, CLOSING), (0xFF0D, 0xFF0D, IDEOGRAPHIC),
    (0xFF0E, 0xFF0E, CLOSING), (0xFF0F, 0xFF19, IDEOGRAPHIC), (0xFF1A, 0xFF1B, CLOSING),
    (0xFF1C, 0xFF1E, IDEOGRAPHIC), (0xFF1F, 0xFF1F, CLOSING), (0xFF20, 0xFF3A, IDEOGRAPHIC),
    (0xFF3B, 0xFF3B, OPENING), (0xFF3C, 0xFF3C, IDEOGRAPHIC), (0xFF3D, 0xFF3D, CLOSING),
    (0xFF3E, 0xFF5A, IDEOGRAPHIC), (0xFF5B, 0xFF5B, OPENING), (0xFF5C, 0xFF5C, IDEOGRAPHIC),
    (0xFF5D, 0xFF5D, CLOSING), (0xFF5E, 0xFF60, IDEOGRAPHIC), (0xFF61, 0xFF61, CLOSING), (0xFF62, 0xFF62, OPENING),
    (0xFF63, 0xFF64, CLOSING), (0xFF65, 0xFFEF, IDEOGRAPHIC), (0x16FE0, 0x18AFF, IDEOGRAPHIC),
    (0x1B000, 0x1B2FF, IDEOGRAPHIC), (0x1F000, 0x1FAFF, IDEOGRAPHIC), (0x20000, 0x3FFFD, IDEOGRAPHIC),
)
_FIRSTS = [r[0] for r in FALLBACK_RANGES]


def line_class(cp: int) -> int:
    i = bisect.bisect_right(_FIRSTS, cp) - 1
    if i >= 0 and cp <= FALLBACK_RANGES[i][1]:
        return FALLBACK_RANGES[i][2]
    return OTHER


def no_space_letter(cp: int) -> bool:
    """A letter of a script written without spaces: the CJK punctuation blocks, and the table's ideographic class."""
    if 0x3000 <= cp <= 0x303F or 0xFE30 <= cp <= 0xFE4F or 0xFF00 <= cp <= 0xFFEF:
        return True
    return line_class(cp) == IDEOGRAPHIC


def may_break(before: int, after: int) -> bool:
    """May a line break between a character `before` and one `after`? Next to an ideographic letter, unless the next
    one is closing punctuation or the one before opens; after closing punctuation before an opening one."""
    a, b = line_class(before), line_class(after)
    if b == CLOSING or a == OPENING:
        return False
    return a == IDEOGRAPHIC or b == IDEOGRAPHIC or (a == CLOSING and b == OPENING)


def break_flags(chars: list[tuple[int, int]], texts: list[tuple[int, ...]] | None = None) -> list[bool]:
    """Where a line may break in a text of characters (clusters), each given as (its first code point, its last): flags[i]
    is True when a line may break between character i - 1 and character i (flags has len + 1 entries). Only text with a
    letter of a script written without spaces, or a zero width space, has any; a break is never next to a space or a
    line feed, and only next to such a letter (or after a zero width space) where the rules allow it.

    With `texts` (each character's code points, at most 16, as the DLL keeps them) the rules are the DLL's in full
    (b200unicode_text.h ComputeBreaks): Windows' icu.dll when it is there (use_icu), else the table and, inside a run of
    Thai, Lao, Khmer or Burmese letters, the ICU word lists. Without `texts`, the table alone."""
    n = len(chars)
    flags = [False] * (n + 1)
    icu = _icu() if texts is not None else None
    no_space = icu.no_space_letter if icu else no_space_letter
    if not any(no_space(first) or first == ZWSP for first, _last in chars):
        return flags
    bounds = at16 = None
    if icu:
        text16, at16 = [], []
        for t in texts:
            at16.append(len(text16))
            for cp in t:
                text16 += [0xD800 + ((cp - 0x10000) >> 10), 0xDC00 + ((cp - 0x10000) & 0x3FF)] if cp >= 0x10000 else [cp]
        at16.append(len(text16))
        bounds = icu.boundaries(text16)
    for i in range(1, n):
        before, after, last = chars[i - 1][0], chars[i][0], chars[i - 1][1]
        if before in (0x20, 0x0A) or after in (0x20, 0x0A):
            continue
        if not (no_space(before) or no_space(after) or last == ZWSP):
            continue
        flags[i] = bounds[at16[i]] if bounds is not None else (last == ZWSP or may_break(before, after))
    if texts is not None and bounds is None:
        _dictionary_breaks(chars, texts, flags)
    return flags


# ---------------------------------------------------------------------------------------------- the word lists
# ICU 77-1's own word lists (runtime/word-lists, copied unchanged; tests/test_word_lists.py checks each SHA-256), used
# only without icu.dll, which has the same lists built in. runtime/native/b200unicode/b200words.h is the same rule.
WORD_LIST_FILES = ("thaidict.txt", "laodict.txt", "khmerdict.txt", "burmesedict.txt")
_lists: dict = {}
WORD_LISTS_FOLDER = [None]       # None: beside this file (the shipped patcher), else the repo's runtime/word-lists


def word_list_of(cp: int) -> int:
    """The word list of a code point's script (0 Thai, 1 Lao, 2 Khmer, 3 Burmese), or -1."""
    if 0x0E00 <= cp <= 0x0E7F:
        return 0
    if 0x0E80 <= cp <= 0x0EFF:
        return 1
    if 0x1780 <= cp <= 0x17FF or 0x19E0 <= cp <= 0x19FF:
        return 2
    if 0x1000 <= cp <= 0x109F or 0xA9E0 <= cp <= 0xA9FF or 0xAA60 <= cp <= 0xAA7F:
        return 3
    return -1


def word_list(which: int):
    """(the words as code point tuples, the longest one's length), read the first time; None without the file. The
    DLL's reading: a byte order mark skipped, "#" lines skipped, a word ends at a tab, strict UTF-8, 1..32 code points."""
    key = (which, WORD_LISTS_FOLDER[0])
    if key not in _lists:
        from pathlib import Path
        here = Path(__file__).resolve().parent
        folders = [Path(WORD_LISTS_FOLDER[0])] if WORD_LISTS_FOLDER[0] else [here / "word-lists",
                                                                             here.parent / "runtime" / "word-lists"]
        data = None
        for folder in folders:
            try:
                data = (folder / WORD_LIST_FILES[which]).read_bytes()
                break
            except OSError:
                pass
        got = None
        if data is not None and len(data) <= (8 << 20):
            words, longest = set(), 0
            for line in data[3 if data.startswith(b"\xef\xbb\xbf") else 0:].split(b"\n"):
                line = line.split(b"\t", 1)[0].rstrip(b"\r ")
                if not line or line.startswith(b"#"):
                    continue
                try:
                    cps = tuple(ord(c) for c in line.decode("utf-8", "strict"))
                except UnicodeDecodeError:
                    continue
                if 0 < len(cps) <= 32 and not any(0xD800 <= c <= 0xDFFF for c in cps):
                    words.add(cps)
                    longest = max(longest, len(cps))
            got = (words, longest) if words else None
        _lists[key] = got
    return _lists[key]


def _dictionary_breaks(chars, texts, flags) -> None:
    """Inside a run of two or more characters of one listed script a line may break only between its words: from the
    run's start the longest listed word that ends at a whole character (at most 64 code points), else one character."""
    n, a = len(chars), 0
    while a < n:
        which = word_list_of(chars[a][0])
        b = a + 1
        if which >= 0:
            while b < n and word_list_of(chars[b][0]) == which:
                b += 1
        lst = word_list(which) if which >= 0 and b - a > 1 else None
        if lst:
            words, longest = lst[0], min(lst[1], 64)
            for i in range(a + 1, b):
                flags[i] = False
            pos = a
            while pos < b:
                best, word = pos + 1, ()
                for k in range(pos, b):
                    if len(word) + len(texts[k]) > longest:
                        break
                    word += tuple(texts[k])
                    if word in words:
                        best = k + 1
                if best < b:
                    flags[best] = True
                pos = best
        a = b


# ---------------------------------------------------------------------------------------------- Windows' ICU
_icu_state = {"on": True, "api": None, "looked": False}


def use_icu(on: bool) -> None:
    """Whether the rules may use Windows' icu.dll (the DLL's first choice; tests turn it off to match the DLL without
    it)."""
    _icu_state["on"] = bool(on)


class _Icu:
    """icu.dll from System32 (Windows 10 1903 and later), used as b200icu.h uses it."""

    def __init__(self, dll):
        import ctypes
        c = self.c = ctypes
        self.open = dll.ubrk_open
        self.open.restype = c.c_void_p
        self.open.argtypes = [c.c_int, c.c_char_p, c.c_void_p, c.c_int32, c.POINTER(c.c_int)]
        self.first, self.next, self.close, self.prop = dll.ubrk_first, dll.ubrk_next, dll.ubrk_close, dll.u_getIntPropertyValue
        for f in (self.first, self.next):
            f.restype, f.argtypes = c.c_int32, [c.c_void_p]
        self.close.restype, self.close.argtypes = None, [c.c_void_p]
        self.prop.restype, self.prop.argtypes = c.c_int32, [c.c_int32, c.c_int]

    def no_space_letter(self, cp: int) -> bool:
        if 0x3000 <= cp <= 0x303F or 0xFE30 <= cp <= 0xFE4F or 0xFF00 <= cp <= 0xFFEF:
            return True
        return self.prop(cp, 0x1008) in (14, 24, 31, 32, 33, 34, 35, 37, 40, 41)

    def boundaries(self, text16):
        c = self.c
        buf = (c.c_uint16 * (len(text16) + 1))(*text16, 0)
        status = c.c_int(0)
        it = self.open(2, b"", buf, len(text16), c.byref(status))
        ok = bool(it) and status.value <= 0
        out = [False] * (len(text16) + 1)
        if ok:
            b = self.first(it)
            while 0 <= b <= len(text16):
                out[b] = True
                b = self.next(it)
        if it:
            self.close(it)
        return out if ok else None


def _icu():
    if not _icu_state["on"]:
        return None
    if not _icu_state["looked"]:
        _icu_state["looked"] = True
        try:
            import ctypes
            _icu_state["api"] = _Icu(ctypes.CDLL("icu.dll", winmode=0x800))      # LOAD_LIBRARY_SEARCH_SYSTEM32
        except (OSError, AttributeError):
            _icu_state["api"] = None
    return _icu_state["api"]
