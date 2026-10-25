"""The Tools tab of the patcher window: Back Up Saves, Restore Saves and the How to Use guide.

A mixin for VF2PatcherGUI (offline_vf2_patcher_gui.py), kept in its own file so the window's patching code
stays as it was.  It needs from the window: ``root``, ``status_var``, ``_run_with_wait`` and the
``Link.TLabel`` / ``LinkHover.TLabel`` styles.  The saves themselves are handled by vf2_save_backup (no Tk
there); the guides live in vf2_how_to_use.json.
"""
from __future__ import annotations

import contextlib
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import vf2_family_logs
import vf2_how_to_use
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
                "patcher's own files beside them) into a Backups folder in there; Restore Saves brings one back."
            ),
            style="Muted.TLabel", wraplength=WRAP, justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row = ttk.Frame(saves)
        row.grid(row=1, column=0, sticky="w")
        self._link(row, "Back Up Saves...", self.back_up_saves).pack(side="left")
        self._help_button(row, "back_up_saves").pack(side="left", padx=(3, 0))
        self._link(row, "Restore Saves...", self.restore_saves).pack(side="left", padx=(24, 0))
        self._help_button(row, "restore_saves").pack(side="left", padx=(3, 0))

        logs = ttk.LabelFrame(tab, text="Family Logs", style="Section.TLabelframe", padding=10)
        logs.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(
            logs,
            text=(
                "Each family's history, births, deaths and events, written beside its save in "
                "Virtual Families 2 Patcher\\Save <N>\\Logs. They are worked out from the saves the game writes when "
                "you quit, so they update when this tab opens and when you click Update Family Logs."
            ),
            style="Muted.TLabel", wraplength=WRAP, justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        row = ttk.Frame(logs)
        row.grid(row=1, column=0, sticky="w")
        self._link(row, "Update Family Logs", self.update_family_logs).pack(side="left")
        self._help_button(row, "update_family_logs").pack(side="left", padx=(3, 0))
        notebook = getattr(self, "notebook", None)
        if notebook is not None:
            notebook.bind("<<NotebookTabChanged>>", self._tools_tab_changed, add="+")

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

    # -- Family Logs ---------------------------------------------------------

    def _tools_tab_changed(self, _event=None) -> None:
        """Opening the Tools tab brings every family's logs up to date (quietly: the status line says how it went)."""
        try:
            if self.notebook.select() != str(self.tools_tab):
                return
        except (AttributeError, tk.TclError):
            return
        self.update_family_logs(quiet=True)

    def update_family_logs(self, quiet: bool = False):
        """Update the Family Logs of every save folder; refused for a folder whose game is running."""
        documents = vf2_save_backup.documents_folder()
        if documents is None:
            if not quiet:
                messagebox.showerror("Family Logs", "Windows did not report where your Documents folder is, so the save folders cannot be found.")
            return None
        try:
            if quiet:
                outcomes = vf2_family_logs.update_all(documents)
            else:
                outcomes = self._run_with_wait("Updating Family Logs...", lambda: vf2_family_logs.update_all(documents))
        except OSError as exc:
            self.status_var.set(f"Family Logs: not updated ({exc}).")
            if not quiet:
                messagebox.showerror("Family Logs", f"The Family Logs could not be updated:\n\n{exc}")
            return None
        changed = sum(1 for _f, results, _e in outcomes for r in results or () if r.lines)
        refused = [f.name for f, results, _e in outcomes if results is None]
        text = f"Family Logs: {len(outcomes) - len(refused)} save folder(s) checked, {changed} family log(s) updated."
        if refused:
            text += f" Not updated while the game is running: {', '.join(refused)}."
        self.status_var.set(text)
        if not quiet:
            self._show_family_logs_results(outcomes)
        return outcomes

    def _show_family_logs_results(self, outcomes) -> tk.Toplevel:
        dialog, frame = self._scrolling_dialog("Family Logs")
        if not outcomes:
            ttk.Label(frame, text="No Virtual Families 2 save folders were found in your Documents\\LDW folder.",
                      wraplength=WRAP, justify="left").pack(anchor="w")
        words = {"updated": "updated", "unchanged": "no change since the last update", "started": "logs started",
                 "backfilled": "logs started from the family tree", "new family": "a new family: logs started again",
                 "unreadable": "the save could not be read; nothing was changed"}
        for folder, results, error in outcomes:
            ttk.Label(frame, text=folder.name, font=("", 10, "bold")).pack(anchor="w", pady=(8, 0))
            if results is None:
                ttk.Label(frame, text=f"NOT updated: {error}", wraplength=WRAP, justify="left", foreground="#a01010").pack(
                    anchor="w", padx=(14, 0))
                continue
            lines = [f"Save {r.slot}: {words.get(r.status, r.status)}"
                     + (f" ({r.lines} new line(s))" if r.lines else "") for r in results if r.status != "no save"]
            ttk.Label(frame, text="\n".join(lines) or "No family saves.", wraplength=WRAP, justify="left").pack(
                anchor="w", padx=(14, 0))
            logs = folder / vf2_family_logs.PATCHER_FOLDER
            if logs.is_dir():
                self._link(frame, "Open Family Logs Folder", lambda path=logs: self._open_folder(path)).pack(
                    anchor="w", padx=(14, 0), pady=(2, 0))
        ttk.Button(frame, text="Close", command=dialog.destroy).pack(pady=(16, 0))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self._hold(dialog)
        return dialog

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
