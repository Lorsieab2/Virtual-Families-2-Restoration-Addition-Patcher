"""Picture Maker (Tools tab -> "Picture Maker..."): the family in a save, and family members you make yourself,
drawn exactly as Virtual Families 2 draws them, saved as PNG pictures with a clear (transparent) background.

The Fish and Plant Tycoon Fix Patcher's Picture Studio (src/picture_studio.py), made for this game:

* "From my save": the save folder and the family (read only); everyone the save holds, by where they are (at
  home, left home, gone: only in the Family Tree), and the outfits in the tool tray, each drawn as the game
  draws them now. A family member at home can be shown in every way the game draws people (in the house in any
  body frame and head turn, on the Details screen, on an event screen, in the Family Tree); one who has left home
  or died is drawn only in the Family Tree, as the game does.
* "Make your own": any sex, age, head (hairstyle) and outfit, in any of those ways.
* Both tabs: in the house, any item a family member can carry (every cell of carrying.png and
  collectables_small.png, the ones the game never shows too, each labelled), in any body position.
* PNGs: clear, cut to the drawn pixels with a small margin (or none), at the game's size, 2x or 4x (crisp) or any
  width and height (smooth).

The pictures come from the game folder chosen in the window (the patcher's modded game, or the original); a
modded game with the patcher's expansion outfits is drawn with them (vf2_people_pictures). No game art ships with
the patcher. Nothing is ever written but the PNGs the player saves: the save and the game folder are only read.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import vf2_genealogy as gen
import vf2_people_pictures as pp
import vf2_picture_image as pi
import vf2_save_reader as reader

TITLE = "Picture Maker"
PREVIEW = 300                          # the preview area's side, in pixels
WIDTH, HEIGHT = 1100, 760
MIN_WIDTH, MIN_HEIGHT = 760, 520

HOUSE, DETAILS, EVENT, TREE, TRAY = "house", "details", "event", "tree", "tray"
VIEW_NAMES = {
    HOUSE: "In the house",
    DETAILS: "Details screen",
    EVENT: "Event screen",
    TREE: "Family Tree",
    TRAY: "Tool tray",
}
DEFAULT_FRAME = pp.EVENT_FRAME          # standing, facing out (the event screens' own frame)
DEFAULT_TURN = 5                        # the face looking straight out
AGES = [0, 1, 2, 3, 5, 8, 10, 12, 13, 14, 15, 17, 19, 20, 25, 30, 35, 40, 44, 45, 50, 55, 60, 70]
GROUPS = ("At home", "Left home", "Died", "In the Family Tree", "Tool tray")


# ------------------------------------------------------------------ what the save holds


@dataclass(frozen=True)
class SavedItem:
    id: str
    label: str
    group: str
    views: tuple
    person: pp.Person | None = None
    tray: pp.TrayOutfit | None = None
    detail: str = ""


def describe(person: pp.Person) -> str:
    years = person.age // pp.YEAR
    parts = [f"{pp.SEXES[person.sex]}, {years} year{'' if years == 1 else 's'} old ({pp.stage(person.age)})",
             f"head {person.head:02d} ({pp.hairstyle_name(person.sex, person.head)})",
             f"outfit {person.body:02d} ({pp.tier(person.body)})"]
    if person.babies:
        parts.append(f"expecting {person.babies} bab{'y' if person.babies == 1 else 'ies'}")
    return "; ".join(parts) + "."


NOT_CHECKED = "not checked against the game"


def notes(view: str, person: pp.Person | None, patched: bool, tray: pp.TrayOutfit | None = None,
          carrying: str | None = None) -> list[str]:
    """What the picture does not show of the game's screen, and what has not been checked against the running
    game's own drawing (said in the window and in the README)."""
    out = []
    item = pp.carried_item(carrying)
    if item is not None:
        if view == HOUSE:
            out.append(f"Carrying: {item.name}. {item.reason}")
        else:
            out.append(f"Carrying {item.name}: not drawn here; the game draws carried items only in the house.")
    if view == TREE:
        out.append("The Family Tree's own frame round the portrait is not drawn.")
    if view == HOUSE:
        out.append("Drawn as the house shows them at its normal zoom, standing on the floor.")
    if person is not None and person.body in pp.EXPANSION_BODIES and patched and view != TREE:
        out.append("The patcher's expansion outfit is placed as the patcher's own code places it "
                   f"({NOT_CHECKED} while it runs).")
    if tray is not None and tray.picture >= pp.ROWS:
        out.append(f"An expansion outfit's tray picture is drawn as the game's own code draws row 49 ({NOT_CHECKED}).")
    return out


def saved_items(folder: Path, slot: int) -> list[SavedItem]:
    """Everyone the save names, in family words, and the tool tray's outfits. Read only."""
    path = gen.save_path(folder, slot)
    data = path.read_bytes()
    save = reader.parse_family_save(data)
    family = gen.build_family(save, slot, data=data, sidecar=gen._sidecar(Path(folder), slot))
    items: list[SavedItem] = []
    seen_slots: set[int] = set()
    for person in sorted(family.people.values(), key=lambda p: (p.generation, p.birth_record or 0, p.id)):
        if person.upcoming:
            continue                                   # a baby on the way is drawn only in its mother's arms
        record = save.villagers[person.slot] if person.slot is not None and 0 <= person.slot < len(save.villagers) \
            else None
        if record is not None and record.active:
            seen_slots.add(person.slot)
            babies = record.babies_expected if record.pregnancy_mark and 1 <= record.babies_expected <= 3 else 0
            drawn = pp.Person(sex=1 if record.gender else 0, head=record.head, body=record.body,
                              age=max(0, record.age_units), babies=babies)
            name = record.name or person.name or "(no name)"
            if record.health > 0 and not record.left_home:
                group, views = "At home", (HOUSE, DETAILS, EVENT, TREE)
            elif record.left_home:
                group, views = "Left home", (TREE,)
            else:
                group, views = "Died", (TREE,)
            items.append(SavedItem(f"slot{person.slot}", name, group, views, drawn, detail=describe(drawn)))
            continue
        if person.head is None or person.body is None or person.sex not in ("Male", "Female"):
            continue
        drawn = pp.Person(sex=pp.FEMALE if person.sex == "Female" else pp.MALE, head=person.head, body=person.body,
                          age=person.age if person.age is not None else 400)
        why = "died" if person.gone == "died" else ("left home" if person.gone == "left" or person.left_home
                                                    else "no longer in the house")
        items.append(SavedItem(f"tree{person.id}", person.name or "(no name)", "In the Family Tree", (TREE,), drawn,
                               detail=f"{pp.SEXES[drawn.sex]}; {why}. The game draws them only in the Family Tree."))
    sidecar = None
    with contextlib.suppress(OSError):
        sidecar = pp.outfit_sidecar_path(folder, slot).read_bytes()
    for outfit in pp.tray_outfits(data, sidecar):
        sex = pp.SEXES[outfit.sex]
        whose = ("its own picture (the patcher's Outfit Pictures)" if outfit.own
                 else f"the last {sex.lower()} outfit bought, as the original game shows every {sex.lower()} outfit")
        items.append(SavedItem(f"tray{outfit.place}", f"{sex} Outfit, tray place {outfit.place + 1}", "Tool tray",
                               (TRAY,), tray=outfit,
                               detail=f"Outfit {outfit.picture:02d} ({pp.outfit_name(outfit.sex, outfit.picture)}): "
                                      f"{whose}."))
    order = {group: n for n, group in enumerate(GROUPS)}
    return sorted(items, key=lambda it: order.get(it.group, len(order)))     # stable: family order within a group


def render_item(art: pp.GameArt, item: SavedItem, view: str, *, frame: int = DEFAULT_FRAME,
                turn: int = DEFAULT_TURN, big_turn: int = 1, facing_you: bool = True, shadow: bool = True,
                patched: bool | None = None, carrying: str | None = None, position: int | None = None) -> pi.Image:
    """The picture of one saved item, in one of its views."""
    if view not in item.views:
        view = item.views[0]
    return pp.render(art, plan_for(item.person, view, frame=frame, turn=turn, big_turn=big_turn,
                                   facing_you=facing_you, shadow=shadow,
                                   patched=art.patched if patched is None else patched, tray=item.tray,
                                   carrying=carrying, position=position))


def plan_for(person: pp.Person | None, view: str, *, frame: int = DEFAULT_FRAME, turn: int = DEFAULT_TURN,
             big_turn: int = 1, facing_you: bool = True, shadow: bool = True, patched: bool = False,
             tray: pp.TrayOutfit | None = None, carrying: str | None = None, position: int | None = None) -> list:
    """The layers of one picture. `carrying` is a carried item's key (pp.carried_items) and `position` the body
    position (None: the one the game waits in for `frame`); both matter only in the house, the one place the game
    draws carried items."""
    if view == TRAY:
        return pp.tray_outfit_plan(tray.sex, tray.picture)
    if view == HOUSE:
        where = pp.default_position(frame) if position is None else int(position)
        return pp.house_plan(person, frame, turn, shadow=shadow, patched=patched,
                             carried=pp.carried_item(carrying), position=where)
    if view == DETAILS:
        return pp.details_plan(person, big_turn, patched=patched)
    if view == EVENT:
        return pp.event_plan(person, facing_you=facing_you, patched=patched)
    return pp.tree_plan(person)


# ------------------------------------------------------------------ Make your own


@dataclass(frozen=True)
class Choice:
    key: object
    label: str
    patcher: bool = False


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    options: tuple
    default: object = None


def custom_fields(patched: bool) -> list[Field]:
    """What Make your own offers: the game's every head, outfit and age, in every way it draws people; the
    patcher's expansion outfits only when the game folder has them."""
    bodies = [Choice(b, f"Outfit {b:02d}: {pp.tier(b)}") for b in range(pp.ROWS)]
    if patched:
        bodies += [Choice(b, f"Outfit {b:02d}: Holiday outfit {b - 49}", patcher=True) for b in pp.EXPANSION_BODIES]
    return [
        Field("sex", "Sex", (Choice(pp.FEMALE, "Female"), Choice(pp.MALE, "Male")), pp.FEMALE),
        Field("age", "Age", tuple(Choice(y * pp.YEAR, f"{y} year{'' if y == 1 else 's'} ({pp.stage(y * pp.YEAR)})")
                                  for y in AGES), 25 * pp.YEAR),
        Field("head", "Head and hairstyle", tuple(Choice(h, f"Head {h:02d}") for h in range(pp.ROWS)), 0),
        Field("body", "Outfit", tuple(bodies), 0),
        Field("view", "Drawn as", tuple(Choice(v, VIEW_NAMES[v]) for v in (HOUSE, DETAILS, EVENT, TREE)), HOUSE),
        Field("frame", "Body frame (in the house)", tuple(Choice(f, pp.FRAME_NAMES[f]) for f in range(56)),
              DEFAULT_FRAME),
        Field("turn", "Head turn (in the house)", tuple(Choice(t, pp.HEAD_NAMES[t]) for t in range(12)),
              DEFAULT_TURN),
        Field("big_turn", "Head turn (Details screen)", tuple(Choice(t, pp.HEAD_NAMES[12 + t]) for t in range(3)), 1),
        Field("facing", "Head (event screen)", (Choice(True, "Facing you"), Choice(False, "Turned")), True),
        Field("babies", "Babies on the way (in the house)",
              tuple(Choice(n, "None" if n == 0 else str(n)) for n in range(4)), 0),
        Field("carrying", "Carrying (in the house)", carrying_choices(), None),
        Field("position", "Body position (in the house)", position_choices(), None),
        Field("shadow", "Shadow (in the house)", (Choice(True, "Shown"), Choice(False, "Not shown")), True),
    ]


def carrying_choices() -> tuple:
    """Nothing, then every carried-item picture the game has, in sheet order, each named with its group; the ones
    the game never puts in a family member's hands say so."""
    return (Choice(None, "Nothing"),) + tuple(Choice(item.key, f"{item.group}: {item.label}")
                                              for item in pp.carried_items())


def position_choices() -> tuple:
    """"As the game waits in this frame", then body positions 0-23 with the frame each waits in and how much lower
    a carried item goes."""
    out = [Choice(None, "As the game waits in this frame")]
    for position, (frame, _direction) in enumerate(pp.body_positions()):
        where = pp.FRAME_NAMES[frame] if 0 <= frame < len(pp.FRAME_NAMES) else "no frame of its own"
        if 0 <= frame < 8:
            where = f"walking frame {frame + 1}, any direction"
        drop = pp.carry_drop(position)
        out.append(Choice(position, f"Position {position}: {where}" + (f"; item {drop} lower" if drop else "")))
    return tuple(out)


def person_from_spec(spec: dict) -> pp.Person:
    sex = pp.FEMALE if spec.get("sex", pp.FEMALE) else pp.MALE
    return pp.Person(sex=sex, head=int(spec.get("head", 0)), body=int(spec.get("body", 0)),
                     age=int(spec.get("age", 25 * pp.YEAR)), babies=int(spec.get("babies", 0) or 0))


def render_custom(art: pp.GameArt, spec: dict, patched: bool | None = None) -> pi.Image:
    person = person_from_spec(spec)
    return pp.render(art, plan_for(person, spec.get("view", HOUSE), frame=int(spec.get("frame", DEFAULT_FRAME)),
                                   turn=int(spec.get("turn", DEFAULT_TURN)), big_turn=int(spec.get("big_turn", 1)),
                                   facing_you=bool(spec.get("facing", True)), shadow=bool(spec.get("shadow", True)),
                                   patched=art.patched if patched is None else patched,
                                   carrying=spec.get("carrying"), position=spec.get("position")))


def custom_name(spec: dict) -> str:
    person = person_from_spec(spec)
    view = VIEW_NAMES.get(spec.get("view", HOUSE), "")
    item = pp.carried_item(spec.get("carrying")) if spec.get("view", HOUSE) == HOUSE else None
    holding = f", carrying {item.name}" if item is not None else ""
    return (f"{pp.SEXES[person.sex]}, {person.age // pp.YEAR} years, head {person.head:02d}, outfit "
            f"{person.body:02d}{holding} - {view}")


# ------------------------------------------------------------------ export choices


def export_options(size: str, width: str = "", height: str = "", margin: bool = True) -> dict:
    """The options for vf2_picture_image.export from the window's choices: "1x" / "2x" / "4x", or "custom" with
    a width and/or height in pixels."""
    options: dict = {"margin": pi.MARGIN if margin else 0}
    if size == "custom":
        def number(text: str) -> int:
            text = str(text or "").strip()
            if not text:
                return 0
            if not text.isdigit() or int(text) <= 0:
                raise pi.PictureError("A width or height is a whole number of pixels, 1 or more.")
            return int(text)
        options["size"] = (number(width), number(height))
    else:
        options["scale"] = dict(pi.SIZES).get(size, 1)
    return options


# ------------------------------------------------------------------ the window


def open_picture_maker(app, folders: list[Path], game_folder: str = "") -> "PictureMaker":
    """Open (or raise) the Picture Maker over the patcher window `app` (a VF2PatcherGUI)."""
    existing = getattr(app, "_picture_maker", None)
    if existing is not None:
        with contextlib.suppress(tk.TclError):
            if existing.window.winfo_exists():
                existing.window.deiconify()
                existing.window.lift()
                return existing
    maker = PictureMaker(getattr(app, "root", app), folders, game_folder)
    hold = getattr(app, "_hold", None)
    if hold is not None:
        hold(maker.window)
    app._picture_maker = maker
    return maker


class PictureMaker:
    def __init__(self, master: tk.Misc, folders: list[Path], game_folder: str = "") -> None:
        self.folders = list(folders)
        self.window = tk.Toplevel(master)
        self.window.title(TITLE)
        with contextlib.suppress(tk.TclError):
            self.window.transient(master)
        screen_w, screen_h = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        width, height = min(WIDTH, screen_w - 60), min(HEIGHT, screen_h - 110)
        self.window.geometry(f"{width}x{height}")
        self.window.minsize(min(MIN_WIDTH, width), min(MIN_HEIGHT, height))
        self.window.resizable(True, True)
        self.window.bind("<Escape>", lambda _e: self.close())
        self.folder_var = tk.StringVar(master=self.window)
        self.slot_var = tk.StringVar(master=self.window)
        self.game_var = tk.StringVar(master=self.window, value=game_folder)
        self.status_var = tk.StringVar(master=self.window)
        self.size_var = tk.StringVar(master=self.window, value="1x")
        self.width_var = tk.StringVar(master=self.window)
        self.height_var = tk.StringVar(master=self.window)
        self.margin_var = tk.BooleanVar(master=self.window, value=True)
        self.patched_var = tk.BooleanVar(master=self.window, value=True)
        self.art = pp.GameArt(None)
        self.items: list[SavedItem] = []
        self.item_nodes: dict[str, SavedItem] = {}
        self.group_nodes: dict[str, str] = {}
        self.slots: list[int] = []
        self.shown: dict[str, pi.Image] = {}
        self.custom_boxes: dict[str, dict] = {}
        self.carrying_options = carrying_choices()
        self.position_options = position_choices()
        self.quiet = False                            # tests: messages are kept, not shown
        self.last_message = ""
        self._build()
        self.game_var.trace_add("write", lambda *_a: self._game_changed())
        self._load_folders()
        self._game_changed()

    # ---- layout
    def _build(self) -> None:
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="Save folder:").pack(side="left")
        self.folder_box = ttk.Combobox(top, textvariable=self.folder_var, state="readonly", width=34)
        self.folder_box.pack(side="left", padx=(4, 12))
        self.folder_box.bind("<<ComboboxSelected>>", lambda _e: self._load_slots())
        ttk.Button(top, text="Other...", command=self.browse_saves).pack(side="left", padx=(0, 12))
        ttk.Label(top, text="Family:").pack(side="left")
        self.slot_box = ttk.Combobox(top, textvariable=self.slot_var, state="readonly", width=34)
        self.slot_box.pack(side="left", padx=(4, 12))
        self.slot_box.bind("<<ComboboxSelected>>", lambda _e: self._fill_save_list())
        ttk.Button(top, text="?", width=2, command=self.show_help).pack(side="right")
        game = ttk.Frame(outer)
        game.pack(fill="x", pady=(6, 0))
        ttk.Label(game, text="Game folder (for the pictures):").pack(side="left")
        ttk.Entry(game, textvariable=self.game_var, width=60).pack(side="left", padx=(4, 6), fill="x", expand=True)
        ttk.Button(game, text="Choose...", command=self.choose_game).pack(side="left")
        self.status = ttk.Label(outer, textvariable=self.status_var, foreground="#245a9a", wraplength=600,
                                justify="left")
        self.status.pack(anchor="w", pady=(6, 0))
        outer.bind("<Configure>", lambda e: self.status.configure(wraplength=max(300, e.width - 30)))

        options = ttk.LabelFrame(outer, text="Options", padding=(10, 4))
        options.pack(fill="x", pady=(6, 0))
        self.patched_check = ttk.Checkbutton(options, text="Patched look", variable=self.patched_var,
                                             command=self._refresh_pictures)
        self.patched_check.pack(side="left", padx=(0, 18))
        ttk.Label(options, text="PNG size:").pack(side="left")
        for label, value in (("Game size", "1x"), ("2x", "2x"), ("4x", "4x"), ("Custom:", "custom")):
            ttk.Radiobutton(options, text=label, value=value, variable=self.size_var).pack(side="left", padx=(4, 0))
        ttk.Entry(options, textvariable=self.width_var, width=6).pack(side="left", padx=(2, 0))
        ttk.Label(options, text="x").pack(side="left", padx=2)
        ttk.Entry(options, textvariable=self.height_var, width=6).pack(side="left")
        ttk.Label(options, text="px").pack(side="left", padx=(2, 12))
        ttk.Checkbutton(options, text="Small margin", variable=self.margin_var).pack(side="left")

        bottom = ttk.Frame(outer)
        bottom.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Close", command=self.close).pack(side="right")
        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True, pady=(8, 0))
        self._build_save_tab()
        self._build_custom_tab()

    def _scrolled(self, parent) -> ttk.Frame:
        """A frame with scroll bars both ways, for a pane that may not fit a small window."""
        holder = ttk.Frame(parent)
        canvas = tk.Canvas(holder, highlightthickness=0, borderwidth=0,
                           background=ttk.Style(self.window).lookup("TFrame", "background") or "#f0f0f0")
        ybar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        xbar = ttk.Scrollbar(holder, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        ybar.pack(side="right", fill="y")
        xbar.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(canvas, padding=(10, 0))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all"),
                                                               width=inner.winfo_reqwidth()))
        holder.inner = inner
        return holder

    def _preview_pane(self, parent) -> dict:
        canvas = tk.Canvas(parent, width=PREVIEW, height=PREVIEW, highlightthickness=1,
                           highlightbackground="#c0c0c0",
                           background=ttk.Style(self.window).lookup("TFrame", "background") or "#f0f0f0")
        canvas.pack(anchor="n")
        info = ttk.Label(parent, text="", wraplength=PREVIEW, justify="left")
        info.pack(anchor="w", pady=(6, 0))
        return {"canvas": canvas, "info": info}

    def _build_save_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="From my save")
        right = self._scrolled(tab)
        right.pack(side="right", fill="y")             # first, so the list gives way when the window is small
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        self.save_tree = ttk.Treeview(left, columns=("what",), show="tree headings", selectmode="browse")
        self.save_tree.heading("#0", text="In the save")
        self.save_tree.heading("what", text="Drawn")
        self.save_tree.column("#0", width=260)
        self.save_tree.column("what", width=150, stretch=False)
        yscroll = ttk.Scrollbar(left, orient="vertical", command=self.save_tree.yview)
        xscroll = ttk.Scrollbar(left, orient="horizontal", command=self.save_tree.xview)
        self.save_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        self.save_tree.pack(side="left", fill="both", expand=True)
        pane = right.inner
        self.save_preview = self._preview_pane(pane)
        ways = ttk.Frame(pane, padding=(0, 6))
        ways.pack(fill="x")
        self.save_controls = {}
        rows = (("view", "Drawn as:", []),
                ("frame", "Body frame:", [pp.FRAME_NAMES[f] for f in range(56)]),
                ("turn", "Head turn:", pp.HEAD_NAMES[:12]),
                ("big_turn", "Big head turn:", pp.HEAD_NAMES[12:]),
                ("facing", "Event head:", ["Facing you", "Turned"]),
                ("shadow", "Shadow:", ["Shown", "Not shown"]),
                ("carrying", "Carrying:", [c.label for c in self.carrying_options]),
                ("position", "Body position:", [c.label for c in self.position_options]))
        for row, (key, label, values) in enumerate(rows):
            ttk.Label(ways, text=label).grid(row=row, column=0, sticky="w", pady=2)
            box = ttk.Combobox(ways, state="readonly", width=44 if key in ("carrying", "position") else 30,
                               values=values)
            box.grid(row=row, column=1, sticky="w", padx=(4, 0), pady=2)
            box.bind("<<ComboboxSelected>>", lambda _e: self._show_saved())
            self.save_controls[key] = box
        self.save_controls["frame"].current(DEFAULT_FRAME)
        self.save_controls["turn"].current(DEFAULT_TURN)
        self.save_controls["big_turn"].current(1)
        self.save_controls["facing"].current(0)
        self.save_controls["shadow"].current(0)
        self.save_controls["carrying"].current(0)
        self.save_controls["position"].current(0)
        ttk.Label(ways, text="A save does not keep what anyone is carrying: pick it here. The game draws carried "
                             "items only in the house.", wraplength=320, justify="left", foreground="#555555").grid(
            row=len(rows), column=0, columnspan=2, sticky="w", pady=(4, 0))
        buttons = ttk.Frame(pane, padding=(0, 6))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Save PNG...", command=lambda: self.save_png("save")).pack(anchor="w")
        ttk.Button(buttons, text="Save all in this group...", command=self.save_all).pack(anchor="w", pady=(6, 0))
        self.save_tree.bind("<<TreeviewSelect>>", lambda _e: self._picked_saved())

    def _build_custom_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Make your own")
        right = ttk.Frame(tab, padding=(10, 0))
        right.pack(side="right", fill="y")             # first, so the choices give way when the window is small
        holder = self._scrolled(tab)
        holder.pack(side="left", fill="both", expand=True)
        self.custom_frame = holder.inner
        self.custom_preview = self._preview_pane(right)
        ttk.Button(right, text="Save PNG...", command=lambda: self.save_png("custom")).pack(anchor="w", pady=(6, 0))
        self._fill_custom()

    def close(self) -> None:
        with contextlib.suppress(tk.TclError):
            self.window.grab_release()
        if self.window.winfo_exists():
            self.window.destroy()

    def show_help(self) -> tk.Toplevel:
        import vf2_how_to_use
        guide = vf2_how_to_use.guide("picture_maker")
        window = tk.Toplevel(self.window)
        window.title(f"How to use: {guide.title}")
        window.transient(self.window)
        frame = ttk.Frame(window, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=guide.title, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))
        for line in guide.lines:
            ttk.Label(frame, text=line, wraplength=480, justify="left").pack(anchor="w", pady=(0, 6))
        ttk.Button(frame, text="Close", command=window.destroy).pack(anchor="e", pady=(8, 0))
        window.bind("<Escape>", lambda _e: window.destroy())
        return window

    # ---- the game folder
    def choose_game(self, chosen: str | None = None) -> None:
        if chosen is None:
            chosen = filedialog.askdirectory(parent=self.window, title="The game's folder (the one with Images in it)")
        if chosen:
            self.game_var.set(chosen)

    def _game_changed(self) -> None:
        text = self.game_var.get().strip()
        folder = Path(text) if text else None
        if folder is not None and folder.name.lower() == "images":
            folder = folder.parent
        self.art = pp.GameArt(folder)
        self._refresh_pictures()

    def look_patched(self) -> bool:
        return self.art.patched and bool(self.patched_var.get())

    def _status(self) -> None:
        words = []
        if self.current_slot() is not None:
            words.append(f"{self.folder_var.get()}, {self.slot_var.get()}.")
        else:
            words.append("No family chosen.")
        missing = self.art.missing()
        if self.art.folder is None:
            words.append("Choose the game folder: the pictures are drawn from its Images.")
        elif missing:
            words.append(f"{self.art.folder} is not a Virtual Families 2 game folder the pictures can come from "
                         f"(missing {', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}).")
        elif self.art.patched:
            words.append("Drawn from the patched game in " + str(self.art.folder)
                         + (": the patcher's expansion outfits are shown." if self.patched_var.get()
                            else ", with Patched look off: as the original game draws them."))
        else:
            words.append(f"Drawn from {self.art.folder}: the original game's pictures (no patcher outfits there).")
        self.status_var.set(" ".join(words))
        with contextlib.suppress(tk.TclError):
            self.patched_check.configure(state="normal" if self.art.patched else "disabled")

    def _refresh_pictures(self) -> None:
        self._status()
        with contextlib.suppress(tk.TclError):
            self._fill_custom()
            self._show_saved()

    # ---- the save
    def browse_saves(self, chosen: str | None = None) -> None:
        if chosen is None:
            chosen = filedialog.askdirectory(parent=self.window,
                                             title="A Virtual Families 2 save folder (Documents\\LDW\\...)")
        if chosen:
            self.folders.append(Path(chosen))
            self.folder_box.configure(values=[f.name for f in self.folders])
            self.folder_box.current(len(self.folders) - 1)
            self._load_slots()

    def _load_folders(self) -> None:
        self.folder_box.configure(values=[f.name for f in self.folders])
        if self.folders:
            modded = [i for i, f in enumerate(self.folders) if f.name != gen.GAME_TITLE]
            self.folder_box.current(modded[0] if modded else 0)
        self._load_slots()

    def current_folder(self) -> Path | None:
        index = self.folder_box.current()
        return self.folders[index] if 0 <= index < len(self.folders) else None

    def _load_slots(self) -> None:
        self.slots, labels = [], []
        folder = self.current_folder()
        if folder is not None:
            for slot in range(1, 6):
                path = gen.save_path(folder, slot)
                if not path.is_file():
                    continue
                try:
                    save = reader.read_family_save(path)
                except (OSError, reader.SaveFormatError, ValueError, IndexError):
                    continue
                self.slots.append(slot)
                labels.append(f"Save {slot}: {save.nickname or 'Family'}")
        self.slot_box.configure(values=labels)
        if labels:
            self.slot_box.current(0)
        else:
            self.slot_var.set("")
        self._fill_save_list()

    def current_slot(self) -> int | None:
        index = self.slot_box.current()
        return self.slots[index] if 0 <= index < len(self.slots) else None

    def _fill_save_list(self) -> None:
        tree = self.save_tree
        tree.delete(*tree.get_children())
        self.items, self.item_nodes, self.group_nodes = [], {}, {}
        self._status()
        folder, slot = self.current_folder(), self.current_slot()
        info = self.save_preview["info"]
        self.save_preview["canvas"].delete("all")
        self.shown.pop("save", None)
        if folder is None or slot is None:
            info.configure(text="Pick a save folder and a family to see who is in it.", foreground="")
            return
        try:
            self.items = saved_items(folder, slot)
        except (OSError, reader.SaveFormatError, ValueError, IndexError) as exc:
            info.configure(text=f"The save could not be read: {exc}", foreground="#a01010")
            return
        for item in self.items:
            parent = self.group_nodes.get(item.group)
            if parent is None:
                parent = tree.insert("", "end", text=item.group, open=True)
                self.group_nodes[item.group] = parent
            node = tree.insert(parent, "end", text=item.label,
                               values=(", ".join(VIEW_NAMES[v] for v in item.views[:2])
                                       + ("..." if len(item.views) > 2 else ""),))
            self.item_nodes[node] = item
        if not self.items:
            info.configure(text="Nobody is in this save yet.", foreground="")
        else:
            info.configure(text="Click someone to see them as the game draws them.", foreground="")

    def selected_item(self) -> SavedItem | None:
        selection = self.save_tree.selection()
        return self.item_nodes.get(selection[0]) if selection else None

    def _picked_saved(self) -> None:
        item = self.selected_item()
        box = self.save_controls["view"]
        if item is None:
            box.configure(values=[])
            return
        box.configure(values=[VIEW_NAMES[v] for v in item.views])
        box.current(0)
        self._show_saved()

    def saved_view(self, item: SavedItem) -> str:
        index = self.save_controls["view"].current()
        return item.views[index] if 0 <= index < len(item.views) else item.views[0]

    def saved_options(self) -> dict:
        c = self.save_controls
        return {"frame": max(0, c["frame"].current()), "turn": max(0, c["turn"].current()),
                "big_turn": max(0, c["big_turn"].current()), "facing_you": c["facing"].current() != 1,
                "shadow": c["shadow"].current() != 1,
                "carrying": self.carrying_options[max(0, c["carrying"].current())].key,
                "position": self.position_options[max(0, c["position"].current())].key}

    def render_saved(self, item: SavedItem, view: str | None = None) -> pi.Image:
        return render_item(self.art, item, view or self.saved_view(item), patched=self.look_patched(),
                           **self.saved_options())

    def _show_saved(self) -> None:
        item = self.selected_item()
        if item is None:
            return
        if not self.art.present():
            self._show(self.save_preview, None, "Choose the game folder first: the pictures come from it.")
            return
        try:
            image = self.render_saved(item)
        except (OSError, pi.PictureError, KeyError, ValueError) as exc:
            self.shown.pop("save", None)
            self._show(self.save_preview, None, f"{item.label}: this cannot be drawn ({exc}).")
            return
        self.shown["save"] = image
        said = notes(self.saved_view(item), item.person, self.look_patched(), item.tray,
                     self.saved_options()["carrying"] if item.person is not None else None)
        self._show(self.save_preview, image, " ".join([f"{item.label}: {item.detail}"] + said))

    def _show(self, preview: dict, image: pi.Image | None, text: str) -> None:
        canvas = preview["canvas"]
        canvas.delete("all")
        preview["info"].configure(text=text, foreground="")
        if image is None:
            return
        shown = image.cropped(pi.MARGIN)
        biggest = max(shown.width, shown.height, 1)
        if biggest <= PREVIEW:
            factor = max(1, min(4, PREVIEW // biggest))
            photo = shown.photo(tk, self.window)
            if factor > 1:
                photo = photo.zoom(factor)
        else:
            photo = shown.photo(tk, self.window, max_side=PREVIEW)
        canvas.create_image(PREVIEW // 2, PREVIEW // 2, image=photo)
        canvas.photo = photo

    # ---- Make your own
    def _fill_custom(self) -> None:
        frame = self.custom_frame
        picks = {key: box["box"].get() for key, box in self.custom_boxes.items()}
        for child in frame.winfo_children():
            child.destroy()
        self.custom_boxes = {}
        for row, fld in enumerate(custom_fields(self.look_patched())):
            ttk.Label(frame, text=f"{fld.label}:").grid(row=row, column=0, sticky="w", pady=3)
            labels = [o.label + ("  (patcher)" if o.patcher else "") for o in fld.options]
            box = ttk.Combobox(frame, values=labels, state="readonly", width=52)
            box.grid(row=row, column=1, sticky="w", padx=(6, 0), pady=3)
            keep = picks.get(fld.key)
            if keep in labels:
                box.current(labels.index(keep))
            else:
                keys = [o.key for o in fld.options]
                box.current(keys.index(fld.default) if fld.default in keys else 0)
            box.bind("<<ComboboxSelected>>", lambda _e: self._show_custom())
            self.custom_boxes[fld.key] = {"box": box, "field": fld}
        ttk.Label(frame, text="Heads 00-49 are the game's 50 faces and hairstyles of each sex (the patcher's store "
                              "sells all 100 as hairstyles). From 45 years a head is drawn old, and below 14 years "
                              "the body and head are drawn smaller every age unit, as the game does. Every "
                              "carried-item picture the game has can be carried, the ones the game never puts in "
                              "a family member's hands too (they say so); the game draws carried items only in the "
                              "house, at their own size, held lower in some sitting and lying positions.",
                  wraplength=520, justify="left", foreground="#555555").grid(
            row=len(self.custom_boxes), column=0, columnspan=2, sticky="w", pady=(10, 0))
        self._show_custom()

    def custom_spec(self) -> dict:
        spec = {}
        for key, box in self.custom_boxes.items():
            index = box["box"].current()
            options = box["field"].options
            spec[key] = options[index].key if 0 <= index < len(options) else box["field"].default
        return spec

    def _show_custom(self) -> None:
        if not self.custom_boxes:
            return
        if not self.art.present():
            self.shown.pop("custom", None)
            self._show(self.custom_preview, None, "Choose the game folder first: the pictures come from it.")
            return
        spec = self.custom_spec()
        try:
            image = render_custom(self.art, spec, patched=self.look_patched())
        except (OSError, pi.PictureError, KeyError, ValueError) as exc:
            self.shown.pop("custom", None)
            self._show(self.custom_preview, None, f"This cannot be drawn: {exc}")
            return
        self.shown["custom"] = image
        person = person_from_spec(spec)
        said = notes(spec.get("view", HOUSE), person, self.look_patched(), carrying=spec.get("carrying"))
        self._show(self.custom_preview, image, " ".join([describe(person)] + said))

    # ---- saving
    def export_choice(self) -> dict:
        return export_options(self.size_var.get(), self.width_var.get(), self.height_var.get(), self.margin_var.get())

    def picture_name(self, which: str) -> str:
        if which == "save":
            item = self.selected_item()
            if item is None:
                return "picture"
            view = self.saved_view(item)
            held = pp.carried_item(self.saved_options()["carrying"]) if view == HOUSE else None
            return pi.safe_file_name(f"{item.label}{f' carrying {held.name}' if held else ''} - {VIEW_NAMES[view]}")
        return pi.safe_file_name(custom_name(self.custom_spec()))

    def save_png(self, which: str, path: str | None = None) -> Path | None:
        image = self.shown.get(which)
        if image is None:
            self._tell("info", "Pick a picture first.")
            return None
        try:
            options = self.export_choice()
        except pi.PictureError as exc:
            self._tell("warning", str(exc))
            return None
        if path is None:
            path = filedialog.asksaveasfilename(parent=self.window, title="Save PNG", defaultextension=".png",
                                                initialfile=self.picture_name(which) + ".png",
                                                filetypes=[("PNG picture", "*.png")])
        if not path:
            return None
        try:
            return pi.save_png(image, path, **options)
        except (OSError, pi.PictureError) as exc:
            self._tell("warning", f"The picture could not be saved: {exc}")
            return None

    def save_all(self, folder: str | None = None) -> Path | None:
        item = self.selected_item()
        selection = self.save_tree.selection()
        group = item.group if item is not None else (self.save_tree.item(selection[0], "text") if selection else None)
        if group is None:
            self._tell("info", "Pick a group (or anyone in it) first.")
            return None
        try:
            options = self.export_choice()
        except pi.PictureError as exc:
            self._tell("warning", str(exc))
            return None
        if folder is None:
            folder = filedialog.askdirectory(parent=self.window, title="Save the pictures in...")
        if not folder:
            return None
        family = self.slot_var.get().split(": ", 1)[-1] if self.current_slot() is not None else "Family"
        base = pi.safe_file_name(f"{family} - {group}")
        target, n = Path(folder) / base, 2
        while target.exists():
            target, n = Path(folder) / f"{base} ({n})", n + 1
        try:
            target.mkdir(parents=True)
        except OSError as exc:
            self._tell("warning", f"The folder could not be made: {exc}")
            return None
        saved, failed = 0, []
        for each in self.items:
            if each.group != group:
                continue
            view = self.saved_view(each) if each is item else each.views[0]
            try:
                image = self.render_saved(each, view)
                pi.save_png(image, pi.unique_path(target, pi.safe_file_name(f"{each.label} - {VIEW_NAMES[view]}")),
                            **options)
                saved += 1
            except (OSError, pi.PictureError, KeyError, ValueError) as exc:
                failed.append(f"{each.label}: {exc}")
        text = f"{saved} picture(s) saved in {target}."
        if failed:
            text += "\nNot saved:\n" + "\n".join(failed[:10])
        self._tell("info", text)
        return target

    def _tell(self, kind: str, text: str) -> None:
        self.last_message = text
        if not self.quiet:
            (messagebox.showwarning if kind == "warning" else messagebox.showinfo)(TITLE, text, parent=self.window)
