"""The Game Mechanics window (the Tools tab's "Game Mechanics..." link): Virtual Families 2's hidden rules.

Laid out as the Virtual Villagers patcher's Game Mechanics window: an intro, the line that explains the labels, a
link to each group at the top, then the page in a read-only Text box with its own scroll bar that takes the rest
of the resizable window, each group under its heading and every line a bullet.  Each line carries its label right
after the bullet -- VERIFIED-E, VERIFIED-C or UNCONFIRMED (src/vf2_game_mechanics.py) -- in capitals and in its
own colour, so it is always visible.  Times are real times at the game's normal speed.

It only shows text: it reads no save, writes nothing (no save, install, log, data or settings file), and runs
nothing else, so it may be open while the game runs.  Closing it destroys only the window.
"""
from __future__ import annotations

import contextlib
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import vf2_game_mechanics as gm

TITLE = gm.TITLE
WIDTH, HEIGHT = 900, 720
MIN_WIDTH, MIN_HEIGHT = 600, 600
# 3, not 4: in 4 columns the 15 group links need 690 pixels, more than the window has at its smallest (600 less the
# 12-pixel padding each side); in 3 they need 511 (tests/test_game_mechanics.py).
LINKS_PER_ROW = 3
PADDING = 12
LABEL_COLOURS = {gm.VERIFIED_E: "#1b6e20", gm.VERIFIED_C: "#1f4e9c", gm.UNCONFIRMED: "#b00020"}
# The VF1 patcher's Game Mechanics fonts, so the two patchers' tools look the same (the owner prefers VF1's).
PAGE_FONT, HEADING_FONT, LABEL_FONT = ("Segoe UI", 10), ("Segoe UI", 12, "bold"), ("Segoe UI", 9, "bold")
NOTE_RED = LABEL_COLOURS[gm.UNCONFIRMED]


def open_game_mechanics(parent: tk.Misc) -> tk.Toplevel:
    """Open the window over `parent` and return it."""
    window = tk.Toplevel(parent)
    window.title(TITLE)
    with contextlib.suppress(tk.TclError):
        window.transient(parent)
    width = min(WIDTH, max(MIN_WIDTH, window.winfo_screenwidth() - 80))
    height = min(HEIGHT, max(MIN_HEIGHT, window.winfo_screenheight() - 120))
    window.geometry(f"{width}x{height}")
    window.minsize(MIN_WIDTH, MIN_HEIGHT)
    window.resizable(True, True)

    outer = ttk.Frame(window, padding=PADDING)
    outer.pack(fill="both", expand=True)
    top = ttk.Frame(outer)
    top.pack(fill="x")
    intro = ttk.Label(top, text=gm.INTRO, wraplength=width - 60, justify="left")
    intro.pack(anchor="w")
    note = ttk.Label(top, text=gm.LABEL_NOTE, wraplength=width - 60, justify="left", foreground=NOTE_RED)
    note.pack(anchor="w", pady=(4, 8))
    top.bind("<Configure>", lambda event: (intro.configure(wraplength=max(200, event.width - 8)),
                                           note.configure(wraplength=max(200, event.width - 8))))
    links = ttk.Frame(outer)
    links.pack(fill="x", pady=(0, 6))
    buttons = ttk.Frame(outer)
    buttons.pack(side="bottom", fill="x", pady=(8, 0))
    body = ttk.Frame(outer)
    body.pack(fill="both", expand=True)

    page = tk.Text(body, wrap="word", padx=10, pady=8, cursor="arrow", borderwidth=1, relief="solid",
                   font=PAGE_FONT)
    scroll = ttk.Scrollbar(body, orient="vertical", command=page.yview)
    page.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    page.pack(side="left", fill="both", expand=True)

    page.tag_configure("heading", font=HEADING_FONT, spacing1=10, spacing3=4)
    page.tag_configure("line", lmargin1=8, lmargin2=28, spacing3=2)
    page.tag_configure("sub", lmargin1=28, lmargin2=48, spacing3=1)
    for label, colour in LABEL_COLOURS.items():
        page.tag_configure(label, foreground=colour, font=LABEL_FONT)

    marks: dict[str, str] = {}
    for kind, label, text in gm.render_lines():
        if kind == "heading":
            marks[text] = page.index("end-1c")
            page.insert("end", text + "\n", "heading")
            continue
        sub = text.startswith(gm.SUB_BULLET)
        mark = gm.SUB_BULLET if sub else gm.BULLET
        style = "sub" if sub else "line"
        page.insert("end", mark, style)
        page.insert("end", label, (style, label))
        page.insert("end", "  " + text[len(mark):] + "\n", style)
    page.configure(state="disabled")

    def jump(group: str) -> None:
        page.see("end")
        page.see(marks[group])
        page.yview(marks[group])

    link_font = tkfont.nametofont("TkDefaultFont").copy()   # underlined, as the patcher's own links
    link_font.configure(underline=True)
    window.mechanics_fonts = (link_font,)             # kept while the window is open
    for index, group in enumerate(gm.GROUPS):
        link = ttk.Label(links, text=group, foreground="#0645ad", cursor="hand2", font=link_font)
        link.grid(row=index // LINKS_PER_ROW, column=index % LINKS_PER_ROW, sticky="w", padx=(0, 18), pady=1)
        link.bind("<Button-1>", lambda _event, g=group: jump(g))

    close = ttk.Button(buttons, text="Close", command=window.destroy)
    close.pack(side="right")
    window.bind("<Escape>", lambda _event: window.destroy())
    with contextlib.suppress(tk.TclError):
        close.focus_set()

    window.mechanics_page = page                       # for the tests
    window.mechanics_marks = marks
    window.mechanics_links = links
    window.mechanics_jump = jump
    return window
