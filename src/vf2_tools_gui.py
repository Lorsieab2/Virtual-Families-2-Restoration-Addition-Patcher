"""The Tools tab: Back Up Saves, Restore Saves, Rename Family, Game Speed, Game Mechanics, the Family Tree Maker
(vf2_family_tree_window, its family read by vf2_genealogy) and the guide.

A mixin for VF2PatcherGUI (offline_vf2_patcher_gui.py), kept in its own file so the window's patching code
stays as it was.  It needs from the window: ``root``, ``status_var``, ``notebook``, ``_run_with_wait`` and the
``Link.TLabel`` / ``LinkHover.TLabel`` styles.  The saves themselves are handled by vf2_save_backup,
vf2_rename_family and vf2_game_speed (no Tk there); Game Mechanics is a read-only window of text
(vf2_game_mechanics_window, its lines in vf2_game_mechanics); the guides live in vf2_how_to_use.json.

The tab and every tool window follow the Virtual Villagers Fun Patcher's (src/vv_fun_patcher_gui.py), as the
Virtual Families 1 patcher's do: the same layout, titles, headings, wording, buttons, waits and result windows, with
this game's own family wording.
"""
from __future__ import annotations

import contextlib
import json
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import vf2_game_mechanics_window
import vf2_game_speed
import vf2_how_to_use
import vf2_rename_family
import vf2_save_backup
from vf2_tree_editor_tools import scrollable_frame

TOOLS_TITLE = "Virtual Families 2 Restoration/Addition Patcher"
# The Tools tab's box: the game its tools work on (the Virtual Villagers patcher's box names its game).
TOOLS_GAME_TITLE = vf2_save_backup.GAME_TITLE
WRAP = 640
# The Family Tree Maker's remembered look and window, beside the patcher (its own file: the window's
# patcher_local_settings.json keeps only its folders and drops any other key when it saves them).
TREE_SETTINGS_FILE = "family_tree_settings.json"


def tree_settings_path() -> Path:
    return Path(__file__).resolve().parent / TREE_SETTINGS_FILE


def load_tree_settings(path: Path | None = None) -> dict:
    """{"style": ..., "window": ...}, or {} when there is none or it does not read."""
    try:
        data = json.loads((path or tree_settings_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_tree_settings(style: dict | None, window: dict | None, path: Path | None = None) -> None:
    (path or tree_settings_path()).write_text(
        json.dumps({"style": style or {}, "window": window or {}}, indent=2) + "\n", encoding="utf-8")


class ToolsTabMixin:
    """Everything the Tools tab does.  ``self`` is the VF2PatcherGUI window."""

    def _init_tools(self) -> None:
        self.help_keys: set[str] = set()
        self._help_windows: dict[str, tk.Toplevel] = {}
        self.saves_found_var = tk.StringVar(value="")

    # -- widgets ------------------------------------------------------------

    def _link(self, parent: tk.Widget, text: str, command) -> ttk.Label:
        """A clickable, underlined link label in the window's link style."""
        link = ttk.Label(parent, text=text, style="Link.TLabel", cursor="hand2")
        link.bind("<Button-1>", lambda _event: command())
        link.bind("<Enter>", lambda _event: link.configure(style="LinkHover.TLabel"))
        link.bind("<Leave>", lambda _event: link.configure(style="Link.TLabel"))
        return link

    def _help_button(self, parent: tk.Widget, key: str) -> ttk.Button:
        """A small "?" button that opens the brief guide for one control.

        A key with no guide fails here, while the window is built, never later on a click.
        """
        vf2_how_to_use.guide(key)
        self.help_keys.add(key)
        return ttk.Button(parent, text="?", width=2, command=lambda: self._show_how_to_use(key))

    def _scrolling_dialog(self, title: str) -> tuple[tk.Toplevel, ttk.Frame]:
        """A dialog whose content scrolls once it is taller than the screen."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        return dialog, scrollable_frame(dialog, padding=16)

    def _center_dialog(self, window: tk.Toplevel) -> None:
        window.update_idletasks()
        try:
            viewable = bool(self.root.winfo_viewable())
        except tk.TclError:
            viewable = False
        width, height = window.winfo_reqwidth(), window.winfo_reqheight()
        if viewable:
            x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        else:
            x = max(0, (window.winfo_screenwidth() - width) // 2)
            y = max(0, (window.winfo_screenheight() - height) // 2)
        window.geometry(f"+{x}+{y}")

    def _hold(self, dialog: tk.Toplevel, focus: tk.Widget | None = None) -> None:
        """Hold the patcher behind a dialog (the main window stays inert while it is open).  The dialog opens where
        Windows puts a new window, as the Virtual Villagers patcher's do: a wide one centred on the patcher would
        start off the left of the screen."""
        dialog.update_idletasks()
        with contextlib.suppress(tk.TclError):
            dialog.grab_set()
        with contextlib.suppress(tk.TclError):
            (focus or dialog).focus_set()

    # -- the tab ------------------------------------------------------------

    def _build_tools_tab(self, tab: ttk.Frame) -> None:
        """Laid out as the Virtual Villagers Fun Patcher's Tools tab: one box for the game, the save folders found in
        blue, the save tools in one row of links and the family and game tools in the next, each link with its "?";
        then the guide."""
        box = ttk.LabelFrame(tab, text=TOOLS_GAME_TITLE, padding=10)
        box.pack(fill="x")
        ttk.Label(box, textvariable=self.saves_found_var, foreground="#245a9a", wraplength=760,
                  justify="left").grid(row=0, column=0, sticky="w")
        links = ttk.Frame(box)
        links.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._link(links, "Back Up Saves", self.back_up_saves).pack(side="left")
        self._help_button(links, "back_up_saves").pack(side="left", padx=(3, 0))
        self._link(links, "Restore Saves...", self.restore_saves).pack(side="left", padx=(18, 0))
        self._help_button(links, "restore_saves").pack(side="left", padx=(3, 0))
        self._link(links, "Rename Family...", self.rename_family).pack(side="left", padx=(18, 0))
        self._help_button(links, "rename_family").pack(side="left", padx=(3, 0))
        self._link(links, "Game Speed...", self.game_speed).pack(side="left", padx=(18, 0))
        self._help_button(links, "game_speed").pack(side="left", padx=(3, 0))
        family = ttk.Frame(box)
        family.grid(row=2, column=0, sticky="w", pady=(6, 0))
        self._link(family, "Family Tree Maker...", self.open_family_tree).pack(side="left")
        self._help_button(family, "family_tree").pack(side="left", padx=(3, 0))
        self._link(family, "Game Mechanics...", self.game_mechanics).pack(side="left", padx=(18, 0))
        self._help_button(family, "game_mechanics").pack(side="left", padx=(3, 0))

        guide = ttk.LabelFrame(tab, text="How to Use", padding=10)
        guide.pack(fill="x", pady=(10, 0))
        row = ttk.Frame(guide)
        row.pack(anchor="w")
        self._link(row, "How to Use...", self.show_how_to_use_guide).pack(side="left")
        self._help_button(row, "how_to_use").pack(side="left", padx=(3, 0))
        # The save folders found are read again whenever the tab is shown, as the Virtual Villagers patcher's
        # game line is always current.
        self.notebook.bind("<<NotebookTabChanged>>", lambda _event: self._refresh_saves_found(), add="+")
        self._refresh_saves_found()

    def _refresh_saves_found(self) -> None:
        documents = vf2_save_backup.documents_folder()
        folders = vf2_save_backup.find_save_folders(documents) if documents is not None else []
        if documents is None:
            text = "Windows did not report where your Documents folder is, so the save folders cannot be found."
        elif not folders:
            text = (f"No {TOOLS_GAME_TITLE} save folders were found in {documents / 'LDW'}. The game makes its save "
                    "folder the first time it is played.")
        else:
            text = "Save folders found: " + ", ".join(folder.name for folder in folders)
        self.saves_found_var.set(text)

    # -- Family Tree Maker ---------------------------------------------------

    def open_family_tree(self) -> tk.Toplevel | None:
        """The Family Tree Maker (vf2_family_tree_window): choose a save folder and a family, then the editor."""
        import vf2_family_tree_window as tree_window
        saved = load_tree_settings()
        if not hasattr(self, "tree_style"):
            self.tree_style = saved.get("style") or None
        if not hasattr(self, "tree_window"):
            self.tree_window = saved.get("window") or {}
        folders = vf2_save_backup.find_save_folders(vf2_save_backup.documents_folder())
        return tree_window.open_family_tree(self, folders=folders)

    def _save_settings(self) -> None:
        """The Family Tree Maker's look and window, remembered for the next tree (its own settings file)."""
        with contextlib.suppress(OSError, TypeError, ValueError):
            save_tree_settings(getattr(self, "tree_style", None), getattr(self, "tree_window", None))

    # -- Game Mechanics -----------------------------------------------------

    def game_mechanics(self) -> tk.Toplevel:
        """The read-only Game Mechanics window (one at a time: a second click brings it to the front)."""
        existing = getattr(self, "_game_mechanics_window", None)
        if existing is not None:
            with contextlib.suppress(tk.TclError):
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    return existing
        window = vf2_game_mechanics_window.open_game_mechanics(self.root)
        self._game_mechanics_window = window
        return window

    # -- How to Use ---------------------------------------------------------

    def _show_how_to_use(self, key: str) -> tk.Toplevel:
        """The small "How to use" window for one control."""
        window = self._help_windows.get(key)
        if window is not None and window.winfo_exists():
            window.deiconify()
            window.lift()
            window.focus_set()
            return window
        guide = vf2_how_to_use.guide(key)
        window = tk.Toplevel(self.root)
        window.title(f"How to use: {guide.title}")
        window.transient(self.root)
        window.resizable(False, False)
        frame = scrollable_frame(window, padding=16)
        ttk.Label(frame, text=guide.title, font=("Segoe UI", 11, "bold"), wraplength=480, justify="left").pack(
            anchor="w", pady=(0, 8))
        for line in guide.lines:
            ttk.Label(frame, text=line, wraplength=480, justify="left").pack(anchor="w", pady=(0, 6))
        close = ttk.Button(frame, text="Close", command=window.destroy)
        close.pack(anchor="e", pady=(8, 0))
        window.bind("<Escape>", lambda _event: window.destroy())
        self._center_dialog(window)
        with contextlib.suppress(tk.TclError):
            close.focus_set()
        self._help_windows[key] = window
        return window

    def show_how_to_use_guide(self) -> tk.Toplevel:
        """The full guide: a list of every topic and the page of the one chosen."""
        existing = self._help_windows.get("*guide")
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            return existing
        window = tk.Toplevel(self.root)
        window.title("How to Use")
        window.transient(self.root)
        window.geometry("820x520")
        window.columnconfigure(1, weight=1)
        window.rowconfigure(0, weight=1)
        keys = vf2_how_to_use.keys()
        topics = tk.Listbox(window, width=30, exportselection=False)
        topics.grid(row=0, column=0, sticky="ns", padx=(12, 6), pady=12)
        last_section = None
        index_of: dict[int, str] = {}
        for key in keys:
            sect = vf2_how_to_use.section(key)
            if sect != last_section:
                last_section = sect
                topics.insert("end", f"-- {sect} --")
                topics.itemconfigure("end", foreground="#555555")
            topics.insert("end", "  " + vf2_how_to_use.control_title(key))
            index_of[topics.size() - 1] = key
        page = tk.Text(window, wrap="word", state="disabled", padx=10, pady=8, font=("Segoe UI", 10))   # as VF1
        page.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        page.tag_configure("title", font=("Segoe UI", 12, "bold"), spacing3=8)
        page.tag_configure("line", spacing3=8)

        def show(key: str) -> None:
            guide = vf2_how_to_use.guide(key)
            page.configure(state="normal")
            page.delete("1.0", "end")
            page.insert("end", guide.title + "\n", "title")
            for line in guide.lines:
                page.insert("end", line + "\n", "line")
            page.configure(state="disabled")

        def picked(_event=None) -> None:
            chosen = topics.curselection()
            if chosen and chosen[0] in index_of:
                show(index_of[chosen[0]])

        topics.bind("<<ListboxSelect>>", picked)
        first = min(index_of)
        topics.selection_set(first)
        show(index_of[first])
        ttk.Button(window, text="Close", command=window.destroy).grid(row=1, column=0, columnspan=2, sticky="e", padx=12, pady=(0, 12))
        window.bind("<Escape>", lambda _event: window.destroy())
        self._help_windows["*guide"] = window
        window._vf2_topics = topics
        window._vf2_page = page
        return window

    # -- Back Up Saves ------------------------------------------------------

    def _tool_save_folders(self, title: str) -> list[Path] | None:
        """Every Virtual Families 2 save folder, or None (after telling the player) if Documents is unknown."""
        documents = vf2_save_backup.documents_folder()
        if documents is None:
            messagebox.showerror(
                title,
                "Windows did not report where your Documents folder is, so the save folders cannot be found.",
            )
            return None
        return vf2_save_backup.find_save_folders(documents)

    def back_up_saves(self) -> tk.Toplevel | None:
        """Let the player pick save folders, then pause each game that is running and copy."""
        folders = self._tool_save_folders("Back Up Saves")
        if folders is None:
            return None
        if not folders:
            messagebox.showinfo(
                "Back Up Saves",
                f"No {TOOLS_GAME_TITLE} save folders were found in your Documents\\LDW folder.\n\n"
                "The game makes its save folder the first time it is played.",
            )
            return None
        return self._show_backup_chooser(folders)

    def _show_backup_chooser(self, folders: list[Path]) -> tk.Toplevel:
        dialog, frame = self._scrolling_dialog("Back Up Saves")
        ttk.Label(frame, text="Choose the save folders to back up:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Each folder is copied into a new dated folder inside it: <save folder>\\Backups\\Backup <date and "
                f"time>, with the patcher's own files for each save ({vf2_save_backup.DATA_FOLDER}). If the game is "
                "running it is paused for the copy and then resumes by itself. This game saves when you quit normally "
                "and by itself every 2 minutes while running, so a backup made while the game is running holds your "
                "families as of its last save; quit the game normally first to be sure the latest state is backed up."
            ),
            wraplength=WRAP, justify="left",
        ).pack(anchor="w", pady=(4, 10))
        ttk.Label(frame, text=TOOLS_GAME_TITLE).pack(anchor="w", pady=(6, 0))
        choices: list[tuple[Path, tk.BooleanVar]] = []
        for folder in folders:
            label = folder.name
            if vf2_save_backup.running_game_count(folder):
                label += "   (running: will be paused for the copy)"
            var = tk.BooleanVar(value=vf2_save_backup.is_patcher_save_folder(folder.name))
            ttk.Checkbutton(frame, text=label, variable=var).pack(anchor="w", padx=(14, 0))
            choices.append((folder, var))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))

        def start() -> None:
            chosen = [folder for folder, var in choices if var.get()]
            if not chosen:
                messagebox.showinfo("Back Up Saves", "Tick at least one save folder.", parent=dialog)
                return
            dialog.destroy()
            self._run_backups(chosen)

        ttk.Button(buttons, text="Back Up Selected", command=start).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=(8, 0))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog._vf2_choices = choices
        dialog._vf2_start = start
        self._hold(dialog)
        return dialog

    def _run_backups(self, folders: list[Path]) -> list:
        def work():
            outcomes = []
            for folder in folders:
                try:
                    outcomes.append((folder, vf2_save_backup.back_up_save_folder(folder), None))
                except (vf2_save_backup.BackupError, OSError) as exc:
                    outcomes.append((folder, None, str(exc)))
            return outcomes

        outcomes = self._run_with_wait("Backing up saves…\n\nA running game is paused for the copy.", work)
        made = sum(1 for _folder, result, _error in outcomes if result is not None)
        self.status_var.set(f"Back Up Saves: {made} of {len(outcomes)} save folder(s) backed up.")
        self._show_backup_results(outcomes)
        return outcomes

    def _show_backup_results(self, outcomes) -> tk.Toplevel:
        dialog, frame = self._scrolling_dialog("Back Up Saves")
        for folder, result, error in outcomes:
            ttk.Label(frame, text=folder.name, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(8, 0))
            if result is None:
                ttk.Label(frame, text=f"NOT backed up: {error}", wraplength=WRAP, justify="left", foreground="#a01010").pack(
                    anchor="w", padx=(14, 0)
                )
                continue
            lines = [
                f"Backed up {result.file_count} file(s), {vf2_save_backup.describe_size(result.total_bytes)}; every copy "
                "was checked against the original (size and SHA-256).",
                f"Backup folder: {result.backup_folder}",
            ]
            if result.paused:
                lines.append(
                    "The game was running: it was paused for the copy and has resumed. The backup holds your families "
                    "as of the game's last save (it saves by itself every 2 minutes, and when you quit normally)."
                )
            else:
                lines.append("The game was not running.")
            ttk.Label(frame, text="\n".join(lines), wraplength=WRAP, justify="left").pack(anchor="w", padx=(14, 0))
            if result.resume_problems:
                ttk.Label(
                    frame,
                    text=(
                        "The backup is complete, but the game could not be resumed: "
                        + "; ".join(result.resume_problems)
                        + ". If it stays frozen, close it from Task Manager; the backup above is safe."
                    ),
                    wraplength=WRAP, justify="left", foreground="#a01010",
                ).pack(anchor="w", padx=(14, 0))
            self._link(
                frame, "Open Backup Folder", lambda path=result.backup_folder: self._open_folder(path)
            ).pack(anchor="w", padx=(14, 0), pady=(2, 0))
        ttk.Button(frame, text="Close", command=dialog.destroy).pack(pady=(16, 0))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self._hold(dialog)
        return dialog

    def _open_folder(self, path: Path) -> None:
        """Open a folder (a file's own folder) in Explorer, or say it is not there."""
        target = Path(path).expanduser()
        if target.is_file():
            target = target.parent
        if not target.is_dir():
            self.status_var.set(f"Folder not found: {target}")
            messagebox.showerror("Cannot open folder", self.status_var.get())
            return
        try:
            subprocess.Popen(["explorer", str(target)])
        except Exception as exc:
            messagebox.showerror(TOOLS_TITLE, f"Could not open:\n{target}\n\n{exc}")

    # -- Restore Saves ------------------------------------------------------

    def restore_saves(self) -> tk.Toplevel | None:
        """List the backups of every save folder so the player can restore or delete one."""
        folders = self._tool_save_folders("Restore Saves")
        if folders is None:
            return None
        if not any(vf2_save_backup.list_backups(folder) for folder in folders):
            messagebox.showinfo(
                "Restore Saves", f"There are no backups of {TOOLS_GAME_TITLE} yet.\n\nUse Back Up Saves to make one."
            )
            return None
        return self._show_restore_window(folders)

    @staticmethod
    def _backup_families(info) -> dict[int, str]:
        """Each slot the backup holds, with the family's name in the backup's own save."""
        names = {slot.slot: slot.name for slot in vf2_rename_family.read_slots(Path(info.path))}
        return {slot: vf2_rename_family.shown(names.get(slot)) for slot in info.slots}

    def _show_restore_window(self, folders: list[Path]) -> tk.Toplevel:
        dialog, frame = self._scrolling_dialog("Restore Saves")
        ttk.Label(frame, text="Choose a backup to restore:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Newest first. The game must be closed: quit it from its own menu before restoring. Your saves as they "
                "are now are backed up first, as \"Backup <date> (before restore)\", so a restore can be undone."
            ),
            wraplength=700, justify="left",
        ).pack(anchor="w", pady=(4, 8))
        listbox = tk.Listbox(frame, width=110, height=12, exportselection=False)
        listbox.pack(fill="both", expand=True)
        details = ttk.Label(frame, text="", wraplength=700, justify="left")
        details.pack(anchor="w", pady=(6, 0))
        scope = tk.StringVar(value="whole")
        slot_choice = tk.StringVar()
        options = ttk.Frame(frame)
        options.pack(anchor="w", pady=(8, 0))
        ttk.Radiobutton(options, text="The whole save folder", value="whole", variable=scope).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(options, text="One save slot only:", value="slot", variable=scope).grid(row=1, column=0, sticky="w")
        slots = ttk.Combobox(options, textvariable=slot_choice, state="readonly", width=50)
        slots.grid(row=1, column=1, sticky="w", padx=(8, 0))
        entries: list[tuple[Path, vf2_save_backup.BackupInfo, dict[int, str]]] = []

        def describe(folder: Path, info, families: dict[int, str]) -> str:
            held = ", ".join(f"Save {slot}: {name}" for slot, name in families.items()) or "no family saves"
            variant = folder.name.removeprefix(TOOLS_GAME_TITLE + " - ")
            return (
                f"{info.label}   [{variant}]   {held}   "
                f"{info.file_count} files, {vf2_save_backup.describe_size(info.size)}"
            )

        def refresh() -> None:
            entries.clear()
            listbox.delete(0, "end")
            listed = [(folder, info) for folder in folders for info in vf2_save_backup.list_backups(folder)]
            listed.sort(key=lambda item: item[1].when, reverse=True)
            for folder, info in listed:
                families = self._backup_families(info)
                entries.append((folder, info, families))
                listbox.insert("end", describe(folder, info, families))
            if entries:
                listbox.selection_set(0)
            selected()

        def current():
            chosen = listbox.curselection()
            return entries[chosen[0]] if chosen else None

        def selected(_event=None) -> None:
            item = current()
            if item is None:
                details.configure(text="")
                slots.configure(values=[])
                slot_choice.set("")
                return
            _folder, info, families = item
            details.configure(text=f"Backup folder: {info.path}")
            values = [f"Save {slot}: {name}" for slot, name in families.items()]
            slots.configure(values=values)
            slot_choice.set(values[0] if values else "")

        def chosen_slot():
            """None = the whole folder; False = a slot was asked for but the backup holds none."""
            if scope.get() != "slot":
                return None
            text = slot_choice.get()
            if not text.startswith("Save "):
                return False
            return int(text.split(":", 1)[0].removeprefix("Save "))

        def restore() -> None:
            item = current()
            if item is None:
                return
            slot = chosen_slot()
            if slot is False:
                messagebox.showinfo("Restore Saves", "This backup holds no family save to choose.", parent=dialog)
                return
            self._run_restore(dialog, item[0], item[1], slot)
            # The "Please wait" window held the patcher and let it go on closing; hold it again, so the main
            # window stays inert behind this one, as it was before the restore.
            if dialog.winfo_exists():
                with contextlib.suppress(tk.TclError):
                    dialog.grab_set()
                refresh()

        def delete() -> None:
            item = current()
            if item is None:
                return
            folder, info, families = item
            if not messagebox.askyesno(
                "Delete Backup",
                f"Delete this backup permanently?\n\n{describe(folder, info, families)}\n\n{info.path}\n\n"
                "Your current saves are not affected.",
                parent=dialog,
            ):
                return
            try:
                vf2_save_backup.delete_backup(folder, info.path)
            except (vf2_save_backup.BackupError, OSError) as exc:
                messagebox.showerror("Delete Backup", str(exc), parent=dialog)
            refresh()

        listbox.bind("<<ListboxSelect>>", selected)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Restore...", command=restore).pack(side="left")
        ttk.Button(buttons, text="Delete Backup...", command=delete).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="left", padx=(8, 0))
        refresh()
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog._vf2_listbox = listbox
        dialog._vf2_entries = entries
        dialog._vf2_scope = scope
        dialog._vf2_slot_choice = slot_choice
        dialog._vf2_restore = restore
        self._hold(dialog)
        return dialog

    def _run_restore(self, parent, folder: Path, info, slot) -> bool:
        """Show exactly what will change, ask, then restore with the game closed.  True when it was restored."""
        if vf2_save_backup.running_game_count(folder):
            messagebox.showerror(
                "Restore Saves",
                f"{vf2_save_backup.running_game_names(folder, None)} is running.\n\nQuit the game from its own menu first, then "
                "restore: a running game writes its families over the restored save the next time it saves (by itself "
                "every 2 minutes, or when it quits). Nothing was changed.",
                parent=parent,
            )
            return False
        try:
            # Hashes both copies of every file, which can take a while: off the main thread, behind the wait.
            plan = self._run_with_wait(
                "Checking the backup…", lambda: vf2_save_backup.plan_restore(folder, info.path, slot)
            )
        except (vf2_save_backup.BackupError, OSError) as exc:
            messagebox.showerror("Restore Saves", str(exc), parent=parent)
            return False
        if plan.changes == 0:
            messagebox.showinfo(
                "Restore Saves", "Your saves already match this backup; there is nothing to restore.", parent=parent
            )
            return False
        what = "the whole save folder" if slot is None else f"Save {slot} only"
        lines = (
            [f"Replace: {path}" for path in plan.replace]
            + [f"Add: {path}" for path in plan.add]
            + [f"Remove: {path}" for path in plan.remove]
        )
        shown = "\n".join(lines[:20])
        if len(lines) > 20:
            shown += f"\n... and {len(lines) - 20} more"
        if not messagebox.askyesno(
            "Restore Saves",
            f"Restore {what} of {folder.name} from the backup of {info.label}?\n\n"
            f"{len(plan.replace)} file(s) will be replaced, {len(plan.add)} added and {len(plan.remove)} removed:\n\n"
            f"{shown}\n\nYour saves as they are now are backed up first, so this can be undone.",
            parent=parent,
        ):
            return False
        try:
            result = self._run_with_wait(
                "Restoring saves…", lambda: vf2_save_backup.restore_backup(folder, info.path, slot)
            )
        except (vf2_save_backup.BackupError, OSError) as exc:
            self.status_var.set("Restore Saves: the restore did not complete.")
            messagebox.showerror("Restore Saves", str(exc), parent=parent)
            return False
        undo = (
            f"\n\nYour saves from before the restore are in:\n{result.before_restore.backup_folder}"
            if result.before_restore
            else ""
        )
        self.status_var.set(f"Restore Saves: {folder.name} restored from {info.label}.")
        messagebox.showinfo(
            "Restore Saves",
            f"Restored {what} from the backup of {info.label}: every file was checked against the backup.{undo}",
            parent=parent,
        )
        return True

    # -- Rename Family ------------------------------------------------------

    def rename_family(self) -> tk.Toplevel | None:
        """Pick a save folder and a family, then type the new name (the Virtual Villagers patcher's Rename Tribe).

        The family list is read from the saves and is only for choosing; the counter and every refusal come from
        vf2_rename_family.  The rename itself runs off the main thread."""
        folders = self._tool_save_folders("Rename Family")
        if folders is None:
            return None
        folders = [folder for folder in folders
                   if any(s.problem is None for s in vf2_rename_family.read_slots(folder))]
        if not folders:
            messagebox.showinfo(
                "Rename Family",
                f"No {TOOLS_GAME_TITLE} family saves were found in your Documents\\LDW folder.\n\n"
                "The game makes a family's save the first time it saves that family.",
            )
            return None
        return self._show_rename_dialog(folders)

    def _show_rename_dialog(self, folders: list[Path]) -> tk.Toplevel:
        dialog, frame = self._scrolling_dialog("Rename Family")
        ttk.Label(
            frame,
            text=(
                "Virtual Families 2 has no family surname: a family is shown under the player name typed when it was "
                "started (on the main menu and in Change Player). This changes that name inside its save. The game "
                "must be closed: it saves by itself every 2 minutes and when you quit it, which would put the old name back. The save folder is "
                "backed up first, into <save folder>\\Backups\\Backup <date and time> (before rename), and the "
                "family's Family History log gets one line noting the new name."
            ),
            wraplength=560, justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        folder_var = tk.StringVar()
        name_var = tk.StringVar()
        counter_var = tk.StringVar()
        problem_var = tk.StringVar()
        state: dict = {"slots": []}

        ttk.Label(frame, text="Save folder:").grid(row=1, column=0, sticky="w")
        folder_box = ttk.Combobox(frame, textvariable=folder_var, values=[folder.name for folder in folders],
                                  state="readonly", width=48)
        folder_box.grid(row=1, column=1, columnspan=2, sticky="we", pady=2)
        ttk.Label(frame, text="Family:").grid(row=2, column=0, sticky="nw", pady=(4, 0))
        slot_list = tk.Listbox(frame, height=5, width=60, exportselection=False)
        slot_list.grid(row=2, column=1, columnspan=2, sticky="we", pady=(4, 2))
        ttk.Label(frame, text="New name:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        name_entry = ttk.Entry(frame, textvariable=name_var, width=36)
        name_entry.grid(row=3, column=1, sticky="w", pady=(8, 0))
        counter = ttk.Label(frame, textvariable=counter_var)
        counter.grid(row=3, column=2, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Label(frame, textvariable=problem_var, foreground="#a01010", wraplength=560, justify="left").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=3, sticky="w", pady=(12, 0))
        rename_button = ttk.Button(buttons, text="Rename")
        rename_button.pack(side="left")
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="left", padx=(8, 0))

        def folder() -> Path | None:
            index = folder_box.current()
            return folders[index] if 0 <= index < len(folders) else None

        def chosen_slot():
            picked = slot_list.curselection()
            return state["slots"][picked[0]] if picked else None

        def refresh_check(*_args) -> None:
            name = name_var.get()
            counter_var.set(f"{len(name)} / {vf2_rename_family.MAX_LENGTH} characters")
            counter.configure(foreground="#a01010" if len(name) > vf2_rename_family.MAX_LENGTH else "")
            info = chosen_slot()
            problem = None
            if folder() is None:
                problem = "No save folder was found for this game."
            elif info is None:
                problem = "Choose a family."
            elif info.problem:
                problem = info.problem
            elif name:
                problem = vf2_rename_family.name_problem(name)
                if problem is None and name == vf2_rename_family.shown(info.name):
                    problem = "That is already this family's name."
            problem_var.set(problem or "")
            ok = problem is None and bool(name)
            rename_button.configure(state="normal" if ok else "disabled")

        def load_slots(*_args) -> None:
            slot_list.delete(0, "end")
            state["slots"] = []
            where = folder()
            if where is not None:
                state["slots"] = vf2_rename_family.read_slots(where)
                for info in state["slots"]:
                    slot_list.insert("end", info.label)
                first = next((n for n, info in enumerate(state["slots"]) if not info.problem), None)
                if first is not None:
                    slot_list.selection_set(first)
            refresh_check()

        def start() -> None:
            info = chosen_slot()
            where = folder()
            if info is None or where is None:
                return
            new_name = name_var.get()
            problem = vf2_rename_family.name_problem(new_name)
            if problem is not None:
                messagebox.showerror("Rename Family", problem, parent=dialog)
                return
            if not messagebox.askyesno(
                "Rename Family",
                f"Rename \"{vf2_rename_family.shown(info.name)}\" (Save {info.slot}) in {where.name} to "
                f"\"{new_name}\"?\n\nThe save folder is backed up first.",
                parent=dialog,
            ):
                return
            try:
                result = self._run_with_wait(
                    "Renaming the family…\n\nThe save folder is backed up first.",
                    lambda: vf2_rename_family.rename_family(where, info.slot, new_name),
                )
            except (vf2_rename_family.RenameError, vf2_save_backup.BackupError, OSError) as exc:
                self.status_var.set("Rename Family: nothing was renamed.")
                messagebox.showerror("Rename Family", str(exc), parent=dialog)
                load_slots()
                return
            self.status_var.set(f"Rename Family: {result.old_name} is now {result.new_name}.")
            messagebox.showinfo(
                "Rename Family",
                f"\"{result.old_name}\" is now \"{result.new_name}\" (Save {result.slot}, {where.name}).\n\n"
                f"{len(result.changed)} save file(s) changed and read back; {len(result.notes)} log(s) noted the "
                f"rename.\n\nBackup: {result.backup.backup_folder}",
                parent=dialog,
            )
            name_var.set("")
            load_slots()

        def choose(index: int) -> None:          # a click on a family (the tests)
            slot_list.selection_clear(0, "end")
            slot_list.selection_set(index)
            refresh_check()

        rename_button.configure(command=start)
        folder_box.bind("<<ComboboxSelected>>", load_slots)
        slot_list.bind("<<ListboxSelect>>", refresh_check)
        name_var.trace_add("write", refresh_check)
        frame.columnconfigure(1, weight=1)
        folder_box.current(0)
        load_slots()
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog._vf2_folder_box = folder_box
        dialog._vf2_folder_var = folder_var        # kept: a dropped StringVar empties its box
        dialog._vf2_slot_list = slot_list
        dialog._vf2_name_var = name_var
        dialog._vf2_counter_var = counter_var
        dialog._vf2_problem_var = problem_var
        dialog._vf2_rename_button = rename_button
        dialog._vf2_start = start
        dialog._vf2_choose = choose
        self._hold(dialog, focus=name_entry)
        return dialog

    # -- Game Speed ---------------------------------------------------------

    def game_speed(self) -> tk.Toplevel | None:
        """Pick a save folder and a family, then Paused or Normal, written into the closed game's save (laid out as
        Rename Family)."""
        folders = self._tool_save_folders("Game Speed")
        if folders is None:
            return None
        folders = [folder for folder in folders
                   if any(s.state is not None for s in vf2_game_speed.read_slots(folder))]
        if not folders:
            messagebox.showinfo(
                "Game Speed",
                f"No {TOOLS_GAME_TITLE} family saves were found in your Documents\\LDW folder.\n\n"
                "The game makes a family's save the first time it saves that family.",
            )
            return None
        return self._show_speed_dialog(folders)

    def _show_speed_dialog(self, folders: list[Path]) -> tk.Toplevel:
        dialog, frame = self._scrolling_dialog("Game Speed")
        ttk.Label(
            frame,
            text=(
                "Sets a family's game speed inside its save. The game must be closed: it saves by itself every 2 minutes and when you quit it, which "
                "would put the old speed back. The save folder is backed up first, into <save folder>\\Backups\\Backup "
                "<date and time> (before speed change). Paused works as if you paused just before the game last saved; "
                "Normal as if you unpaused it now, so the paused time is never aged in."
            ),
            wraplength=560, justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        folder_var = tk.StringVar()
        target_var = tk.StringVar(value="")
        problem_var = tk.StringVar()
        state: dict = {"slots": []}

        ttk.Label(frame, text="Save folder:").grid(row=1, column=0, sticky="w")
        folder_box = ttk.Combobox(frame, textvariable=folder_var, values=[folder.name for folder in folders],
                                  state="readonly", width=48)
        folder_box.grid(row=1, column=1, columnspan=2, sticky="we", pady=2)
        ttk.Label(frame, text="Family:").grid(row=2, column=0, sticky="nw", pady=(4, 0))
        slot_list = tk.Listbox(frame, height=5, width=60, exportselection=False)
        slot_list.grid(row=2, column=1, columnspan=2, sticky="we", pady=(4, 2))
        ttk.Label(frame, text="New speed:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        targets = ttk.Frame(frame)
        targets.grid(row=3, column=1, columnspan=2, sticky="w", pady=(8, 0))
        for name in vf2_game_speed.TARGETS:
            ttk.Radiobutton(targets, text=name, value=name, variable=target_var).pack(side="left", padx=(0, 14))
        ttk.Label(frame, textvariable=problem_var, foreground="#a01010", wraplength=560, justify="left").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=3, sticky="w", pady=(12, 0))
        set_button = ttk.Button(buttons, text="Set Speed")
        set_button.pack(side="left")
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="left", padx=(8, 0))

        def folder() -> Path | None:
            index = folder_box.current()
            return folders[index] if 0 <= index < len(folders) else None

        def chosen_slot():
            picked = slot_list.curselection()
            return state["slots"][picked[0]] if picked else None

        def check(*_args) -> None:
            info = chosen_slot()
            target = target_var.get()
            if folder() is None:
                problem = "No save folder was found for this game."
            elif info is None or info.state is None:
                problem = info.problem if info is not None and info.problem else "Choose a family."
            elif info.problem:
                problem = info.problem
            elif not target:
                problem = "Choose Paused or Normal."
            elif info.state.label == target:
                problem = f"This family is {target} already."
            else:
                problem = ""
            problem_var.set(problem)
            set_button.configure(state="disabled" if problem else "normal")

        def picked(*_args) -> None:
            info = chosen_slot()
            if info is not None and info.state is not None and info.problem is None:
                target_var.set(vf2_game_speed.NORMAL_NAME if info.state.kind == "paused" else vf2_game_speed.PAUSED)
            check()

        def load_slots(*_args) -> None:
            slot_list.delete(0, "end")
            state["slots"] = []
            where = folder()
            if where is not None:
                state["slots"] = vf2_game_speed.read_slots(where)
                for info in state["slots"]:
                    slot_list.insert("end", info.label)
                first = next((n for n, info in enumerate(state["slots"])
                              if info.state is not None and not info.problem), None)
                if first is not None:
                    slot_list.selection_set(first)
            picked()

        def start() -> None:
            info = chosen_slot()
            where = folder()
            target = target_var.get()
            check()
            if info is None or where is None or problem_var.get():
                return
            name = vf2_rename_family.shown(info.name)
            if not messagebox.askyesno(
                "Game Speed",
                f"Set \"{name}\" (Save {info.slot}) in {where.name} from {info.state.label} to {target}?\n\n"
                "The save folder is backed up first.",
                parent=dialog,
            ):
                return
            try:
                result = self._run_with_wait(
                    "Setting the game speed…\n\nThe save folder is backed up first.",
                    lambda: vf2_game_speed.set_speed(where, info.slot, target),
                )
            except (vf2_game_speed.SpeedError, vf2_save_backup.BackupError, OSError) as exc:
                self.status_var.set("Game Speed: nothing was changed.")
                messagebox.showerror("Game Speed", str(exc), parent=dialog)
                load_slots()
                return
            self.status_var.set(f"Game Speed: Save {info.slot} is now {result.after}.")
            messagebox.showinfo(
                "Game Speed",
                f"\"{name}\" is now {result.after} (Save {info.slot}, {where.name}); it was {result.before}.\n\n"
                f"The save was changed and read back.\n\nBackup: {result.backup.backup_folder}",
                parent=dialog,
            )
            load_slots()

        def choose(index: int) -> None:          # a click on a family (the tests)
            slot_list.selection_clear(0, "end")
            slot_list.selection_set(index)
            picked()

        set_button.configure(command=start)
        folder_box.bind("<<ComboboxSelected>>", load_slots)
        slot_list.bind("<<ListboxSelect>>", picked)
        target_var.trace_add("write", check)
        frame.columnconfigure(1, weight=1)
        folder_box.current(0)
        load_slots()
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog._vf2_folder_box = folder_box
        dialog._vf2_folder_var = folder_var        # kept: a dropped StringVar empties its box
        dialog._vf2_slot_list = slot_list
        dialog._vf2_target_var = target_var
        dialog._vf2_problem_var = problem_var
        dialog._vf2_set_button = set_button
        dialog._vf2_start = start
        dialog._vf2_choose = choose
        self._hold(dialog)
        return dialog
