#!/usr/bin/env python3
"""Tkinter GUI wrapper for the offline VF2 patcher."""

from __future__ import annotations

import contextlib
import io
import threading
import traceback
from argparse import Namespace
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import offline_vf2_patcher as patcher


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


def build_apply_namespace(
    *,
    game_dir: str,
    manifest: str,
    backup_dir: str | None = None,
    log: str | None = None,
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
        backup_dir=optional_path(backup_dir),
        log=optional_path(log),
        dry_run=bool(dry_run),
        enable=sorted(selected_settings) or None,
        disable=None,
        enable_all=False,
        disable_all=bool(settings),
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
        self.root.title("VF2 Offline Patcher")
        self.root.geometry("920x720")
        self.root.minsize(760, 560)

        self.game_dir_var = tk.StringVar()
        self.manifest_var = tk.StringVar()
        self.backup_dir_var = tk.StringVar()
        self.log_path_var = tk.StringVar()
        self.restore_backup_var = tk.StringVar()
        self.restore_log_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose a vanilla VF2 folder and a patch manifest.")

        self.settings: dict[str, patcher.PatchSetting] = {}
        self.setting_vars: dict[str, tk.BooleanVar] = {}
        self.loaded_manifest_path: str | None = None
        self.busy_controls: list[tk.Widget] = []

        self._build_styles()
        self._build_layout()

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
        root_frame.rowconfigure(4, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        ttk.Label(root_frame, text="VF2 Offline Patcher", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            root_frame,
            text="Applies transparent JSON patch manifests to a user-provided vanilla VF2 PC install.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        self._build_file_section(root_frame).grid(row=2, column=0, sticky="ew")
        self._build_settings_section(root_frame).grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        self._build_log_section(root_frame).grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        self._build_action_section(root_frame).grid(row=5, column=0, sticky="ew", pady=(10, 0))

    def _build_file_section(self, parent: tk.Widget) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Patch Input", style="Section.TLabelframe", padding=10)
        frame.columnconfigure(1, weight=1)

        self._path_row(frame, 0, "Vanilla game folder", self.game_dir_var, self._browse_game_dir)
        self._path_row(frame, 1, "Patch manifest", self.manifest_var, self._browse_manifest)
        self._path_row(frame, 2, "Backup folder", self.backup_dir_var, self._browse_backup_dir, optional=True)
        self._path_row(frame, 3, "Patch log", self.log_path_var, self._browse_log_path, optional=True)
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
        self._button(frame, "Dry Run", lambda: self.start_apply(dry_run=True)).grid(row=0, column=0, padx=(0, 8))
        self._button(frame, "Apply Patch", lambda: self.start_apply(dry_run=False)).grid(row=0, column=1, padx=(0, 8))

        restore_frame = ttk.Frame(frame)
        restore_frame.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(10, 0))
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

    def _browse_game_dir(self) -> None:
        path = filedialog.askdirectory(title="Select the vanilla VF2 game folder")
        if path:
            self.game_dir_var.set(path)

    def _browse_manifest(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a VF2 patch manifest",
            filetypes=[("JSON manifests", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.manifest_var.set(path)
            self.load_manifest_settings()

    def _browse_backup_dir(self) -> None:
        path = filedialog.askdirectory(title="Select a backup output folder")
        if path:
            self.backup_dir_var.set(path)

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
        self.setting_vars = {}
        for child in self.settings_inner.winfo_children():
            child.destroy()

        if not settings:
            self._render_settings_placeholder("This manifest does not declare toggleable settings.")
        else:
            for row, setting in enumerate(settings.values()):
                var = tk.BooleanVar(value=setting.default)
                self.setting_vars[setting.id] = var
                item = ttk.Frame(self.settings_inner, padding=(0, 4))
                item.grid(row=row, column=0, sticky="ew")
                item.columnconfigure(0, weight=1)
                ttk.Checkbutton(item, text=setting.label, variable=var).grid(row=0, column=0, sticky="w")
                state = "default on" if setting.default else "default off"
                details = f"{setting.id} - {state}"
                if setting.description:
                    details += f" - {setting.description}"
                ttk.Label(item, text=details, style="Muted.TLabel").grid(row=1, column=0, sticky="w", padx=(22, 0))
        self.status_var.set(f"Loaded {len(settings)} setting(s) from {manifest_path.name}.")
        self._append_log(f"Loaded manifest settings: {manifest_path}\n")
        return True

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
        selected = {setting_id for setting_id, var in self.setting_vars.items() if var.get()}
        try:
            args = build_apply_namespace(
                game_dir=self.game_dir_var.get(),
                manifest=self.manifest_var.get(),
                backup_dir=self.backup_dir_var.get(),
                log=self.log_path_var.get(),
                dry_run=dry_run,
                settings=self.settings,
                selected_settings=selected,
            )
        except patcher.PatchError as exc:
            self._set_error(str(exc))
            return

        if not dry_run and not messagebox.askyesno(
            "Apply VF2 patch",
            "This will patch files inside the selected game folder after creating a backup. Continue?",
        ):
            return

        label = "Dry run" if dry_run else "Apply patch"
        self._run_worker(label, lambda: patcher.apply_manifest(args))

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
        if not messagebox.askyesno("Restore VF2 backup", "Restore the selected backup into the game folder?"):
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

    def _run_worker(self, label: str, func: object) -> None:
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
            self.root.after(0, lambda: self._finish_worker(label, success, message, output, err_output))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_worker(self, label: str, success: bool, message: str, stdout: str, stderr: str) -> None:
        if stdout:
            self._append_log(stdout)
        if stderr:
            self._append_log(stderr)
        if message:
            self._append_log(message + "\n")
        self._set_busy(False)
        if success:
            self.status_var.set(f"{label} complete.")
        else:
            self.status_var.set(f"{label} failed.")

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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = tk.Tk()
    app = VF2PatcherGUI(root)
    if argv:
        app.manifest_var.set(argv[0])
        root.after(100, app.load_manifest_settings)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
