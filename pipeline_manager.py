"""
Google Earth → MSFS Pipeline Manager
A full-featured GUI for managing the GLTF-to-FBX pipeline configuration and execution.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
import sys
import subprocess
import threading
import queue
import time
import copy
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
#  WINDOWS: DPI AWARENESS + DEDICATED GPU
# ─────────────────────────────────────────────
if sys.platform == "win32":
    import ctypes
    # Per-monitor V2 DPI — sharpest possible text on any display scale factor.
    # Must be called BEFORE any window is created.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PROCESS_PER_MONITOR_DPI_AWARE_V2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()    # fallback: system-DPI aware
        except Exception:
            pass

    # Force dedicated (high-performance) GPU on Optimus/hybrid systems.
    # NvOptimusEnablement and AmdPowerXpressRequestHighPerformance are normally
    # compiled into the exe; for a Python script we set the Windows GPU preference
    # via the Graphics Performance Preference registry key for the running executable.
    try:
        import winreg
        _exe = sys.executable
        _key_path = r"SOFTWARE\Microsoft\DirectX\UserGpuPreferences"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _key_path,
                            0, winreg.KEY_SET_VALUE) as _k:
            winreg.SetValueEx(_k, _exe, 0, winreg.REG_SZ,
                              "GpuPreference=2;")   # 2 = High Performance GPU
    except Exception:
        pass   # non-fatal: app still works on integrated GPU


# ─────────────────────────────────────────────
#  THEME & STYLE CONSTANTS
# ─────────────────────────────────────────────
DARK_BG        = "#1e1e2e"
PANEL_BG       = "#252535"
SIDEBAR_BG     = "#1a1a28"
ACCENT         = "#7c6af5"
ACCENT_HOVER   = "#9d8ff7"
ACCENT_DARK    = "#5a4fd6"
SUCCESS        = "#4ade80"
WARNING        = "#facc15"
ERROR          = "#f87171"
INFO           = "#60a5fa"
TEXT_PRIMARY   = "#e2e8f0"
TEXT_SECONDARY = "#94a3b8"
TEXT_DIM       = "#64748b"
BORDER         = "#2d2d45"
INPUT_BG       = "#1a1a2e"
INPUT_BORDER   = "#383858"
CONSOLE_BG     = "#0d0d1a"
CONSOLE_FG     = "#a8ff78"

FONT_FAMILY    = "Segoe UI"
FONT_MONO      = "Consolas"


# ─────────────────────────────────────────────
#  DEFAULT CONFIG TEMPLATE
# ─────────────────────────────────────────────
DEFAULT_CONFIG = {
    "paths": {
        "projectRoot": "D:\\Projects\\google_earth_export\\",
        "blenderExecutable": "D:\\Program Files\\Blender 5.0\\blender.exe"
    },
    "folders": {
        "gltfExport": "gltf_export",
        "modelLib": "gltf_export\\modelLib",
        "modelLibTextures": "gltf_export\\modelLib\\texture",
        "batchFbxOutput": "gltf_export\\batch_fbx",
        "mergedOutput": "gltf_export\\merged"
    },
    "scripts": {
        "mergeGltfBatchOptimized": "merge_gltf_batch_optimized.py",
        "mergeFinalFbx": "merge_final_fbx.py",
        "processGltfParallel": "process_gltf_parallel.ps1",
        "runFullPipeline": "run_full_pipeline.ps1"
    },
    "output": {
        "mergedFbxName": "merged.fbx"
    },
    "processing": {
        "maxParallelBlenderInstances": 32,
        "processCheckIntervalMs": 200,
        "defaultFilesPerBatch": 10,
        "defaultDecimateRatio": 0.5,
        "cleanupSubfolders": True
    },
    "optimization": {
        "enableDecimation": True,
        "enableNormalBaking": True,
        "normalMapResolution": 2048,
        "bakeCageExtrusion": 0.1,
        "bakeMaxRayDistance": 1.0
    },
    "options": {
        "cleanOutputFolders": False,
        "verboseLogging": True,
        "saveBatchLogs": True,
        "removeHighPolyAfterBake": True
    },
    "quality": {
        "presets": {
            "ultra_high": {"decimateRatio": 0.9, "filesPerBatch": 5,  "normalMapResolution": 4096},
            "high":       {"decimateRatio": 0.7, "filesPerBatch": 10, "normalMapResolution": 2048},
            "medium":     {"decimateRatio": 0.5, "filesPerBatch": 15, "normalMapResolution": 2048},
            "low":        {"decimateRatio": 0.3, "filesPerBatch": 20, "normalMapResolution": 1024},
            "very_low":   {"decimateRatio": 0.1, "filesPerBatch": 50, "normalMapResolution": 512}
        }
    }
}


# ─────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────
def deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ─────────────────────────────────────────────
#  STYLED WIDGETS
# ─────────────────────────────────────────────
class StyledButton(tk.Button):
    def __init__(self, parent, text="", command=None, style="primary",
                 width=None, **kwargs):
        colors = {
            "primary":  (ACCENT,       "#ffffff", ACCENT_HOVER),
            "success":  ("#166534",    SUCCESS,   "#15803d"),
            "danger":   ("#7f1d1d",    ERROR,     "#991b1b"),
            "warning":  ("#713f12",    WARNING,   "#854d0e"),
            "ghost":    (PANEL_BG,     TEXT_SECONDARY, BORDER),
            "secondary":(INPUT_BG,     TEXT_PRIMARY,   INPUT_BORDER),
        }
        bg, fg, hover = colors.get(style, colors["primary"])
        kw = dict(
            text=text, command=command,
            bg=bg, fg=fg,
            activebackground=hover, activeforeground=fg,
            relief="flat", cursor="hand2",
            font=(FONT_FAMILY, 9, "bold"),
            padx=14, pady=6,
            bd=0, highlightthickness=0,
        )
        if width:
            kw["width"] = width
        kw.update(kwargs)
        super().__init__(parent, **kw)
        self._bg, self._hover = bg, hover
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))


class LabeledEntry(tk.Frame):
    """A labeled input row with optional browse button."""
    def __init__(self, parent, label, var, browse=None, browse_dir=False, **kwargs):
        super().__init__(parent, bg=PANEL_BG, **kwargs)
        tk.Label(self, text=label, bg=PANEL_BG, fg=TEXT_SECONDARY,
                 font=(FONT_FAMILY, 9), anchor="w", width=26).pack(side="left")
        entry = tk.Entry(self, textvariable=var,
                         bg=INPUT_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=INPUT_BORDER, highlightcolor=ACCENT,
                         font=(FONT_FAMILY, 9), width=40)
        entry.pack(side="left", padx=(0, 6), ipady=4)
        if browse:
            def do_browse():
                if browse_dir:
                    p = filedialog.askdirectory()
                else:
                    p = filedialog.askopenfilename()
                if p:
                    var.set(p)
            StyledButton(self, "Browse", do_browse, style="ghost",
                         font=(FONT_FAMILY, 8)).pack(side="left")


class SectionHeader(tk.Label):
    def __init__(self, parent, text, **kwargs):
        super().__init__(parent, text=text, bg=PANEL_BG, fg=ACCENT,
                         font=(FONT_FAMILY, 10, "bold"),
                         pady=4, **kwargs)


class Separator(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BORDER, height=1, **kwargs)


class ToggleSwitch(tk.Frame):
    """A checkbox styled as a toggle row."""
    def __init__(self, parent, label, var, **kwargs):
        super().__init__(parent, bg=PANEL_BG, **kwargs)
        cb = tk.Checkbutton(self, text=label, variable=var,
                             bg=PANEL_BG, fg=TEXT_PRIMARY, selectcolor=ACCENT_DARK,
                             activebackground=PANEL_BG, activeforeground=TEXT_PRIMARY,
                             font=(FONT_FAMILY, 9), cursor="hand2",
                             relief="flat", bd=0)
        cb.pack(side="left")


class NumericEntry(tk.Frame):
    """Label + Entry constrained to numeric input, with optional range."""
    def __init__(self, parent, label, var, min_val=None, max_val=None,
                 float_mode=False, width=10, **kwargs):
        super().__init__(parent, bg=PANEL_BG, **kwargs)
        self.var = var
        self.float_mode = float_mode
        self.min_val = min_val
        self.max_val = max_val

        tk.Label(self, text=label, bg=PANEL_BG, fg=TEXT_SECONDARY,
                 font=(FONT_FAMILY, 9), anchor="w", width=26).pack(side="left")
        vcmd = (self.register(self._validate), "%P")
        self.entry = tk.Entry(self, textvariable=var,
                              validate="key", validatecommand=vcmd,
                              bg=INPUT_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                              relief="flat", bd=0, highlightthickness=1,
                              highlightbackground=INPUT_BORDER, highlightcolor=ACCENT,
                              font=(FONT_FAMILY, 9), width=width)
        self.entry.pack(side="left", ipady=4, padx=(0, 4))
        hint = ""
        if min_val is not None and max_val is not None:
            hint = f"  [{min_val}–{max_val}]"
        if hint:
            tk.Label(self, text=hint, bg=PANEL_BG, fg=TEXT_DIM,
                     font=(FONT_FAMILY, 8)).pack(side="left")

    def _validate(self, value):
        if value == "" or value == "-":
            return True
        try:
            float(value) if self.float_mode else int(value)
            return True
        except ValueError:
            return False


# ─────────────────────────────────────────────
#  CONFIG EDITOR PANEL
# ─────────────────────────────────────────────
class ConfigPanel(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=PANEL_BG, **kwargs)
        self.app = app
        self._vars = {}
        self._build()

    def _build(self):
        # Scrollable canvas
        canvas = tk.Canvas(self, bg=PANEL_BG, bd=0, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=PANEL_BG)
        inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_configure(e):
            canvas.itemconfig(inner_window, width=e.width)

        inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _scroll(e):
            # Fires exactly once per physical scroll tick via bind_all
            canvas.yview_scroll(-1 * (e.delta // 120), "units")

        def _enable_scroll(e):
            canvas.bind_all("<MouseWheel>", _scroll)

        def _disable_scroll(e):
            canvas.unbind_all("<MouseWheel>")

        # Only capture scroll events while the mouse is inside this panel
        canvas.bind("<Enter>", _enable_scroll)
        canvas.bind("<Leave>", _disable_scroll)
        inner.bind("<Enter>", _enable_scroll)
        inner.bind("<Leave>", _disable_scroll)

        # Two pack-kwargs variants: section headers get extra top padding, rows get standard
        pad     = {"padx": 16, "pady": 3,       "fill": "x"}   # regular rows
        sec_pad = {"padx": 16, "pady": (16, 2), "fill": "x"}   # section headers

        # ── Paths ──────────────────────────────
        SectionHeader(inner, "📁  Paths").pack(**{**sec_pad, "pady": (12, 2)})
        Separator(inner).pack(fill="x", padx=16, pady=(0, 8))

        v = tk.StringVar(); self._vars["paths.projectRoot"] = v
        LabeledEntry(inner, "Project Root", v, browse=True, browse_dir=True).pack(**pad)

        v = tk.StringVar(); self._vars["paths.blenderExecutable"] = v
        LabeledEntry(inner, "Blender Executable", v, browse=True).pack(**pad)

        # ── Folders ────────────────────────────
        SectionHeader(inner, "📂  Folder Structure").pack(**sec_pad)
        Separator(inner).pack(fill="x", padx=16, pady=(0, 8))

        folder_fields = [
            ("gltfExport",        "GLTF Export Folder"),
            ("modelLib",          "Model Library Folder"),
            ("modelLibTextures",  "Model Lib Textures"),
            ("batchFbxOutput",    "Batch FBX Output"),
            ("mergedOutput",      "Merged Output Folder"),
        ]
        for key, label in folder_fields:
            v = tk.StringVar(); self._vars[f"folders.{key}"] = v
            LabeledEntry(inner, label, v).pack(**pad)

        # ── Scripts ────────────────────────────
        SectionHeader(inner, "📜  Script Files").pack(**sec_pad)
        Separator(inner).pack(fill="x", padx=16, pady=(0, 8))

        script_fields = [
            ("mergeGltfBatchOptimized", "Batch Merge Script"),
            ("mergeFinalFbx",           "Final Merge Script"),
            ("processGltfParallel",     "Parallel Process Script"),
            ("runFullPipeline",         "Full Pipeline Script"),
        ]
        for key, label in script_fields:
            v = tk.StringVar(); self._vars[f"scripts.{key}"] = v
            LabeledEntry(inner, label, v).pack(**pad)

        # ── Output ─────────────────────────────
        SectionHeader(inner, "💾  Output Settings").pack(**sec_pad)
        Separator(inner).pack(fill="x", padx=16, pady=(0, 8))

        v = tk.StringVar(); self._vars["output.mergedFbxName"] = v
        LabeledEntry(inner, "Merged FBX Name", v).pack(**pad)

        # ── Processing ─────────────────────────
        SectionHeader(inner, "⚙️  Processing").pack(**sec_pad)
        Separator(inner).pack(fill="x", padx=16, pady=(0, 8))

        v = tk.IntVar(); self._vars["processing.maxParallelBlenderInstances"] = v
        NumericEntry(inner, "Max Parallel Instances", v, 1, 64).pack(**pad)

        v = tk.IntVar(); self._vars["processing.processCheckIntervalMs"] = v
        NumericEntry(inner, "Process Check Interval (ms)", v, 50, 5000).pack(**pad)

        v = tk.IntVar(); self._vars["processing.defaultFilesPerBatch"] = v
        NumericEntry(inner, "Default Files Per Batch", v, 1, 200).pack(**pad)

        v = tk.DoubleVar(); self._vars["processing.defaultDecimateRatio"] = v
        NumericEntry(inner, "Default Decimate Ratio", v, 0.01, 1.0,
                     float_mode=True, width=8).pack(**pad)

        v = tk.BooleanVar(); self._vars["processing.cleanupSubfolders"] = v
        ToggleSwitch(inner, "Clean Up Empty Subfolders After Consolidation", v).pack(**pad)

        # ── Optimization ───────────────────────
        SectionHeader(inner, "🔧  Optimization").pack(**sec_pad)
        Separator(inner).pack(fill="x", padx=16, pady=(0, 8))

        v = tk.BooleanVar(); self._vars["optimization.enableDecimation"] = v
        ToggleSwitch(inner, "Enable Mesh Decimation", v).pack(**pad)

        v = tk.BooleanVar(); self._vars["optimization.enableNormalBaking"] = v
        ToggleSwitch(inner, "Enable Normal Map Baking", v).pack(**pad)

        v = tk.IntVar(); self._vars["optimization.normalMapResolution"] = v
        NumericEntry(inner, "Normal Map Resolution (px)", v, 256, 8192).pack(**pad)

        v = tk.DoubleVar(); self._vars["optimization.bakeCageExtrusion"] = v
        NumericEntry(inner, "Bake Cage Extrusion", v, 0.0, 10.0,
                     float_mode=True, width=8).pack(**pad)

        v = tk.DoubleVar(); self._vars["optimization.bakeMaxRayDistance"] = v
        NumericEntry(inner, "Bake Max Ray Distance", v, 0.0, 100.0,
                     float_mode=True, width=8).pack(**pad)

        # ── Options ────────────────────────────
        SectionHeader(inner, "🔀  Options").pack(**sec_pad)
        Separator(inner).pack(fill="x", padx=16, pady=(0, 8))

        bool_options = [
            ("options.cleanOutputFolders",     "Clean Output Folders Before Run"),
            ("options.verboseLogging",         "Verbose Logging"),
            ("options.saveBatchLogs",          "Save Batch Log Files"),
            ("options.removeHighPolyAfterBake","Remove High-Poly Mesh After Baking"),
        ]
        for key, label in bool_options:
            v = tk.BooleanVar(); self._vars[key] = v
            ToggleSwitch(inner, label, v).pack(**pad)

        # ── Quality Presets ────────────────────
        SectionHeader(inner, "⭐  Quality Presets").pack(**sec_pad)
        Separator(inner).pack(fill="x", padx=16, pady=(0, 8))

        preset_names = ["ultra_high", "high", "medium", "low", "very_low"]
        preset_labels = ["Ultra High", "High", "Medium", "Low", "Very Low"]

        for preset, label in zip(preset_names, preset_labels):
            row = tk.Frame(inner, bg=PANEL_BG)
            row.pack(fill="x", padx=16, pady=2)

            tk.Label(row, text=label, bg=PANEL_BG, fg=TEXT_PRIMARY,
                     font=(FONT_FAMILY, 9, "bold"), width=12, anchor="w").pack(side="left")

            for sub_key, sub_label, fm, w in [
                ("decimateRatio",      "Ratio",   True,  7),
                ("filesPerBatch",      "Batch",   False, 5),
                ("normalMapResolution","Res (px)", False, 7),
            ]:
                tk.Label(row, text=sub_label + ":", bg=PANEL_BG, fg=TEXT_DIM,
                         font=(FONT_FAMILY, 8)).pack(side="left", padx=(8, 2))
                var_key = f"quality.presets.{preset}.{sub_key}"
                v = tk.DoubleVar() if fm else tk.IntVar()
                self._vars[var_key] = v
                e = tk.Entry(row, textvariable=v,
                             bg=INPUT_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                             relief="flat", bd=0, highlightthickness=1,
                             highlightbackground=INPUT_BORDER, highlightcolor=ACCENT,
                             font=(FONT_FAMILY, 9), width=w)
                e.pack(side="left", ipady=3)

        # ── Bottom Padding ─────────────────────
        tk.Frame(inner, bg=PANEL_BG, height=20).pack()

    def load_from_config(self, cfg: dict):
        """Populate all widgets from a config dict."""
        def _set(key_path, value):
            if key_path in self._vars:
                try:
                    self._vars[key_path].set(value)
                except Exception:
                    pass

        def _walk(d, prefix=""):
            for k, v in d.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    _walk(v, full)
                else:
                    _set(full, v)

        _walk(cfg)

    def collect_config(self) -> dict:
        """Build config dict from all widget values."""
        cfg = copy.deepcopy(DEFAULT_CONFIG)

        def _set_nested(d, keys, value):
            for key in keys[:-1]:
                d = d.setdefault(key, {})
            d[keys[-1]] = value

        for key_path, var in self._vars.items():
            try:
                raw = var.get()
                # Convert types
                if isinstance(var, tk.BooleanVar):
                    value = bool(raw)
                elif isinstance(var, tk.IntVar):
                    value = int(raw) if raw != "" else 0
                elif isinstance(var, tk.DoubleVar):
                    value = float(raw) if raw != "" else 0.0
                else:
                    value = str(raw)
                _set_nested(cfg, key_path.split("."), value)
            except Exception:
                pass

        return cfg


# ─────────────────────────────────────────────
#  PIPELINE RUNNER PANEL
# ─────────────────────────────────────────────
class PipelinePanel(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=DARK_BG, **kwargs)
        self.app = app
        self._process = None
        self._thread = None
        self._reader_thread = None
        self._log_queue = queue.Queue()
        self._running = False
        self._start_time = None
        self._timer_id = None

        self._build()
        self._poll_queue()

    def _build(self):
        # ── Top bar ────────────────────────────
        topbar = tk.Frame(self, bg=SIDEBAR_BG, pady=10)
        topbar.pack(fill="x")

        tk.Label(topbar, text="🚀  Pipeline Runner", bg=SIDEBAR_BG, fg=TEXT_PRIMARY,
                 font=(FONT_FAMILY, 13, "bold")).pack(side="left", padx=16)

        self._elapsed_label = tk.Label(topbar, text="", bg=SIDEBAR_BG, fg=TEXT_DIM,
                                        font=(FONT_MONO, 10))
        self._elapsed_label.pack(side="left", padx=12)

        # Status indicator
        self._status_dot = tk.Label(topbar, text="●", bg=SIDEBAR_BG, fg=TEXT_DIM,
                                     font=(FONT_FAMILY, 16))
        self._status_dot.pack(side="right", padx=6)
        self._status_label = tk.Label(topbar, text="IDLE", bg=SIDEBAR_BG, fg=TEXT_DIM,
                                       font=(FONT_FAMILY, 9, "bold"))
        self._status_label.pack(side="right")

        # ── Options bar ────────────────────────
        opts = tk.Frame(self, bg=PANEL_BG, padx=16, pady=10)
        opts.pack(fill="x")

        tk.Label(opts, text="Run Options:", bg=PANEL_BG, fg=TEXT_SECONDARY,
                 font=(FONT_FAMILY, 9, "bold")).pack(side="left", padx=(0, 14))

        self._skip_batch      = tk.BooleanVar()
        self._skip_texture    = tk.BooleanVar()
        self._only_merge      = tk.BooleanVar()

        for var, label in [
            (self._skip_batch,   "Skip Batch Processing"),
            (self._skip_texture, "Skip Texture Consolidation"),
            (self._only_merge,   "Only Final Merge"),
        ]:
            cb = tk.Checkbutton(opts, text=label, variable=var,
                                 bg=PANEL_BG, fg=TEXT_PRIMARY,
                                 selectcolor=ACCENT_DARK,
                                 activebackground=PANEL_BG,
                                 activeforeground=TEXT_PRIMARY,
                                 font=(FONT_FAMILY, 9), relief="flat", cursor="hand2")
            cb.pack(side="left", padx=8)

        # Override fields
        tk.Label(opts, text="|", bg=PANEL_BG, fg=BORDER).pack(side="left", padx=6)

        tk.Label(opts, text="Files/Batch:", bg=PANEL_BG, fg=TEXT_SECONDARY,
                 font=(FONT_FAMILY, 9)).pack(side="left", padx=(0, 3))
        self._files_per_batch = tk.StringVar(value="")
        tk.Entry(opts, textvariable=self._files_per_batch, width=5,
                 bg=INPUT_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                 relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=INPUT_BORDER, highlightcolor=ACCENT,
                 font=(FONT_FAMILY, 9)).pack(side="left", ipady=3, padx=(0, 10))

        tk.Label(opts, text="Decimate:", bg=PANEL_BG, fg=TEXT_SECONDARY,
                 font=(FONT_FAMILY, 9)).pack(side="left", padx=(0, 3))
        self._decimate_ratio = tk.StringVar(value="")
        tk.Entry(opts, textvariable=self._decimate_ratio, width=5,
                 bg=INPUT_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                 relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=INPUT_BORDER, highlightcolor=ACCENT,
                 font=(FONT_FAMILY, 9)).pack(side="left", ipady=3)

        # ── Quick preset bar ───────────────────
        presets_bar = tk.Frame(self, bg=DARK_BG, padx=16, pady=6)
        presets_bar.pack(fill="x")

        tk.Label(presets_bar, text="Quick Preset:", bg=DARK_BG, fg=TEXT_DIM,
                 font=(FONT_FAMILY, 9)).pack(side="left", padx=(0, 8))

        for preset_name, label in [
            ("ultra_high", "Ultra High"),
            ("high",       "High"),
            ("medium",     "Medium"),
            ("low",        "Low"),
            ("very_low",   "Very Low"),
        ]:
            StyledButton(presets_bar, label, lambda p=preset_name: self._apply_preset(p),
                         style="ghost", font=(FONT_FAMILY, 8), padx=8, pady=3).pack(
                side="left", padx=3)

        # ── Action buttons ─────────────────────
        actions = tk.Frame(self, bg=DARK_BG, padx=16, pady=8)
        actions.pack(fill="x")

        self._run_btn = StyledButton(actions, "▶  Run Pipeline",
                                     self._run_pipeline, style="success")
        self._run_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = StyledButton(actions, "⏹  Stop",
                                      self._stop_pipeline, style="danger")
        self._stop_btn.pack(side="left", padx=(0, 8))
        self._stop_btn.config(state="disabled")

        StyledButton(actions, "🗑  Clear Log", self._clear_console,
                     style="ghost").pack(side="left", padx=(0, 8))

        StyledButton(actions, "💾  Save Log", self._save_log,
                     style="secondary").pack(side="left")

        self._config_path_var = tk.StringVar(value="config.json")
        tk.Label(actions, text="Config:", bg=DARK_BG, fg=TEXT_DIM,
                 font=(FONT_FAMILY, 9)).pack(side="right", padx=(8, 3))
        tk.Entry(actions, textvariable=self._config_path_var, width=22,
                 bg=INPUT_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                 relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=INPUT_BORDER, highlightcolor=ACCENT,
                 font=(FONT_FAMILY, 9)).pack(side="right", ipady=3)
        tk.Label(actions, text="Using:", bg=DARK_BG, fg=TEXT_DIM,
                 font=(FONT_FAMILY, 8)).pack(side="right", padx=(0, 3))

        # ── Progress bar ───────────────────────
        prog_frame = tk.Frame(self, bg=DARK_BG, padx=16, pady=0)
        prog_frame.pack(fill="x")

        self._progress_var = tk.DoubleVar(value=0)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Pipeline.Horizontal.TProgressbar",
                         troughcolor=INPUT_BG, background=ACCENT,
                         darkcolor=ACCENT, lightcolor=ACCENT,
                         bordercolor=DARK_BG, thickness=6)
        self._progress = ttk.Progressbar(prog_frame,
                                          variable=self._progress_var,
                                          style="Pipeline.Horizontal.TProgressbar",
                                          mode="indeterminate")
        self._progress.pack(fill="x", pady=4)

        # ── Console ────────────────────────────
        console_header = tk.Frame(self, bg=CONSOLE_BG, padx=12, pady=6)
        console_header.pack(fill="x")

        tk.Label(console_header, text="Console Output", bg=CONSOLE_BG, fg=TEXT_DIM,
                 font=(FONT_FAMILY, 9, "bold")).pack(side="left")
        self._line_count_label = tk.Label(console_header, text="0 lines",
                                           bg=CONSOLE_BG, fg=TEXT_DIM,
                                           font=(FONT_MONO, 8))
        self._line_count_label.pack(side="right")

        self._console = scrolledtext.ScrolledText(
            self, bg=CONSOLE_BG, fg=CONSOLE_FG,
            font=(FONT_MONO, 9), wrap="word",
            relief="flat", bd=0,
            state="disabled",
            insertbackground=CONSOLE_FG,
        )
        self._console.pack(fill="both", expand=True, padx=0, pady=0)

        # Color tags for console
        self._console.tag_config("info",    foreground=INFO)
        self._console.tag_config("success", foreground=SUCCESS)
        self._console.tag_config("warning", foreground=WARNING)
        self._console.tag_config("error",   foreground=ERROR)
        self._console.tag_config("dim",     foreground=TEXT_DIM)
        self._console.tag_config("accent",  foreground=ACCENT)
        self._console.tag_config("time",    foreground=TEXT_DIM)
        self._console.tag_config("normal",  foreground=CONSOLE_FG)

    # ── Preset Application ─────────────────────
    def _apply_preset(self, preset_name):
        cfg = self.app.current_config
        preset = cfg.get("quality", {}).get("presets", {}).get(preset_name, {})
        if preset:
            self._files_per_batch.set(str(preset.get("filesPerBatch", "")))
            self._decimate_ratio.set(str(preset.get("decimateRatio", "")))
            self._log(f"Applied preset: {preset_name}", "accent")

    # ── Console Helpers ────────────────────────
    def _classify_line(self, line: str) -> str:
        l = line.lower()
        if any(x in l for x in ["error", "failed", "exception", "traceback", "exit code"]):
            return "error"
        if any(x in l for x in ["warning", "warn", "not found", "skipped"]):
            return "warning"
        if any(x in l for x in ["done", "complete", "success", "finished", "merged"]):
            return "success"
        if any(x in l for x in ["step", "starting", "processing", "importing", "exporting"]):
            return "info"
        if line.startswith("=") or line.startswith("-"):
            return "accent"
        return "normal"

    def _log(self, text: str, tag: str = "normal"):
        self._console.config(state="normal")
        ts = f"[{now_str()}] "
        self._console.insert("end", ts, "time")
        self._console.insert("end", text + "\n", tag)
        self._console.see("end")
        self._console.config(state="disabled")
        lines = int(self._console.index("end-1c").split(".")[0])
        self._line_count_label.config(text=f"{lines:,} lines")

    def _clear_console(self):
        self._console.config(state="normal")
        self._console.delete("1.0", "end")
        self._console.config(state="disabled")
        self._line_count_label.config(text="0 lines")

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile=f"pipeline_log_{datetime.now():%Y%m%d_%H%M%S}.txt"
        )
        if path:
            content = self._console.get("1.0", "end")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._log(f"Log saved to: {path}", "success")

    # ── Status updates ─────────────────────────
    def _set_status(self, label: str, color: str):
        self._status_label.config(text=label, fg=color)
        self._status_dot.config(fg=color)

    def _update_timer(self):
        if self._running and self._start_time:
            elapsed = time.time() - self._start_time
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            s = int(elapsed % 60)
            self._elapsed_label.config(
                text=f"Elapsed: {h:02d}:{m:02d}:{s:02d}", fg=TEXT_SECONDARY)
            self._timer_id = self.after(1000, self._update_timer)

    # ── Queue poller ───────────────────────────
    def _poll_queue(self):
        try:
            while True:
                item = self._log_queue.get_nowait()
                if item is None:
                    # Process finished
                    self._on_pipeline_finished()
                    break
                else:
                    tag = self._classify_line(item)
                    self._log(item.rstrip(), tag)
        except queue.Empty:
            pass
        self.after(50, self._poll_queue)

    # ── Pipeline Control ───────────────────────
    def _build_command(self) -> list:
        cfg = self.app.current_config
        project_root = cfg["paths"]["projectRoot"]
        pipeline_script = os.path.join(
            project_root, cfg["scripts"]["runFullPipeline"])
        config_path = self._config_path_var.get() or "config.json"

        files_per_batch = self._files_per_batch.get().strip()
        decimate = self._decimate_ratio.get().strip()

        if not files_per_batch:
            files_per_batch = str(cfg["processing"]["defaultFilesPerBatch"])
        if not decimate:
            decimate = str(cfg["processing"]["defaultDecimateRatio"])

        cmd = [
            "powershell.exe", "-ExecutionPolicy", "Bypass",
            "-File", pipeline_script,
            "-ConfigPath", config_path,
            "-FilesPerBatch", files_per_batch,
            "-DecimateRatio", decimate,
        ]
        if self._skip_batch.get():
            cmd.append("-SkipBatchProcessing")
        if self._skip_texture.get():
            cmd.append("-SkipTextureConsolidation")
        if self._only_merge.get():
            cmd.append("-OnlyFinalMerge")

        return cmd

    def _run_pipeline(self):
        if self._running:
            return

        # Auto-save config first
        self.app.save_config_silently()

        cmd = self._build_command()

        self._running = True
        self._start_time = time.time()
        self._run_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._set_status("RUNNING", SUCCESS)
        self._progress.config(mode="indeterminate")
        self._progress.start(12)

        self._log("=" * 60, "accent")
        self._log(f"Pipeline started", "success")
        self._log(f"Command: {' '.join(cmd)}", "dim")
        self._log("=" * 60, "accent")

        self._update_timer()

        self._thread = threading.Thread(target=self._pipeline_worker,
                                         args=(cmd,), daemon=True)
        self._thread.start()

    def _pipeline_worker(self, cmd: list):
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW
                    if sys.platform == "win32" else 0
            )

            for line in iter(self._process.stdout.readline, ""):
                if line:
                    self._log_queue.put(line)

            self._process.wait()

        except FileNotFoundError as e:
            self._log_queue.put(f"ERROR: Could not start process: {e}")
        except Exception as e:
            self._log_queue.put(f"ERROR: {e}")
        finally:
            self._log_queue.put(None)  # Signal completion

    def _stop_pipeline(self):
        if self._process and self._process.poll() is None:
            self._log("Stopping pipeline (terminating process tree)...", "warning")
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T",
                                     "/PID", str(self._process.pid)],
                                    capture_output=True)
                else:
                    self._process.terminate()
            except Exception as e:
                self._log(f"Error stopping: {e}", "error")

    def _on_pipeline_finished(self):
        self._running = False
        self._progress.stop()
        self._progress.config(mode="determinate")
        self._progress_var.set(100)
        self._run_btn.config(state="normal")
        self._stop_btn.config(state="disabled")

        if self._timer_id:
            self.after_cancel(self._timer_id)

        exit_code = self._process.returncode if self._process else -1
        elapsed = time.time() - self._start_time if self._start_time else 0
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)

        self._log("=" * 60, "accent")
        if exit_code == 0:
            self._log(f"✅  Pipeline completed successfully", "success")
            self._set_status("COMPLETE", SUCCESS)
        else:
            self._log(f"❌  Pipeline exited with code {exit_code}", "error")
            self._set_status("FAILED", ERROR)

        self._log(f"Total time: {h:02d}:{m:02d}:{s:02d}", "info")
        self._log("=" * 60, "accent")
        self._elapsed_label.config(
            fg=SUCCESS if exit_code == 0 else ERROR)

    def update_config_path(self, path: str):
        self._config_path_var.set(path)


# ─────────────────────────────────────────────
#  BATCH MONITOR PANEL
# ─────────────────────────────────────────────
class MonitorPanel(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=PANEL_BG, **kwargs)
        self.app = app
        self._watch_thread = None
        self._watching = False
        self._watch_path = tk.StringVar()
        self._build()

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=SIDEBAR_BG, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📊  Batch Monitor", bg=SIDEBAR_BG, fg=TEXT_PRIMARY,
                 font=(FONT_FAMILY, 13, "bold")).pack(side="left", padx=16)

        # Watch dir row
        row = tk.Frame(self, bg=PANEL_BG, padx=16, pady=10)
        row.pack(fill="x")
        tk.Label(row, text="Watch Directory:", bg=PANEL_BG, fg=TEXT_SECONDARY,
                 font=(FONT_FAMILY, 9)).pack(side="left", padx=(0, 6))
        tk.Entry(row, textvariable=self._watch_path, width=45,
                 bg=INPUT_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                 relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=INPUT_BORDER, highlightcolor=ACCENT,
                 font=(FONT_FAMILY, 9)).pack(side="left", ipady=4, padx=(0, 6))

        def browse():
            p = filedialog.askdirectory()
            if p: self._watch_path.set(p)

        StyledButton(row, "Browse", browse, style="ghost").pack(side="left", padx=(0, 8))
        self._watch_btn = StyledButton(row, "▶ Watch", self._toggle_watch, style="primary")
        self._watch_btn.pack(side="left")

        self._refresh_btn = StyledButton(row, "↻ Refresh", self._refresh, style="secondary")
        self._refresh_btn.pack(side="left", padx=6)

        # Stats summary
        self._stats_frame = tk.Frame(self, bg=DARK_BG, padx=16, pady=10)
        self._stats_frame.pack(fill="x")

        self._stat_labels = {}
        stats_row = tk.Frame(self._stats_frame, bg=DARK_BG)
        stats_row.pack(fill="x")

        for key, label, color in [
            ("total",    "Total Files",  TEXT_SECONDARY),
            ("fbx",      "FBX Files",    SUCCESS),
            ("log",      "Log Files",    INFO),
            ("err",      "Error Logs",   ERROR),
            ("size",     "Total Size",   ACCENT),
        ]:
            box = tk.Frame(stats_row, bg=INPUT_BG, padx=14, pady=8,
                           highlightthickness=1, highlightbackground=BORDER)
            box.pack(side="left", padx=4)
            tk.Label(box, text=label, bg=INPUT_BG, fg=TEXT_DIM,
                     font=(FONT_FAMILY, 8)).pack()
            lbl = tk.Label(box, text="—", bg=INPUT_BG, fg=color,
                           font=(FONT_FAMILY, 14, "bold"))
            lbl.pack()
            self._stat_labels[key] = lbl

        # File list
        list_frame = tk.Frame(self, bg=PANEL_BG)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        cols = ("File", "Size", "Modified", "Status")
        self._tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=20)

        style = ttk.Style()
        style.configure("Monitor.Treeview",
                         background=INPUT_BG, foreground=TEXT_PRIMARY,
                         fieldbackground=INPUT_BG, bordercolor=BORDER,
                         rowheight=24, font=(FONT_FAMILY, 9))
        style.configure("Monitor.Treeview.Heading",
                         background=SIDEBAR_BG, foreground=ACCENT,
                         font=(FONT_FAMILY, 9, "bold"), relief="flat")
        style.map("Monitor.Treeview", background=[("selected", ACCENT_DARK)])
        self._tree.configure(style="Monitor.Treeview")

        for col, w in zip(cols, [280, 90, 160, 90]):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="w")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)

    def _refresh(self):
        path = self._watch_path.get()
        if not path or not os.path.isdir(path):
            messagebox.showwarning("Monitor", "Please select a valid directory.")
            return

        self._tree.delete(*self._tree.get_children())
        total_size = 0
        counts = {"fbx": 0, "log": 0, "err": 0, "total": 0}

        try:
            files = sorted(Path(path).iterdir(), key=lambda f: f.name)
            for f in files:
                if not f.is_file():
                    continue
                size = f.stat().st_size
                total_size += size
                modified = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                ext = f.suffix.lower()

                counts["total"] += 1
                if ext == ".fbx":
                    counts["fbx"] += 1
                    status = "✅ Ready"
                    tag = "fbx"
                elif ext == ".log":
                    counts["log"] += 1
                    status = "📋 Log"
                    tag = "log"
                elif ext == ".err":
                    counts["err"] += 1
                    status = "⚠ Error"
                    tag = "err"
                else:
                    status = "—"
                    tag = "other"

                size_str = (f"{size/1024/1024:.2f} MB" if size > 1024*1024
                            else f"{size/1024:.1f} KB")
                self._tree.insert("", "end", values=(f.name, size_str, modified, status))

        except Exception as e:
            messagebox.showerror("Monitor", f"Error reading directory:\n{e}")
            return

        # Update stats
        self._stat_labels["total"].config(text=str(counts["total"]))
        self._stat_labels["fbx"].config(text=str(counts["fbx"]))
        self._stat_labels["log"].config(text=str(counts["log"]))
        self._stat_labels["err"].config(text=str(counts["err"]))
        size_mb = total_size / 1024 / 1024
        size_str = (f"{size_mb/1024:.2f} GB" if size_mb > 1024
                    else f"{size_mb:.1f} MB")
        self._stat_labels["size"].config(text=size_str)

    def _toggle_watch(self):
        if not self._watching:
            self._watching = True
            self._watch_btn.config(text="⏹ Stop", bg="#7f1d1d")
            self._watch_thread = threading.Thread(target=self._watch_worker, daemon=True)
            self._watch_thread.start()
        else:
            self._watching = False
            self._watch_btn.config(text="▶ Watch", bg=ACCENT)

    def _watch_worker(self):
        while self._watching:
            self.after(0, self._refresh)
            time.sleep(3)

    def set_default_path(self, path: str):
        self._watch_path.set(path)


# ─────────────────────────────────────────────
#  MAIN APPLICATION
# ─────────────────────────────────────────────
class PipelineManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Google Earth → MSFS Pipeline Manager")
        self.geometry("1200x820")
        self.minsize(900, 600)
        self.configure(bg=DARK_BG)

        # ── Sharp text: tell Tk to use the system font renderer at native DPI
        # option_add forces all default fonts to a crisp, hinted variant.
        from tkinter import font as tkfont
        self.tk.call("tk", "scaling", self.winfo_fpixels("1i") / 72.0)
        default_font  = tkfont.nametofont("TkDefaultFont")
        text_font     = tkfont.nametofont("TkTextFont")
        fixed_font    = tkfont.nametofont("TkFixedFont")
        default_font.configure(family=FONT_FAMILY, size=9)
        text_font.configure(family=FONT_FAMILY,    size=9)
        fixed_font.configure(family=FONT_MONO,     size=9)
        self.option_add("*Font", default_font)

        self.current_config = copy.deepcopy(DEFAULT_CONFIG)
        self._config_path = tk.StringVar(value="config.json")

        # Style global ttk
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TNotebook", background=DARK_BG, borderwidth=0)
        style.configure("TNotebook.Tab",
                         background=SIDEBAR_BG, foreground=TEXT_DIM,
                         padding=(16, 8), font=(FONT_FAMILY, 10))
        style.map("TNotebook.Tab",
                   background=[("selected", PANEL_BG)],
                   foreground=[("selected", TEXT_PRIMARY)])
        style.configure("Vertical.TScrollbar",
                         troughcolor=DARK_BG, background=INPUT_BORDER,
                         arrowcolor=TEXT_DIM, borderwidth=0)

        self._build_titlebar()
        self._build_notebook()
        self._build_statusbar()

        # Load config if exists
        self._auto_load_config()

    # ── Title Bar ─────────────────────────────
    def _build_titlebar(self):
        bar = tk.Frame(self, bg=ACCENT_DARK, pady=6, padx=12)
        bar.pack(fill="x")

        tk.Label(bar, text="🌍  Google Earth → MSFS  |  Pipeline Manager",
                 bg=ACCENT_DARK, fg="#ffffff",
                 font=(FONT_FAMILY, 11, "bold")).pack(side="left")

        # Config file selector
        right = tk.Frame(bar, bg=ACCENT_DARK)
        right.pack(side="right")

        tk.Label(right, text="Config File:", bg=ACCENT_DARK, fg="#ddd",
                 font=(FONT_FAMILY, 9)).pack(side="left", padx=(0, 5))
        tk.Entry(right, textvariable=self._config_path, width=22,
                 bg=ACCENT, fg="#fff", insertbackground="#fff",
                 relief="flat", bd=0, highlightthickness=0,
                 font=(FONT_FAMILY, 9)).pack(side="left", ipady=3, padx=(0, 6))

        StyledButton(right, "Open", self._open_config,
                     style="secondary", font=(FONT_FAMILY, 8),
                     padx=8, pady=3).pack(side="left", padx=2)
        StyledButton(right, "Save", self._save_config,
                     style="primary", font=(FONT_FAMILY, 8),
                     padx=8, pady=3).pack(side="left", padx=2)
        StyledButton(right, "Save As", self._save_config_as,
                     style="ghost", font=(FONT_FAMILY, 8),
                     padx=8, pady=3).pack(side="left", padx=2)

    # ── Notebook ──────────────────────────────
    def _build_notebook(self):
        self._notebook = ttk.Notebook(self, style="TNotebook")
        self._notebook.pack(fill="both", expand=True, pady=(1, 0))

        self._config_panel = ConfigPanel(self._notebook, self)
        self._pipeline_panel = PipelinePanel(self._notebook, self)
        self._monitor_panel = MonitorPanel(self._notebook, self)

        self._notebook.add(self._config_panel,   text="⚙️  Configuration")
        self._notebook.add(self._pipeline_panel,  text="🚀  Pipeline Runner")
        self._notebook.add(self._monitor_panel,   text="📊  Batch Monitor")

    # ── Status Bar ────────────────────────────
    def _build_statusbar(self):
        bar = tk.Frame(self, bg=SIDEBAR_BG, pady=4, padx=12)
        bar.pack(fill="x", side="bottom")

        self._status_msg = tk.Label(bar, text="Ready", bg=SIDEBAR_BG, fg=TEXT_DIM,
                                     font=(FONT_FAMILY, 9))
        self._status_msg.pack(side="left")

        tk.Label(bar, text=f"Python {sys.version.split()[0]}",
                 bg=SIDEBAR_BG, fg=TEXT_DIM, font=(FONT_FAMILY, 9)).pack(side="right")

    def _set_status(self, msg: str, color: str = TEXT_DIM):
        self._status_msg.config(text=msg, fg=color)

    # ── Config I/O ────────────────────────────
    def _auto_load_config(self):
        """Try to load config.json from current directory on startup."""
        candidates = ["config.json",
                      os.path.join(os.path.dirname(__file__), "config.json")]
        for path in candidates:
            if os.path.isfile(path):
                self._load_config_from(path)
                return
        # Just populate defaults
        self._config_panel.load_from_config(self.current_config)
        self._set_status("Loaded default configuration (no config.json found)")

    def _load_config_from(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.current_config = deep_merge(DEFAULT_CONFIG, raw)
            self._config_panel.load_from_config(self.current_config)
            self._config_path.set(path)
            self._pipeline_panel.update_config_path(path)
            # Set monitor default path
            batch_dir = os.path.join(
                self.current_config["paths"]["projectRoot"],
                self.current_config["folders"]["batchFbxOutput"]
            )
            self._monitor_panel.set_default_path(batch_dir)
            self._set_status(f"Loaded: {path}", SUCCESS)
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load config:\n{e}")
            self._set_status(f"Load failed: {e}", ERROR)

    def _open_config(self):
        path = filedialog.askopenfilename(
            title="Open Config File",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if path:
            self._load_config_from(path)

    def _save_config(self, path=None):
        path = path or self._config_path.get()
        if not path:
            self._save_config_as()
            return
        try:
            cfg = self._config_panel.collect_config()
            self.current_config = cfg
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            self._set_status(f"Saved: {path}", SUCCESS)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save:\n{e}")
            self._set_status(f"Save failed: {e}", ERROR)

    def _save_config_as(self):
        path = filedialog.asksaveasfilename(
            title="Save Config As",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile="config.json"
        )
        if path:
            self._config_path.set(path)
            self._pipeline_panel.update_config_path(path)
            self._save_config(path)

    def save_config_silently(self):
        """Called by pipeline panel before run — saves without dialogs."""
        path = self._config_path.get()
        if path:
            try:
                cfg = self._config_panel.collect_config()
                self.current_config = cfg
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
                self._set_status(f"Config auto-saved to: {path}", INFO)
            except Exception:
                pass


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = PipelineManagerApp()

    # Set window icon if running on Windows
    try:
        app.iconbitmap(default="")
    except Exception:
        pass

    app.mainloop()