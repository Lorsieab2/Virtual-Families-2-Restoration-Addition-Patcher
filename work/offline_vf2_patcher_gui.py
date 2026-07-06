#!/usr/bin/env python3
"""Tkinter GUI wrapper for the offline VF2 patcher."""

from __future__ import annotations

import contextlib
import io
import re
import subprocess
import threading
import traceback
from argparse import Namespace
from pathlib import Path
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog, messagebox, ttk

import offline_vf2_patcher as patcher

APP_DISPLAY_NAME = "Virtual Families 2 Restoration/Addition Patcher"
PATCHER_ICON_PNG = "patcher_icon.png"
PATCHER_ICON_ICO = "patcher_icon.ico"
SETTING_CATEGORIES = [
    ("main", "Main Patches", "#00802b"),
    ("optional", "Optional Patches", "#000000"),
    ("experimental", "Experimental/Not Working Patches", "#b00020"),
]
SETTING_CATEGORY_LOOKUP = {key: (label, color) for key, label, color in SETTING_CATEGORIES}


def clean_path_text(value: str | None) -> str:
    return (value or "").strip().strip('"')


def optional_path(value: str | None) -> str | None:
    text = clean_path_text(value)
    return text or None


def required_path(value: str | None, label: str) -> str:
    text = clean_path_text(value)
    if not text:
        raise patcher.PatchError(f"{label} is required.")
    return text


def markup_segments(text: str) -> list[tuple[str, bool]]:
    """Return (text, bold) spans for a tiny **bold** markup subset."""
    spans: list[tuple[str, bool]] = []
    pos = 0
    bold = False
    for match in re.finditer(r"\*\*", text):
        if match.start() > pos:
            spans.append((text[pos:match.start()], bold))
        bold = not bold
        pos = match.end()
    if pos < len(text):
        spans.append((text[pos:], bold))
    return spans


def categorized_settings(
    settings: dict[str, patcher.PatchSetting],
) -> list[tuple[str, str, str, list[patcher.PatchSetting]]]:
    grouped: dict[str, list[patcher.PatchSetting]] = {key: [] for key, _label, _color in SETTING_CATEGORIES}
    grouped["other"] = []
    for setting in settings.values():
        category = (setting.category or "main").lower()
        if category not in grouped:
            category = "other"
        grouped[category].append(setting)

    rows: list[tuple[str, str, str, list[patcher.PatchSetting]]] = []
    for key, label, color in SETTING_CATEGORIES:
        if grouped[key]:
            rows.append((key, label, color, grouped[key]))
    if grouped["other"]:
        rows.append(("other", "Other Patches", "#000000", grouped["other"]))
    return rows


def build_apply_namespace(
    *,
    game_dir: str,
    manifest: str,
    backup_dir: str | None = None,
    log: str | None = None,
    output_dir: str | None = None,
    dry_run: bool = False,
    settings: dict[str, patcher.PatchSetting] | None = None,
    selected_settings: set[str] | None = None,
) -> Namespace:
    settings = settings or {}
    selected_settings = selected_settings or set()
    unknown = sorted(selected_settings - set(settings))
    if unknown:
        raise patcher.PatchError(f"Unknown selected setting(s): {', '.join(unknown)}")
    return Namespace(
        game_dir=required_path(game_dir, "Game directory"),
        manifest=required_path(manifest, "Patch manifest"),
        output_dir=optional_path(output_dir),
        backup_dir=optional_path(backup_dir),
        log=optional_path(log),
        dry_run=bool(dry_run),
        enable=sorted(selected_settings) or None,
        disable=None,
        enable_all=False,
        disable_all=bool(settings),
        progress_callback=None,
    )


def build_restore_namespace(*, backup_dir: str, game_dir: str | None = None, log: str | None = None) -> Namespace:
    return Namespace(
        backup_dir=required_path(backup_dir, "Backup directory"),
        game_dir=optional_path(game_dir),
        log=optional_path(log),
    )


class VF2PatcherGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_DISPLAY_NAME)
        self.root.geometry("920x720")
        self.root.minsize(760, 560)

        self.game_dir_var = tk.StringVar()
        self.manifest_var = tk.StringVar()
        self.backup_dir_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.log_path_var = tk.StringVar()
        self.restore_backup_var = tk.StringVar()
        self.restore_log_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose a vanilla VF2 folder and a patch manifest.")

        self.settings: dict[str, patcher.PatchSetting] = {}
        self.setting_vars: dict[str, tk.BooleanVar] = {}
        self.loaded_manifest_path: str | None = None
        self.loaded_manifest_data: dict[str, object] | None = None
        self.last_auto_output_dir = ""
        self.busy_controls: list[tk.Widget] = []
        self.window_icon_image: tk.PhotoImage | None = None
        self.title_icon_image: tk.PhotoImage | None = None

        self._load_icons()
        self._build_styles()
        self._build_layout()

    def _asset_path_candidates(self, name: str) -> list[Path]:
        script_dir = Path(__file__).resolve().parent
        cwd = Path.cwd()
        return [
            script_dir / name,
            script_dir / "assets" / name,
            cwd / name,
            cwd / "work" / "assets" / name,
        ]

    def _load_icons(self) -> None:
        for path in self._asset_path_candidates(PATCHER_ICON_ICO):
            if path.is_file():
                try:
                    self.root.iconbitmap(str(path))
                    break
                except tk.TclError:
                    pass

        for path in self._asset_path_candidates(PATCHER_ICON_PNG):
            if path.is_file():
                try:
                    self.window_icon_image = tk.PhotoImage(file=str(path))
                    self.root.iconphoto(True, self.window_icon_image)
                    factor = max(1, (max(self.window_icon_image.width(), self.window_icon_image.height()) + 55) // 56)
                    self.title_icon_image = self.window_icon_image.subsample(factor, factor)
                    break
                except tk.TclError:
                    pass

    def _build_styles(self) -> None:
        style = ttk.Style()
        style.configure("Title.TLabel", font=("", 15, "bold"))
        style.configure("Section.TLabelframe.Label", font=("", 10, "bold"))
        style.configure("Muted.TLabel", foreground="#555555")
        style.configure("Status.TLabel", foreground="#333333")

    def _build_layout(self) -> None:
        root_frame = ttk.Frame(self.root, padding=12)
        root_frame.grid(row=0, column=0, sticky="nsew")
        root_frame.columnconfigure(0, weight=1)
        root_frame.rowconfigure(3, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        header = ttk.Frame(root_frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(1, weight=1)
        if self.title_icon_image is not None:
            ttk.Label(header, image=self.title_icon_image).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 10))
        ttk.Label(header, text=APP_DISPLAY_NAME, style="Title.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(
            header,
            text="Created with Codex AI. Applies transparent JSON patch manifests to a user-provided vanilla VF2 PC install.",
            style="Muted.TLabel",
        ).grid(row=1, column=1, sticky="w", pady=(2, 0))

        self._build_file_section(root_frame).grid(row=1, column=0, sticky="ew")
        self._build_settings_section(root_frame).grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        self._build_log_section(root_frame).grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        self._build_action_section(root_frame).grid(row=4, column=0, sticky="ew", pady=(10, 0))

    def _build_file_section(self, parent: tk.Widget) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Patch Input", style="Section.TLabelframe", padding=10)
        frame.columnconfigure(1, weight=1)

        self._path_row(frame, 0, "Vanilla game folder", self.game_dir_var, self._browse_game_dir)
        self._path_row(frame, 1, "Patch manifest", self.manifest_var, self._browse_manifest)
        self._path_row(frame, 2, "Modded output folder", self.output_dir_var, self._browse_output_dir, optional=True)
        self._path_row(frame, 3, "Backup folder", self.backup_dir_var, self._browse_backup_dir, optional=True)
        self._path_row(frame, 4, "Patch log", self.log_path_var, self._browse_log_path, optional=True)
        return frame

    def _build_settings_section(self, parent: tk.Widget) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Patch Settings", style="Section.TLabelframe", padding=10)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        controls = ttk.Frame(frame)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        controls.columnconfigure(4, weight=1)
        self._button(controls, "Load Manifest Settings", self.load_manifest_settings).grid(row=0, column=0, padx=(0, 6))
        self._button(controls, "Defaults", self.select_default_settings).grid(row=0, column=1, padx=(0, 6))
        self._button(controls, "Enable All", self.select_all_settings).grid(row=0, column=2, padx=(0, 6))
        self._button(controls, "Disable All", self.clear_all_settings).grid(row=0, column=3, padx=(0, 6))

        outer = ttk.Frame(frame)
        outer.grid(row=1, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        self.settings_canvas = tk.Canvas(outer, height=170, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.settings_canvas.yview)
        self.settings_canvas.configure(yscrollcommand=scrollbar.set)
        self.settings_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.settings_inner = ttk.Frame(self.settings_canvas)
        self.settings_window = self.settings_canvas.create_window((0, 0), window=self.settings_inner, anchor="nw")
        self.settings_inner.bind(
            "<Configure>",
            lambda event: self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox("all")),
        )
        self.settings_canvas.bind(
            "<Configure>",
            lambda event: self.settings_canvas.itemconfigure(self.settings_window, width=event.width),
        )
        self._render_settings_placeholder("Load a manifest to see toggleable patch settings.")
        return frame

    def _build_log_section(self, parent: tk.Widget) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Run Log", style="Section.TLabelframe", padding=10)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(frame, height=11, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        return frame

    def _build_action_section(self, parent: tk.Widget) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.columnconfigure(3, weight=1)
        self._button(frame, "Dry Run (Validate Only)", lambda: self.start_apply(dry_run=True)).grid(row=0, column=0, padx=(0, 8))
        self._apply_button(frame, "Apply Patches", lambda: self.start_apply(dry_run=False)).grid(row=0, column=1, padx=(0, 8))
        ttk.Label(
            frame,
            text="Dry Run validates that the patcher's working. It does not actually change or write files.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        restore_frame = ttk.Frame(frame)
        restore_frame.grid(row=2, column=0, columnspan=5, sticky="ew", pady=(10, 0))
        restore_frame.columnconfigure(1, weight=1)
        ttk.Label(restore_frame, text="Restore backup").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(restore_frame, textvariable=self.restore_backup_var).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        self._button(restore_frame, "Browse", self._browse_restore_backup).grid(row=0, column=2, padx=(0, 8))
        ttk.Label(restore_frame, text="Restore log").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        ttk.Entry(restore_frame, textvariable=self.restore_log_var).grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=(6, 0))
        self._button(restore_frame, "Save As", self._browse_restore_log).grid(row=1, column=2, padx=(0, 8), pady=(6, 0))
        self._button(restore_frame, "Restore Backup", self.start_restore).grid(row=0, column=3, rowspan=2, sticky="ns")

        ttk.Label(frame, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0, column=3, sticky="ew", padx=(8, 0)
        )
        return frame

    def _path_row(
        self,
        parent: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
        command: object,
        *,
        optional: bool = False,
    ) -> None:
        suffix = " (optional)" if optional else ""
        ttk.Label(parent, text=f"{label}{suffix}").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(0, 6), pady=3)
        self._button(parent, "Browse", command).grid(row=row, column=2, sticky="ew", pady=3)

    def _button(self, parent: tk.Widget, text: str, command: object) -> ttk.Button:
        button = ttk.Button(parent, text=text, command=command)
        self.busy_controls.append(button)
        return button

    def _apply_button(self, parent: tk.Widget, text: str, command: object) -> tk.Button:
        button = tk.Button(parent, text=text, command=command, fg="#00802b", font=("", 10, "bold"), padx=12)
        self.busy_controls.append(button)
        return button

    def _browse_game_dir(self) -> None:
        path = filedialog.askdirectory(title="Select the vanilla VF2 game folder")
        if path:
            self.game_dir_var.set(path)
            self._auto_populate_output_dir()

    def prompt_for_game_dir_on_startup(self) -> None:
        if clean_path_text(self.game_dir_var.get()):
            return
        path = filedialog.askdirectory(
            title="Select your vanilla Virtual Families 2 install folder",
            mustexist=True,
        )
        if path:
            self.game_dir_var.set(path)
            self._auto_populate_output_dir()
            self.status_var.set("Vanilla VF2 folder selected. Review settings, then run Dry Run or Apply Patches.")

    def _browse_manifest(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a VF2 patch manifest",
            filetypes=[("JSON manifests", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.manifest_var.set(path)
            self.load_manifest_settings()
            self._auto_populate_output_dir()

    def _browse_backup_dir(self) -> None:
        path = filedialog.askdirectory(title="Select a backup output folder")
        if path:
            self.backup_dir_var.set(path)

    def _browse_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Select the modded output folder")
        if path:
            self.output_dir_var.set(path)

    def _browse_log_path(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose patch log path",
            defaultextension=".json",
            filetypes=[("JSON logs", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.log_path_var.set(path)

    def _browse_restore_backup(self) -> None:
        path = filedialog.askdirectory(title="Select a VF2 patch backup folder")
        if path:
            self.restore_backup_var.set(path)

    def _browse_restore_log(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose restore log path",
            defaultextension=".json",
            filetypes=[("JSON logs", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.restore_log_var.set(path)

    def load_manifest_settings(self) -> bool:
        try:
            manifest_path = Path(required_path(self.manifest_var.get(), "Patch manifest")).resolve()
            manifest = patcher.read_json(manifest_path)
            settings = patcher.manifest_settings(manifest)
        except Exception as exc:
            self._set_error(f"Could not load manifest settings: {exc}")
            return False

        self.settings = settings
        self.loaded_manifest_path = str(manifest_path)
        self.loaded_manifest_data = manifest if isinstance(manifest, dict) else None
        self.setting_vars = {}
        for child in self.settings_inner.winfo_children():
            child.destroy()

        if not settings:
            self._render_settings_placeholder("This manifest does not declare toggleable settings.")
        else:
            row = 0
            for _key, label, color, category_settings in categorized_settings(settings):
                self._category_header(self.settings_inner, label, color).grid(row=row, column=0, sticky="ew", pady=(8 if row else 0, 4))
                row += 1
                for setting in category_settings:
                    var = tk.BooleanVar(value=setting.default)
                    self.setting_vars[setting.id] = var
                    item = ttk.Frame(self.settings_inner, padding=(0, 4))
                    item.grid(row=row, column=0, sticky="ew")
                    item.columnconfigure(0, weight=1)
                    ttk.Checkbutton(item, text=setting.label, variable=var).grid(row=0, column=0, sticky="w")
                    state = "default on" if setting.default else "default off"
                    details = f"{setting.id} - {state} - {setting.description}" if setting.description else f"{setting.id} - {state}"
                    self._markup_label(item, details).grid(row=1, column=0, sticky="ew", padx=(22, 0))
                    row += 1
        self.status_var.set(f"Loaded {len(settings)} setting(s) from {manifest_path.name}.")
        self._append_log(f"Loaded manifest settings: {manifest_path}\n")
        self._auto_populate_output_dir()
        return True

    def _markup_label(self, parent: tk.Widget, text: str) -> tk.Text:
        widget = tk.Text(
            parent,
            height=1,
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            background=self.root.cget("background"),
            foreground="#555555",
        )
        normal_font = tkfont.nametofont("TkDefaultFont").copy()
        bold_font = normal_font.copy()
        bold_font.configure(weight="bold")
        widget.tag_configure("normal", font=normal_font, foreground="#555555")
        widget.tag_configure("bold", font=bold_font, foreground="#555555")
        for segment, bold in markup_segments(text):
            widget.insert("end", segment, "bold" if bold else "normal")
        widget.configure(state="disabled", cursor="arrow")
        widget.bind("<Configure>", lambda _event, text_widget=widget: self._resize_markup_label(text_widget))
        self.root.after_idle(lambda text_widget=widget: self._resize_markup_label(text_widget))
        return widget

    def _category_header(self, parent: tk.Widget, text: str, color: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            fg=color,
            font=("", 10, "bold"),
            anchor="w",
            background=self.root.cget("background"),
        )

    def _resize_markup_label(self, widget: tk.Text) -> None:
        try:
            count = widget.count("1.0", "end-1c", "displaylines")
            display_lines = int(count[0]) if count else 1
        except tk.TclError:
            display_lines = max(1, int(widget.index("end-1c").split(".", 1)[0]))
        height = max(1, display_lines)
        if int(widget.cget("height")) != height:
            widget.configure(height=height)
            self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox("all"))

    def _render_settings_placeholder(self, text: str) -> None:
        for child in self.settings_inner.winfo_children():
            child.destroy()
        ttk.Label(self.settings_inner, text=text, style="Muted.TLabel", padding=(0, 8)).grid(row=0, column=0, sticky="w")

    def select_default_settings(self) -> None:
        for setting_id, var in self.setting_vars.items():
            var.set(self.settings[setting_id].default)

    def select_all_settings(self) -> None:
        for var in self.setting_vars.values():
            var.set(True)

    def clear_all_settings(self) -> None:
        for var in self.setting_vars.values():
            var.set(False)

    def start_apply(self, *, dry_run: bool) -> None:
        if not self._ensure_manifest_settings_loaded():
            return
        self._auto_populate_output_dir()
        selected = {setting_id for setting_id, var in self.setting_vars.items() if var.get()}
        try:
            args = build_apply_namespace(
                game_dir=self.game_dir_var.get(),
                manifest=self.manifest_var.get(),
                output_dir=self.output_dir_var.get(),
                backup_dir=self.backup_dir_var.get(),
                log=self.log_path_var.get(),
                dry_run=dry_run,
                settings=self.settings,
                selected_settings=selected,
            )
        except patcher.PatchError as exc:
            self._set_error(str(exc))
            return
        args.progress_callback = lambda message: self.root.after(
            0,
            lambda text=message: self._append_log(text + "\n"),
        )

        if not dry_run and not messagebox.askyesno(
            f"Apply {APP_DISPLAY_NAME}",
            "This will validate the vanilla game folder, then create a separate modded game folder and backup before writing patched files. Continue?",
        ):
            return

        label = "Dry run" if dry_run else "Apply patches"
        self._run_worker(label, lambda: patcher.apply_manifest(args), args=args, dry_run=dry_run)

    def start_restore(self) -> None:
        try:
            args = build_restore_namespace(
                backup_dir=self.restore_backup_var.get(),
                game_dir=self.game_dir_var.get(),
                log=self.restore_log_var.get(),
            )
        except patcher.PatchError as exc:
            self._set_error(str(exc))
            return
        if not messagebox.askyesno(APP_DISPLAY_NAME, "Restore the selected backup into the game folder?"):
            return
        self._run_worker("Restore backup", lambda: patcher.restore_backup(args))

    def _ensure_manifest_settings_loaded(self) -> bool:
        try:
            current = str(Path(required_path(self.manifest_var.get(), "Patch manifest")).resolve())
        except patcher.PatchError as exc:
            self._set_error(str(exc))
            return False
        if current != self.loaded_manifest_path:
            return self.load_manifest_settings()
        return True

    def _auto_populate_output_dir(self) -> None:
        game_dir_text = clean_path_text(self.game_dir_var.get())
        if not game_dir_text:
            return
        manifest = self.loaded_manifest_data
        folder_name = None
        if isinstance(manifest, dict):
            output = manifest.get("output")
            if isinstance(output, dict):
                raw_folder = output.get("default_folder_name")
                if isinstance(raw_folder, str) and raw_folder.strip():
                    folder_name = raw_folder.strip()
        game_dir = Path(game_dir_text)
        default_output = str((game_dir.parent / folder_name).resolve()) if folder_name else str(game_dir.resolve())
        current = clean_path_text(self.output_dir_var.get())
        if not current or current == self.last_auto_output_dir:
            self.output_dir_var.set(default_output)
            self.last_auto_output_dir = default_output

    def _run_worker(self, label: str, func: object, *, args: object | None = None, dry_run: bool = False) -> None:
        self._set_busy(True)
        self.status_var.set(f"{label} running...")
        self._append_log(f"\n== {label} ==\n")

        def worker() -> None:
            stdout = io.StringIO()
            stderr = io.StringIO()
            success = True
            message = ""
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    func()
                except patcher.PatchError as exc:
                    success = False
                    message = f"ERROR: {exc}"
                except Exception:
                    success = False
                    message = traceback.format_exc()
            output = stdout.getvalue()
            err_output = stderr.getvalue()
            summary = getattr(args, "last_apply_summary", None) if args is not None else None
            self.root.after(0, lambda: self._finish_worker(label, success, message, output, err_output, summary, dry_run))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_worker(
        self,
        label: str,
        success: bool,
        message: str,
        stdout: str,
        stderr: str,
        summary: dict[str, object] | None = None,
        dry_run: bool = False,
    ) -> None:
        if stdout:
            self._append_log(stdout)
        if stderr:
            self._append_log(stderr)
        if message:
            self._append_log(message + "\n")
        self._set_busy(False)
        if success:
            self.status_var.set(f"{label} complete.")
            if summary and not dry_run:
                self._show_apply_success(summary)
        else:
            self.status_var.set(f"{label} failed.")
            if message:
                display = message.removeprefix("ERROR: ").strip()
                messagebox.showerror(APP_DISPLAY_NAME, display)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for control in self.busy_controls:
            control.configure(state=state)

    def _set_error(self, message: str) -> None:
        self.status_var.set(message)
        self._append_log(f"ERROR: {message}\n")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _show_apply_success(self, summary: dict[str, object]) -> None:
        settings = summary.get("settings", {})
        enabled_labels = []
        if isinstance(settings, dict):
            for row in settings.get("available", []):
                if isinstance(row, dict) and row.get("enabled"):
                    enabled_labels.append(str(row.get("label") or row.get("id")))
        altered_files = []
        for key in ("patched_files", "asset_files"):
            rows = summary.get(key, [])
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        altered_files.append(str(row.get("output_file_path") or row.get("file_path")))

        def compact(values: list[str], limit: int = 18) -> str:
            if not values:
                return "(none)"
            shown = values[:limit]
            suffix = "" if len(values) <= limit else f"\n...and {len(values) - limit} more."
            return "\n".join(f"- {value}" for value in shown) + suffix

        vanilla_dir = str(summary.get("game_dir", ""))
        output_dir = str(summary.get("output_dir", ""))
        save_dir = str(summary.get("modded_save_dir", ""))
        log_path = str(summary.get("log_path", ""))
        win = tk.Toplevel(self.root)
        win.title(f"{APP_DISPLAY_NAME} complete")
        win.geometry("780x620")
        win.minsize(620, 430)
        win.transient(self.root)
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)

        body = ttk.Frame(win, padding=14)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(5, weight=1)

        ttk.Label(body, text="Patch complete!", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(body, text="Patches added successfully:", style="Section.TLabelframe.Label").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Label(body, text=compact(enabled_labels, limit=10), wraplength=720, justify="left").grid(row=2, column=0, sticky="ew")

        paths = ttk.Frame(body)
        paths.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        paths.columnconfigure(1, weight=1)
        self._path_link_row(paths, 0, "Vanilla Game Folder Path", vanilla_dir)
        self._path_link_row(paths, 1, "Modified Game Folder Path", output_dir)
        self._path_link_row(paths, 2, "Modified Game Saves Folder Path", save_dir)

        ttk.Label(body, text="Modified file log:", style="Section.TLabelframe.Label").grid(row=4, column=0, sticky="w", pady=(12, 0))
        log_frame = ttk.Frame(body)
        log_frame.grid(row=5, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        file_text = tk.Text(log_frame, height=14, wrap="none")
        file_scroll_y = ttk.Scrollbar(log_frame, orient="vertical", command=file_text.yview)
        file_scroll_x = ttk.Scrollbar(log_frame, orient="horizontal", command=file_text.xview)
        file_text.configure(yscrollcommand=file_scroll_y.set, xscrollcommand=file_scroll_x.set)
        file_text.grid(row=0, column=0, sticky="nsew")
        file_scroll_y.grid(row=0, column=1, sticky="ns")
        file_scroll_x.grid(row=1, column=0, sticky="ew")
        file_lines = [f"- {value}" for value in sorted(set(altered_files))] or ["(none)"]
        if log_path:
            file_lines.insert(0, f"Patch log: {log_path}")
            file_lines.insert(1, "")
        file_text.insert("end", "\n".join(file_lines))
        file_text.configure(state="disabled")

        footer_text = (
            "To play existing Virtual Families 2 saves, copy the contents of your original "
            "Documents/LDW/Virtual Families 2 save folder into the modded save folder above. "
            "Existing game saves are unaltered in the original game folder.\n\n"
            "Have fun! -Lorsieab2 :)"
        )
        ttk.Label(body, text=footer_text, wraplength=720, justify="left").grid(row=6, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(body, text="Close", command=win.destroy).grid(row=7, column=0, sticky="e", pady=(12, 0))

    def _path_link_row(self, parent: tk.Widget, row: int, label: str, path: str) -> None:
        ttk.Label(parent, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
        link = tk.Label(
            parent,
            text=path or "(not available)",
            fg="#0057c2",
            font=("", 9, "bold"),
            cursor="hand2" if path else "arrow",
            anchor="w",
        )
        link.grid(row=row, column=1, sticky="ew", pady=2)
        if path:
            link.bind("<Button-1>", lambda _event, value=path: self._open_path(value))

    def _open_path(self, path: str) -> None:
        try:
            subprocess.Popen(["explorer", path])
        except Exception as exc:
            messagebox.showerror(APP_DISPLAY_NAME, f"Could not open path:\n{path}\n\n{exc}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = tk.Tk()
    app = VF2PatcherGUI(root)
    if argv:
        app.manifest_var.set(argv[0])
        def startup_load() -> None:
            app.load_manifest_settings()
            root.after(150, app.prompt_for_game_dir_on_startup)

        root.after(100, startup_load)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
