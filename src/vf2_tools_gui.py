"""The Tools tab: Back Up Saves, Restore Saves, Rename Family, Game Speed, Game Mechanics and the guide.

A mixin for VF2PatcherGUI (offline_vf2_patcher_gui.py), kept in its own file so the window's patching code
stays as it was.  It needs from the window: ``root``, ``status_var``, ``_run_with_wait`` and the
``Link.TLabel`` / ``LinkHover.TLabel`` styles.  The saves themselves are handled by vf2_save_backup,
vf2_rename_family and vf2_game_speed (no Tk there); Game Mechanics is a read-only window of text
(vf2_game_mechanics_window, its lines in vf2_game_mechanics); the guides live in vf2_how_to_use.json.
"""
from __future__ import annotations

import contextlib
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import vf2_game_mechanics_window
import vf2_game_speed
import vf2_how_to_use
import vf2_rename_family
import vf2_save_backup

TOOLS_TITLE = "Virtual Families 2 Restoration/Addition Patcher"
WRAP = 640


class ToolsTabMixin:
    """Everything the Tools tab does.  ``self`` is the VF2PatcherGUI window."""

    def _init_tools(self) -> None:
        self.help_keys: set[str] = set()
        self._help_windows: dict[str, tk.Toplevel] = {}

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

    def _scrolling_dialog(self, title: str, modal: bool = True) -> tuple[tk.Toplevel, ttk.Frame]:
        """A dialog whose content scrolls once it is taller than the screen."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        outer = ttk.Frame(dialog)
        outer.pack(fill="both", expand=True)
        max_height = max(300, int(dialog.winfo_screenheight() * 0.7))
        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0, height=10)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        frame = ttk.Frame(canvas, padding=16)
        window = canvas.create_window((0, 0), window=frame, anchor="nw")

        def resize(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            needed = frame.winfo_reqheight()
            canvas.configure(height=min(needed, max_height), width=frame.winfo_reqwidth())
            if needed > max_height:
                scrollbar.pack(side="right", fill="y")
            else:
                scrollbar.pack_forget()

        frame.bind("<Configure>", resize)
        canvas.pack(side="left", fill="both", expand=True)
        dialog._vf2_modal = modal
        dialog._vf2_window = window
        return dialog, frame

    def _hold(self, dialog: tk.Toplevel) -> None:
        """Keep the main window inert behind a dialog (best effort: a grab can fail on an unmapped window)."""
        dialog.update_idletasks()
        with contextlib.suppress(tk.TclError):
            dialog.grab_set()
        with contextlib.suppress(tk.TclError):
            dialog.focus_set()

    # -- the tab ------------------------------------------------------------

    def _build_tools_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(0, weight=1)
        saves = ttk.LabelFrame(tab, text="Saves", style="Section.TLabelframe", padding=10)
        saves.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            saves,
            text=(
                "Your families live in Documents\\LDW\\<game folder name>. Back Up Saves copies them (and the "
                "patcher's own files beside them) into a Backups folder in there; Restore Saves brings one back. "
                "Rename Family changes the name a family slot is shown under; Game Speed pauses or unpauses a family."
            ),
            style="Muted.TLabel", wraplength=WRAP, justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row = ttk.Frame(saves)
        row.grid(row=1, column=0, sticky="w")
        self._link(row, "Back Up Saves...", self.back_up_saves).pack(side="left")
        self._help_button(row, "back_up_saves").pack(side="left", padx=(3, 0))
        self._link(row, "Restore Saves...", self.restore_saves).pack(side="left", padx=(24, 0))
        self._help_button(row, "restore_saves").pack(side="left", padx=(3, 0))
        self._link(row, "Rename Family...", self.rename_family).pack(side="left", padx=(24, 0))
        self._help_button(row, "rename_family").pack(side="left", padx=(3, 0))
        self._link(row, "Game Speed...", self.game_speed).pack(side="left", padx=(24, 0))
        self._help_button(row, "game_speed").pack(side="left", padx=(3, 0))

        game = ttk.LabelFrame(tab, text="Game", style="Section.TLabelframe", padding=10)
        game.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        row = ttk.Frame(game)
        row.grid(row=0, column=0, sticky="w")
        self._link(row, "Game Mechanics...", self.game_mechanics).pack(side="left")
        self._help_button(row, "game_mechanics").pack(side="left", padx=(3, 0))
        ttk.Label(
            game,
            text="How the game works underneath: ageing, needs, illness, careers, money, events and their chances "
                 "and timers, in real time. It only shows text and changes nothing.",
            style="Muted.TLabel", wraplength=WRAP, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        guide = ttk.LabelFrame(tab, text="Help", style="Section.TLabelframe", padding=10)
        guide.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        row = ttk.Frame(guide)
        row.grid(row=0, column=0, sticky="w")
        self._link(row, "How to Use...", self.show_how_to_use_guide).pack(side="left")
        self._help_button(row, "how_to_use").pack(side="left", padx=(3, 0))
        ttk.Label(
            guide,
            text="Every button in the patcher, one short page each. The small ? buttons open the page for the control beside them.",
            style="Muted.TLabel", wraplength=WRAP, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

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
        frame = ttk.Frame(window, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=guide.title, font=("", 11, "bold"), wraplength=480, justify="left").pack(anchor="w", pady=(0, 8))
        for line in guide.lines:
            ttk.Label(frame, text=line, wraplength=480, justify="left").pack(anchor="w", pady=(0, 6))
        close = ttk.Button(frame, text="Close", command=window.destroy)
        close.pack(anchor="e", pady=(8, 0))
        window.bind("<Escape>", lambda _event: window.destroy())
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
        shown = ""
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
        page = tk.Text(window, wrap="word", state="disabled", padx=10, pady=8)
        page.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        page.tag_configure("title", font=("", 12, "bold"), spacing3=8)
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

    def _tool_save_folders(self) -> list[Path] | None:
        """Every Virtual Families 2 save folder, or None (after telling the player) if Documents is unknown."""
        documents = vf2_save_backup.documents_folder()
        if documents is None:
            messagebox.showerror(
                "Saves",
                "Windows did not report where your Documents folder is, so the save folders cannot be found.",
            )
            return None
        return vf2_save_backup.find_save_folders(documents)

    def back_up_saves(self) -> tk.Toplevel | None:
        """Let the player pick save folders, then pause each game that is running and copy."""
        folders = self._tool_save_folders()
        if folders is None:
            return None
        if not folders:
            messagebox.showinfo(
                "Back Up Saves",
                "No Virtual Families 2 save folders were found in your Documents\\LDW folder.\n\n"
                "The game makes its save folder the first time it is played.",
            )
            return None
        return self._show_backup_chooser(folders)

    def _show_backup_chooser(self, folders: list[Path]) -> tk.Toplevel:
        dialog, frame = self._scrolling_dialog("Back Up Saves")
        ttk.Label(frame, text="Choose the save folders to back up:", font=("", 10, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Each folder is copied into a new dated folder inside it: <save folder>\\Backups\\Backup <date and time>. "
                "The patcher's own files (Virtual Families 2 Patcher Data) are copied too. If the game is running it is "
                "paused for the copy and then resumes by itself. The game saves only when you quit normally, so a backup "
                "of a running game holds your families as of its last save."
            ),
            wraplength=WRAP, justify="left",
        ).pack(anchor="w", pady=(4, 10))
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

        outcomes = self._run_with_wait("Backing up saves...\n\nA running game is paused for the copy.", work)
        made = sum(1 for _folder, result, _error in outcomes if result is not None)
        self.status_var.set(f"Back Up Saves: {made} of {len(outcomes)} save folder(s) backed up.")
        self._show_backup_results(outcomes)
        return outcomes

    def _show_backup_results(self, outcomes) -> tk.Toplevel:
        dialog, frame = self._scrolling_dialog("Back Up Saves")
        for folder, result, error in outcomes:
            ttk.Label(frame, text=folder.name, font=("", 10, "bold")).pack(anchor="w", pady=(8, 0))
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
                    "as of the game's last save (it saves when you quit normally)."
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
        target = Path(path)
        if target.is_file():
            target = target.parent
        try:
            subprocess.Popen(["explorer", str(target)])
        except Exception as exc:
            messagebox.showerror(TOOLS_TITLE, f"Could not open:\n{target}\n\n{exc}")

    # -- Restore Saves ------------------------------------------------------

    def restore_saves(self) -> tk.Toplevel | None:
        """List the backups of every save folder so the player can restore or delete one."""
        folders = self._tool_save_folders()
        if folders is None:
            return None
        if not any(vf2_save_backup.list_backups(folder) for folder in folders):
            messagebox.showinfo(
                "Restore Saves", "There are no save backups yet.\n\nUse Back Up Saves to make one."
            )
            return None
        return self._show_restore_window(folders)

    @staticmethod
    def _slot_text(slot: int) -> str:
        return f"Family slot {slot} (Virtual Families 2{slot}.ldw)"

    def _show_restore_window(self, folders: list[Path]) -> tk.Toplevel:
        dialog = tk.Toplevel(self.root)
        dialog.title("Restore Saves")
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Choose a backup to restore:", font=("", 10, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Newest first. The game must be closed: quit it from its own menu before restoring. You will see exactly "
                "which files change and must say yes first. Your saves as they are now are backed up first, as "
                "\"Backup <date> (before restore)\", so a restore can be undone."
            ),
            wraplength=700, justify="left",
        ).pack(anchor="w", pady=(4, 8))
        listbox = tk.Listbox(frame, width=100, height=12, exportselection=False)
        listbox.pack(fill="both", expand=True)
        details = ttk.Label(frame, text="", wraplength=700, justify="left")
        details.pack(anchor="w", pady=(6, 0))
        scope = tk.StringVar(value="whole")
        slot_choice = tk.StringVar()
        options = ttk.Frame(frame)
        options.pack(anchor="w", pady=(8, 0))
        ttk.Radiobutton(options, text="The whole save folder", value="whole", variable=scope).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(options, text="One family slot only:", value="slot", variable=scope).grid(row=1, column=0, sticky="w")
        slots = ttk.Combobox(options, textvariable=slot_choice, state="readonly", width=44)
        slots.grid(row=1, column=1, sticky="w", padx=(8, 0))
        entries: list[tuple[Path, vf2_save_backup.BackupInfo]] = []

        def describe(folder: Path, info) -> str:
            held = ", ".join(str(slot) for slot in info.slots) or "none"
            return (
                f"{info.label}   [{folder.name}]   family slots: {held}   "
                f"{info.file_count} files, {vf2_save_backup.describe_size(info.size)}"
            )

        def refresh() -> None:
            entries.clear()
            listbox.delete(0, "end")
            listed = [(folder, info) for folder in folders for info in vf2_save_backup.list_backups(folder)]
            listed.sort(key=lambda item: item[1].when, reverse=True)
            for folder, info in listed:
                entries.append((folder, info))
                listbox.insert("end", describe(folder, info))
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
            _folder, info = item
            details.configure(text=f"Backup folder: {info.path}")
            values = [self._slot_text(slot) for slot in info.slots]
            slots.configure(values=values)
            slot_choice.set(values[0] if values else "")

        def chosen_slot():
            """None = the whole folder; False = a slot was asked for but the backup holds none."""
            if scope.get() != "slot":
                return None
            text = slot_choice.get()
            if not text.startswith("Family slot "):
                return False
            return int(text.split(" ")[2])

        def restore() -> None:
            item = current()
            if item is None:
                return
            slot = chosen_slot()
            if slot is False:
                messagebox.showinfo("Restore Saves", "This backup holds no family slot to choose.", parent=dialog)
                return
            self._run_restore(dialog, item[0], item[1], slot)
            if dialog.winfo_exists():
                self._hold(dialog)
                refresh()

        def delete() -> None:
            item = current()
            if item is None:
                return
            folder, info = item
            if not messagebox.askyesno(
                "Delete Backup",
                f"Delete this backup permanently?\n\n{describe(folder, info)}\n\n{info.path}\n\n"
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
        self._hold(dialog)
        return dialog

    def _run_restore(self, parent, folder: Path, info, slot) -> bool:
        """Show exactly what will change, ask, then restore with the game closed.  True when it was restored."""
        if vf2_save_backup.running_game_count(folder):
            messagebox.showerror(
                "Restore Saves",
                f"{vf2_save_backup.running_game_names(folder, None)} is running.\n\nQuit the game from its own menu first, then "
                "restore: a running game writes its families over the restored save when it quits. Nothing was changed.",
                parent=parent,
            )
            return False
        try:
            plan = self._run_with_wait(
                "Checking the backup...", lambda: vf2_save_backup.plan_restore(folder, info.path, slot)
            )
        except (vf2_save_backup.BackupError, OSError) as exc:
            messagebox.showerror("Restore Saves", str(exc), parent=parent)
            return False
        if plan.changes == 0:
            messagebox.showinfo(
                "Restore Saves", "Your saves already match this backup; there is nothing to restore.", parent=parent
            )
            return False
        what = "the whole save folder" if slot is None else f"family slot {slot} only"
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
                "Restoring saves...", lambda: vf2_save_backup.restore_backup(folder, info.path, slot)
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
        """Let the player pick a family slot and a new name, then rename it in the closed game's saves."""
        folders = self._tool_save_folders()
        if folders is None:
            return None
        folders = [folder for folder in folders
                   if any(s.problem is None for s in vf2_rename_family.read_slots(folder))]
        if not folders:
            messagebox.showinfo(
                "Rename Family",
                "No Virtual Families 2 family saves were found in your Documents\\LDW folder.\n\n"
                "The game makes a family's save the first time it saves that family.",
            )
            return None
        return self._show_rename_dialog(folders)

    def _show_rename_dialog(self, folders: list[Path]) -> tk.Toplevel:
        dialog, frame = self._scrolling_dialog("Rename Family")
        ttk.Label(frame, text="Rename a family:", font=("", 10, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Virtual Families 2 has no family surname: a family slot is shown under the player name typed when it "
                "was started (on the main menu and in Change Player). This changes that name. Quit the game from its "
                "own menu first: a running game would put the old name back. Your saves are backed up first, as "
                "\"Backup <date> (before rename)\"."
            ),
            wraplength=WRAP, justify="left",
        ).pack(anchor="w", pady=(4, 10))
        by_name = {folder.name: folder for folder in folders}
        folder_var = tk.StringVar(value=folders[0].name)
        if len(folders) > 1:
            row = ttk.Frame(frame)
            row.pack(anchor="w", pady=(0, 6))
            ttk.Label(row, text="Save folder").pack(side="left", padx=(0, 8))
            ttk.Combobox(row, textvariable=folder_var, values=list(by_name), state="readonly", width=48).pack(side="left")
        slot_var = tk.IntVar(value=0)
        slots_box = ttk.Frame(frame)
        slots_box.pack(anchor="w", pady=(0, 6))
        name_var = tk.StringVar()
        problem_var = tk.StringVar()
        slots: dict[int, vf2_rename_family.SlotInfo] = {}

        def fill_slots(*_args) -> None:
            for child in slots_box.winfo_children():
                child.destroy()
            slots.clear()
            first = 0
            for info in vf2_rename_family.read_slots(by_name[folder_var.get()]):
                slots[info.slot] = info
                usable = info.problem is None
                ttk.Radiobutton(slots_box, text=info.label, value=info.slot, variable=slot_var,
                                state="normal" if usable else "disabled").pack(anchor="w")
                if usable and not first:
                    first = info.slot
            slot_var.set(first)

        def picked(*_args) -> None:
            info = slots.get(slot_var.get())
            name_var.set(vf2_rename_family.shown(info.name) if info is not None and info.name else "")

        def check(*_args) -> None:
            name = name_var.get()
            info = slots.get(slot_var.get())
            problem = vf2_rename_family.name_problem(name)
            if problem is None and info is not None and info.name == name.encode("ascii"):
                problem = "That is the family's name already."
            problem_var.set(problem or "")

        ttk.Label(frame, text=f"New name (up to {vf2_rename_family.MAX_LENGTH} characters)").pack(anchor="w")
        entry = ttk.Entry(frame, textvariable=name_var, width=40)
        entry.pack(anchor="w", pady=(2, 0))
        ttk.Label(frame, textvariable=problem_var, foreground="#a01010", wraplength=WRAP, justify="left").pack(
            anchor="w", pady=(2, 0))
        name_var.trace_add("write", check)
        slot_var.trace_add("write", picked)
        folder_var.trace_add("write", fill_slots)
        fill_slots()
        check()
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))

        def start() -> None:
            folder = by_name[folder_var.get()]
            slot = slot_var.get()
            name = name_var.get()
            check()
            if slot not in slots or slots[slot].problem is not None or problem_var.get():
                messagebox.showinfo("Rename Family", problem_var.get() or "Choose a family to rename.", parent=dialog)
                return
            old = vf2_rename_family.shown(slots[slot].name)
            if not messagebox.askyesno(
                "Rename Family",
                f"Rename family slot {slot}, \"{old}\", to \"{name}\"?\n\nYour saves are backed up first. The game "
                "must be closed.",
                parent=dialog,
            ):
                return
            dialog.destroy()
            self._run_rename(folder, slot, name)

        ttk.Button(buttons, text="Rename", command=start).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=(8, 0))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog._vf2_folder_var = folder_var
        dialog._vf2_slot_var = slot_var
        dialog._vf2_name_var = name_var
        dialog._vf2_problem_var = problem_var
        dialog._vf2_start = start
        self._hold(dialog)
        with contextlib.suppress(tk.TclError):
            entry.focus_set()
        return dialog

    def _run_rename(self, folder: Path, slot: int, name: str):
        def work():
            try:
                return vf2_rename_family.rename_family(folder, slot, name), None
            except (vf2_rename_family.RenameError, vf2_save_backup.BackupError, OSError) as exc:
                return None, str(exc)

        result, error = self._run_with_wait("Backing up your saves, then writing the new name into them...", work)
        if error is not None:
            self.status_var.set("Rename Family: nothing was renamed.")
            messagebox.showerror("Rename Family", error)
            return None
        self.status_var.set(f"Rename Family: family slot {slot} is now called {result.new_name}.")
        files = ", ".join(path.name for path in result.changed)
        messagebox.showinfo(
            "Rename Family",
            f"Family slot {slot} was \"{result.old_name}\" and is now \"{result.new_name}\" ({files}; every file was "
            f"read back and checked).\n\nBackup: {result.backup.backup_folder}",
        )
        return result

    # -- Game Speed ---------------------------------------------------------

    def game_speed(self) -> tk.Toplevel | None:
        """Let the player pick a family slot and Paused or Normal, then write that speed into the closed game's save."""
        folders = self._tool_save_folders()
        if folders is None:
            return None
        folders = [folder for folder in folders
                   if any(s.state is not None for s in vf2_game_speed.read_slots(folder))]
        if not folders:
            messagebox.showinfo(
                "Game Speed",
                "No Virtual Families 2 family saves were found in your Documents\\LDW folder.\n\n"
                "The game makes a family's save the first time it saves that family.",
            )
            return None
        return self._show_speed_dialog(folders)

    def _show_speed_dialog(self, folders: list[Path]) -> tk.Toplevel:
        dialog, frame = self._scrolling_dialog("Game Speed")
        ttk.Label(frame, text="Set a family's game speed:", font=("", 10, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Quit the game from its own menu first: a running game would put the old speed back. Your saves are "
                "backed up first, as \"Backup <date> (before speed change)\". Paused works as if you paused just "
                "before the game last saved; Normal as if you unpaused it now, so the paused time is never aged in."
            ),
            wraplength=WRAP, justify="left",
        ).pack(anchor="w", pady=(4, 10))
        by_name = {folder.name: folder for folder in folders}
        folder_var = tk.StringVar(value=folders[0].name)
        if len(folders) > 1:
            row = ttk.Frame(frame)
            row.pack(anchor="w", pady=(0, 6))
            ttk.Label(row, text="Save folder").pack(side="left", padx=(0, 8))
            ttk.Combobox(row, textvariable=folder_var, values=list(by_name), state="readonly", width=48).pack(side="left")
        slot_var = tk.IntVar(value=0)
        slots_box = ttk.Frame(frame)
        slots_box.pack(anchor="w", pady=(0, 6))
        target_var = tk.StringVar(value="")
        problem_var = tk.StringVar()
        slots: dict[int, vf2_game_speed.SlotSpeed] = {}

        def fill_slots(*_args) -> None:
            for child in slots_box.winfo_children():
                child.destroy()
            slots.clear()
            first = 0
            for info in vf2_game_speed.read_slots(by_name[folder_var.get()]):
                slots[info.slot] = info
                usable = info.state is not None and info.problem is None
                ttk.Radiobutton(slots_box, text=info.label, value=info.slot, variable=slot_var,
                                state="normal" if usable else "disabled").pack(anchor="w")
                if usable and not first:
                    first = info.slot
            slot_var.set(first)

        def check(*_args) -> None:
            info = slots.get(slot_var.get())
            target = target_var.get()
            if info is None or info.state is None:
                problem = "Choose a family."
            elif info.problem:
                problem = info.problem
            elif not target:
                problem = "Choose Paused or Normal."
            elif info.state.label == target:
                problem = f"This family is {target} already."
            else:
                problem = ""
            problem_var.set(problem)

        def picked(*_args) -> None:
            info = slots.get(slot_var.get())
            if info is not None and info.state is not None and info.problem is None:
                target_var.set(vf2_game_speed.NORMAL_NAME if info.state.kind == "paused" else vf2_game_speed.PAUSED)
            check()

        ttk.Label(frame, text="New speed").pack(anchor="w")
        targets = ttk.Frame(frame)
        targets.pack(anchor="w", pady=(2, 0))
        for name in vf2_game_speed.TARGETS:
            ttk.Radiobutton(targets, text=name, value=name, variable=target_var).pack(side="left", padx=(0, 14))
        ttk.Label(frame, textvariable=problem_var, foreground="#a01010", wraplength=WRAP, justify="left").pack(
            anchor="w", pady=(2, 0))
        folder_var.trace_add("write", fill_slots)
        slot_var.trace_add("write", picked)
        target_var.trace_add("write", check)
        fill_slots()
        picked()
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))

        def start() -> None:
            folder = by_name[folder_var.get()]
            slot = slot_var.get()
            target = target_var.get()
            check()
            if slot not in slots or problem_var.get():
                messagebox.showinfo("Game Speed", problem_var.get() or "Choose a family.", parent=dialog)
                return
            info = slots[slot]
            if not messagebox.askyesno(
                "Game Speed",
                f"Set family slot {slot}, \"{vf2_rename_family.shown(info.name)}\", from {info.state.label} to "
                f"{target}?\n\nYour saves are backed up first. The game must be closed.",
                parent=dialog,
            ):
                return
            dialog.destroy()
            self._run_game_speed(folder, slot, target)

        ttk.Button(buttons, text="Set Speed", command=start).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=(8, 0))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog._vf2_folder_var = folder_var
        dialog._vf2_slot_var = slot_var
        dialog._vf2_target_var = target_var
        dialog._vf2_problem_var = problem_var
        dialog._vf2_start = start
        self._hold(dialog)
        return dialog

    def _run_game_speed(self, folder: Path, slot: int, target: str):
        def work():
            try:
                return vf2_game_speed.set_speed(folder, slot, target), None
            except (vf2_game_speed.SpeedError, vf2_save_backup.BackupError, OSError) as exc:
                return None, str(exc)

        result, error = self._run_with_wait("Backing up your saves, then writing the new speed into the save...", work)
        if error is not None:
            self.status_var.set("Game Speed: nothing was changed.")
            messagebox.showerror("Game Speed", error)
            return None
        self.status_var.set(f"Game Speed: family slot {slot} is now {result.after}.")
        messagebox.showinfo(
            "Game Speed",
            f"Family slot {slot} was {result.before} and is now {result.after} ({result.changed.name} was read back "
            f"and checked).\n\nBackup: {result.backup.backup_folder}",
        )
        return result
