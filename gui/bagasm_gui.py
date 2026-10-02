#!/usr/bin/env python3
"""Desktop GUI for running the bagASM Nextflow pipeline and watching its
progress live. Requires ttkbootstrap (`pip install --user ttkbootstrap`)
for theming; everything else is standard library.

Usage:
    python3 gui/bagasm_gui.py
"""
import os
import queue
import re
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from tkinter import ttk as ttk_raw  # PanedWindow/Treeview/Scrollbar: plain
                                     # ttk widgets theme automatically once a
                                     # ttkbootstrap Style is active, and don't
                                     # need the bootstyle= convenience kwarg.

DEFAULT_THEME = "cyborg"
THEME_CHOICES = [
    "cyborg", "superhero", "darkly", "solar", "vapor",
    "flatly", "cosmo", "litera",
]


# ttkbootstrap's Linux HiDPI support (enable_high_dpi_awareness) is a no-op
# unless an explicit scaling factor is passed in -- confirmed by reading its
# source, it does NOT auto-detect anything on Linux, only on Windows. Left
# at its default, Tk renders as if the display were 96dpi. The system's own
# Xft.dpi here is 120, but 150 is used deliberately instead -- chosen after
# testing 300dpi live and finding it badly breaks the two-column layout
# (the form alone needed ~1940px, more than fits) -- 150 is a moderate,
# confirmed-to-fit boost past the system default, not a match to it.
TARGET_DPI = 150


def _detect_dpi_scaling():
    """Tk's scaling factor is pixels-per-point, and a point is 1/72 inch,
    so scaling = dpi / 72."""
    return TARGET_DPI / 72.0


def _find_laptop_monitor_position():
    """New windows default to opening on the primary monitor, which on this
    dual-monitor setup is the external 1920x1080 display -- but the user
    actually looks at this app on the laptop's own (higher-density) panel.
    xrandr names built-in laptop panels "eDP-*" by convention; find its
    offset and open there instead, with a small margin from its corner.
    Falls back to default WM placement (None) on any desktop without one,
    e.g. a workstation with no built-in display."""
    try:
        out = subprocess.run(
            ["xrandr", "--query"], capture_output=True, text=True, timeout=2
        ).stdout
        for line in out.splitlines():
            if line.startswith("eDP") and " connected" in line:
                m = re.search(r"\d+x\d+\+(\d+)\+(\d+)", line)
                if m:
                    return (int(m.group(1)) + 60, int(m.group(2)) + 60)
    except Exception:
        pass
    return None

# Nextflow prints one status line per process each time its counters change,
# e.g.:
#   [81/2788d4] FASTP (TEST)                   | 1 of 1 ✔
#   [skipped  ] GET_ORGANELLE_SETUP            | 1 of 1, stored: 1 ✔
#   [ec/cd16e7] QUALIMAP_BAMQC (TEST)          | 0 of 1
# The hash can be a real work-dir hash or the literal "skipped"/"-" tokens
# Nextflow uses for cached/not-yet-reached processes.
STATUS_RE = re.compile(
    r"^\[(?P<hash>[^\]]*)\]\s+(?P<name>\S+)(?:\s+\((?P<tag>[^)]*)\))?\s*\|\s*"
    r"(?P<done>\d+)\s+of\s+(?P<total>\d+)(?:,\s*(?P<extra>[\w\s:]+))?\s*(?P<check>✔)?\s*$"
)
FAILED_PROC_RE = re.compile(r"Error executing process\s*>\s*'([^']+)'")

PARAM_DEFAULTS = {
    "threads": "20",
    "species": "fungus_mt",
    "decontam_alcr_cutoff": "0.1",
    "decontam_sdr_cutoff": "0.1",
    "filtlong_min_length": "1000",
    "filtlong_keep_percent": "90",
    "ont_mode": "hq",
    "polish_rounds": "3",
}

STATUS_ICON = {
    "done": "done",
    "cached": "cached",
    "running": "running",
    "pending": "pending",
    "failed": "failed",
}

# Nextflow's plain-log renderer widens/narrows its process-name column as
# more processes join the printed table, and re-truncates names with a "…"
# to fit — the same process can appear fully spelled out in one reprint and
# ellipsized in the next. Canonicalizing against the pipeline's own known
# process names (including its DSL2 include-as aliases) collapses these
# back into one tracked row instead of two.
KNOWN_PROCESS_NAMES = [
    "ALIGN_LR_FOR_QC", "ALIGN_SR_FOR_QC", "CHLOMITO", "CHLOMITO_LR",
    "COMPLEASM", "COMPLEASM_LR", "DECONTAM_ORGANELLE_LR", "FASTP", "FILTLONG",
    "FINALIZE_MITOGENOME", "FINALIZE_MITOGENOME_LR", "FLYE",
    "GET_ORGANELLE_FROM_ASSEMBLY", "GET_ORGANELLE_FROM_ASSEMBLY_LR",
    "GET_ORGANELLE_FROM_READS", "GET_ORGANELLE_SETUP", "MEDAKA", "POLYPOLISH",
    "POLYPOLISH_LR", "QUALIMAP_BAMQC", "QUALIMAP_BAMQC_LR", "QUAST", "QUAST_LR",
    "RACON", "REDUNDANS", "RENAME_SORT", "RENAME_SORT_LR", "SPADES",
]


def canonicalize_name(name):
    if name in KNOWN_PROCESS_NAMES or "…" not in name:
        return name
    prefix, _, suffix = name.partition("…")
    matches = [n for n in KNOWN_PROCESS_NAMES if n.startswith(prefix) and n.endswith(suffix)]
    return matches[0] if len(matches) == 1 else name


def parse_status_line(line):
    m = STATUS_RE.match(line.strip())
    if not m:
        return None
    d = m.groupdict()
    return {
        "hash": d["hash"].strip(),
        "name": canonicalize_name(d["name"]),
        "tag": d["tag"] or "",
        "done": int(d["done"]),
        "total": int(d["total"]),
        "extra": (d["extra"] or "").strip(),
        "check": bool(d["check"]),
    }


def open_dialog_big(root, dialog_func, window_name, **kwargs):
    """tkinter's file/directory dialogs have no size parameter and default
    to a cramped ~400x250 window. Both are plain Tk toplevels internally
    (.__tk_filedialog for open/save, .__tk_choosedir for askdirectory),
    resizable via `wm geometry` like any other Tk window -- so schedule a
    resize for just after the dialog opens, since it blocks the caller.

    This sizes it to ~90% of the screen instead of maximizing it, because
    maximizing doesn't work here: Tk marks these dialogs `-type dialog` for
    the window manager, and confirmed empirically (this WM, and typically
    true elsewhere too) that WMs deliberately refuse both the maximize
    button and a programmatic `-zoomed`/`-fullscreen` request for
    dialog-type windows, even after overriding `-type` to `normal` post
    hoc -- the type is evidently latched at map time. Opening already
    near-fullscreen sidesteps needing maximize at all."""
    def resize():
        try:
            # Centering on winfo_screenwidth() would center across the
            # FULL X11 virtual root, which spans all connected monitors
            # combined on a multi-monitor setup (confirmed here: 4480px
            # against two 2560/1920-ish monitors) -- landing the dialog on
            # a monitor boundary or the wrong screen entirely. Centering on
            # the app window's own current position keeps it anchored to
            # wherever the app actually is.
            w, h = 1700, 1000
            root_x = root.winfo_x()
            root_y = root.winfo_y()
            root_w = root.winfo_width()
            root_h = root.winfo_height()
            x = root_x + (root_w - w) // 2
            y = root_y + (root_h - h) // 2
            root.tk.call("wm", "geometry", window_name, f"{w}x{h}+{x}+{y}")
        except tk.TclError:
            pass
    root.after(50, resize)
    return dialog_func(parent=root, **kwargs)


class ProcessTracker:
    """Keeps the latest known status of every process Nextflow has reported,
    in first-seen order, and the running total done/total across all of them."""

    def __init__(self):
        self._order = []
        self._state = {}
        self._failed = set()

    def update(self, parsed):
        name = parsed["name"]
        if name not in self._state:
            self._order.append(name)
        self._state[name] = parsed

    def mark_failed(self, name):
        self._failed.add(name)

    def rows(self):
        return [(name, self._state[name]) for name in self._order]

    def overall_fraction(self):
        done = sum(s["done"] for s in self._state.values())
        total = sum(s["total"] for s in self._state.values())
        return (done, total)

    def status_of(self, parsed):
        if parsed["name"] in self._failed:
            return "failed"
        if parsed["hash"] == "skipped" or "cached" in parsed["extra"] or "stored" in parsed["extra"]:
            return "cached"
        if parsed["done"] >= parsed["total"] and parsed["total"] > 0:
            return "done"
        if parsed["total"] > 0:
            return "running"
        return "pending"


class LabeledEntry(ttk.Frame):
    def __init__(self, parent, label, default="", width=30, browse=None, browse_multi=False):
        super().__init__(parent)
        ttk.Label(self, text=label, width=26, anchor="w").pack(side="left")
        self.var = tk.StringVar(value=default)
        entry = ttk.Entry(self, textvariable=self.var, width=width)
        entry.pack(side="left", fill="x", expand=True, padx=(4, 4))
        if browse == "file":
            ttk.Button(
                self, text="Browse", command=self._browse_file(browse_multi),
                bootstyle="secondary-outline",
            ).pack(side="left")
        elif browse == "dir":
            ttk.Button(
                self, text="Browse", command=self._browse_dir, bootstyle="secondary-outline"
            ).pack(side="left")

    def _browse_file(self, multi):
        def handler():
            root = self.winfo_toplevel()
            if multi:
                paths = open_dialog_big(
                    root, filedialog.askopenfilenames, ".__tk_filedialog", title="Select file(s)"
                )
                if paths:
                    existing = self.var.get().strip()
                    joined = ",".join(paths)
                    self.var.set(f"{existing},{joined}" if existing else joined)
            else:
                path = open_dialog_big(
                    root, filedialog.askopenfilename, ".__tk_filedialog", title="Select file"
                )
                if path:
                    self.var.set(path)
        return handler

    def _browse_dir(self):
        root = self.winfo_toplevel()
        path = open_dialog_big(root, filedialog.askdirectory, ".__tk_choosedir", title="Select directory")
        if path:
            self.var.set(path)

    def get(self):
        return self.var.get().strip()

    def clear(self):
        self.var.set("")


class VerticalScrolledFrame(ttk.Frame):
    """A ttk.Frame with a vertical scrollbar around a scrollable inner frame."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk_raw.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)

        self.inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas = canvas

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Without this, the frame auto-sizes to its packed children (the
        # canvas), which auto-sizes to nothing in particular -- pinning the
        # frame to its configured width/height is what makes the ttk
        # PanedWindow actually honor that size for the pane at add() time
        # (ttk.PanedWindow, unlike the classic tk one, takes no explicit
        # width= at add() time; it uses the child's reqwidth instead).
        self.pack_propagate(False)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def sync_bg(self, color):
        self._canvas.configure(background=color)


BASE_FONT_SIZE = 13
LEFT_PANE_WIDTH = 1120


class BagASMGui(ttk.Window):
    def __init__(self):
        super().__init__(
            title="bagASM — pipeline runner",
            themename=DEFAULT_THEME,
            iconphoto=str(Path(__file__).resolve().parent / "icon.png"),
            size=(2450, 1300),
            position=_find_laptop_monitor_position(),
            minsize=(1700, 850),
            scaling=_detect_dpi_scaling(),
        )

        self._scale_fonts()

        self.pipeline_dir = Path(__file__).resolve().parent.parent
        self.proc = None
        self.log_queue = queue.Queue()
        self.tracker = ProcessTracker()
        self.tree_rows = {}
        self.running = False

        self._build_layout()
        self._apply_theme_colors()
        self._zoomed = False
        self.bind("<F11>", self._toggle_fullscreen)
        self.after(100, self._poll_log_queue)

    def _toggle_fullscreen(self, event=None):
        # state('zoomed') isn't supported on every X11 window manager (confirmed
        # missing here); attributes('-zoomed', ...) is the portable equivalent.
        self._zoomed = not self._zoomed
        self.attributes("-zoomed", self._zoomed)

    def _scale_fonts(self):
        # Every ttk style in this theme falls back to these named fonts
        # rather than a hardcoded size (confirmed empirically: style.lookup
        # returns no font override for TButton/TLabel/Treeview/etc.), and
        # even plain tk.Text defaults to TkDefaultFont — so bumping these
        # few named fonts scales the entire UI in one place.
        import tkinter.font as tkfont
        for name, size, weight in [
            ("TkDefaultFont", BASE_FONT_SIZE, "normal"),
            ("TkTextFont", BASE_FONT_SIZE, "normal"),
            ("TkHeadingFont", BASE_FONT_SIZE, "bold"),
            ("TkMenuFont", BASE_FONT_SIZE, "normal"),
            ("TkCaptionFont", BASE_FONT_SIZE, "bold"),
        ]:
            tkfont.nametofont(name).configure(size=size, weight=weight)
        tkfont.nametofont("TkFixedFont").configure(size=BASE_FONT_SIZE - 1)
        # Treeview's default row height is computed from the font that was
        # active when ttkbootstrap first built the style, so it needs a
        # manual bump to match the new, larger font instead of clipping rows.
        self.style.configure("Treeview", rowheight=int(BASE_FONT_SIZE * 2.4))

    # ---------------------------------------------------------------- layout
    def _build_layout(self):
        header = ttk.Frame(self, padding=(16, 12, 16, 4))
        header.pack(fill="x")
        title_row = ttk.Frame(header)
        title_row.pack(fill="x")
        ttk.Label(
            title_row, text="bagASM", font=("", 22, "bold"), bootstyle="success"
        ).pack(side="left")
        ttk.Label(
            title_row, text="  a User-Friendly Genome Assembly Pipeline",
            font=("", 11),
        ).pack(side="left", padx=(4, 0))

        theme_row = ttk.Frame(title_row)
        theme_row.pack(side="right")
        ttk.Label(theme_row, text="Theme").pack(side="left", padx=(0, 6))
        self.v_theme = tk.StringVar(value=DEFAULT_THEME)
        theme_box = ttk.Combobox(
            theme_row, textvariable=self.v_theme, values=THEME_CHOICES,
            state="readonly", width=12,
        )
        theme_box.pack(side="left")
        theme_box.bind("<<ComboboxSelected>>", self._on_theme_change)

        ttk.Separator(self).pack(fill="x", padx=16)

        paned = ttk_raw.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        left = VerticalScrolledFrame(paned, width=LEFT_PANE_WIDTH, height=800)
        # Tk's PanedWindow only honors an initial pane size passed to add()
        # itself (width=), not the child widget's own requested size, and
        # not reliably via a delayed sashpos() call either (both were tried
        # and produced a collapsed 1px pane) -- width= here is what actually
        # works.
        paned.add(left, weight=1)
        self._left_scroll = left
        self._build_form(left.inner)

        right = ttk.Frame(paned)
        paned.add(right, weight=2)
        self._build_progress(right)

    def _build_form(self, parent):
        pad = {"padx": 8, "pady": 6}

        pipe = ttk.Labelframe(parent, text="  Pipeline location", bootstyle="info")
        pipe.pack(fill="x", **pad)
        self.f_pipeline_dir = LabeledEntry(
            pipe, "main.nf directory", str(self.pipeline_dir), browse="dir"
        )
        self.f_pipeline_dir.pack(fill="x", padx=6, pady=4)

        env = ttk.Labelframe(parent, text="  Nextflow launch environment", bootstyle="info")
        env.pack(fill="x", **pad)
        self.f_nxf_ver = LabeledEntry(env, "NXF_VER", os.environ.get("NXF_VER", "25.04.6"))
        self.f_nxf_ver.pack(fill="x", padx=6, pady=2)
        self.f_java_home = LabeledEntry(
            env, "JAVA_HOME", os.environ.get("JAVA_HOME", "/usr/lib/jvm/java-21-openjdk-amd64")
        )
        self.f_java_home.pack(fill="x", padx=6, pady=2)

        req = ttk.Labelframe(parent, text="  Required", bootstyle="success")
        req.pack(fill="x", **pad)
        self.f_strain = LabeledEntry(req, "Strain / sample ID")
        self.f_strain.pack(fill="x", padx=6, pady=2)
        self.f_outdir = LabeledEntry(req, "Output directory", browse="dir")
        self.f_outdir.pack(fill="x", padx=6, pady=2)

        sr = ttk.Labelframe(
            parent, text="  Short reads (fill for short-read or hybrid mode)", bootstyle="primary"
        )
        sr.pack(fill="x", **pad)
        self.f_r1 = LabeledEntry(sr, "R1 (comma-sep for multi-lane)", browse="file", browse_multi=True)
        self.f_r1.pack(fill="x", padx=6, pady=2)
        self.f_r2 = LabeledEntry(sr, "R2 (comma-sep for multi-lane)", browse="file", browse_multi=True)
        self.f_r2.pack(fill="x", padx=6, pady=2)

        lr = ttk.Labelframe(
            parent, text="  Long reads (fill for long-read or hybrid mode)", bootstyle="primary"
        )
        lr.pack(fill="x", **pad)
        self.f_lr = LabeledEntry(lr, "LR (comma-sep for multi-lane)", browse="file", browse_multi=True)
        self.f_lr.pack(fill="x", padx=6, pady=2)
        lr_type_row = ttk.Frame(lr)
        lr_type_row.pack(fill="x", padx=6, pady=2)
        ttk.Label(lr_type_row, text="lr_type", width=26, anchor="w").pack(side="left")
        self.v_lr_type = tk.StringVar(value="")
        ttk.Combobox(
            lr_type_row, textvariable=self.v_lr_type,
            values=["", "ont", "pacbio-clr", "pacbio-hifi"], state="readonly", width=15,
        ).pack(side="left")

        run = ttk.Labelframe(parent, text="  Run settings", bootstyle="warning")
        run.pack(fill="x", **pad)
        self.f_threads = LabeledEntry(run, "Threads", PARAM_DEFAULTS["threads"])
        self.f_threads.pack(fill="x", padx=6, pady=2)
        self.f_max_memory = LabeledEntry(run, "Max memory (e.g. 50GB)")
        self.f_max_memory.pack(fill="x", padx=6, pady=2)
        prof_row = ttk.Frame(run)
        prof_row.pack(fill="x", padx=6, pady=2)
        ttk.Label(prof_row, text="Execution profile", width=26, anchor="w").pack(side="left")
        self.v_profile = tk.StringVar(value="standard")
        ttk.Combobox(
            prof_row, textvariable=self.v_profile,
            values=["standard", "slurm", "sge"], state="readonly", width=15,
        ).pack(side="left")
        self.v_resume = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            run, text="-resume (reuse cached results)", variable=self.v_resume,
            bootstyle="round-toggle",
        ).pack(anchor="w", padx=6, pady=4)
        self.v_stub = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            run, text="-stub-run (dry run, no real computation, for testing)",
            variable=self.v_stub, bootstyle="round-toggle",
        ).pack(anchor="w", padx=6, pady=4)

        self._advanced_visible = False
        self.adv_toggle_btn = ttk.Button(
            parent, text="Show advanced options", command=self._toggle_advanced,
            bootstyle="info-outline",
        )
        self.adv_toggle_btn.pack(fill="x", padx=8, pady=(8, 2))
        self.adv_frame = ttk.Frame(parent)
        self._build_advanced(self.adv_frame)

    def _toggle_advanced(self):
        self._advanced_visible = not self._advanced_visible
        if self._advanced_visible:
            self.adv_frame.pack(fill="x", padx=0, pady=0)
            self.adv_toggle_btn.configure(text="Hide advanced options")
        else:
            self.adv_frame.pack_forget()
            self.adv_toggle_btn.configure(text="Show advanced options")

    def _build_advanced(self, parent):
        pad = {"padx": 8, "pady": 6}

        org = ttk.Labelframe(parent, text="  Organelle extraction / decontamination", bootstyle="secondary")
        org.pack(fill="x", **pad)
        self.f_species = LabeledEntry(org, "species (GetOrganelle -F)", PARAM_DEFAULTS["species"])
        self.f_species.pack(fill="x", padx=6, pady=2)
        self.v_skip_decontam = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            org, text="skip_decontam (all modes)", variable=self.v_skip_decontam,
            bootstyle="round-toggle",
        ).pack(anchor="w", padx=6, pady=4)
        self.f_decontam_alcr = LabeledEntry(
            org, "decontam_alcr_cutoff", PARAM_DEFAULTS["decontam_alcr_cutoff"]
        )
        self.f_decontam_alcr.pack(fill="x", padx=6, pady=2)
        self.f_decontam_sdr = LabeledEntry(
            org, "decontam_sdr_cutoff", PARAM_DEFAULTS["decontam_sdr_cutoff"]
        )
        self.f_decontam_sdr.pack(fill="x", padx=6, pady=2)
        self.f_getorganelle_db = LabeledEntry(org, "getorganelle_db (override)", browse="dir")
        self.f_getorganelle_db.pack(fill="x", padx=6, pady=2)

        lrf = ttk.Labelframe(parent, text="  Long-read assembly (Filtlong / Flye / medaka)", bootstyle="secondary")
        lrf.pack(fill="x", **pad)
        self.f_filtlong_len = LabeledEntry(
            lrf, "filtlong_min_length", PARAM_DEFAULTS["filtlong_min_length"]
        )
        self.f_filtlong_len.pack(fill="x", padx=6, pady=2)
        self.f_filtlong_pct = LabeledEntry(
            lrf, "filtlong_keep_percent", PARAM_DEFAULTS["filtlong_keep_percent"]
        )
        self.f_filtlong_pct.pack(fill="x", padx=6, pady=2)
        ont_row = ttk.Frame(lrf)
        ont_row.pack(fill="x", padx=6, pady=2)
        ttk.Label(ont_row, text="ont_mode", width=26, anchor="w").pack(side="left")
        self.v_ont_mode = tk.StringVar(value=PARAM_DEFAULTS["ont_mode"])
        ttk.Combobox(
            ont_row, textvariable=self.v_ont_mode, values=["hq", "raw"], state="readonly", width=15
        ).pack(side="left")
        self.f_flye_genome_size = LabeledEntry(lrf, "flye_genome_size (e.g. 35m)")
        self.f_flye_genome_size.pack(fill="x", padx=6, pady=2)
        self.f_flye_asm_coverage = LabeledEntry(lrf, "flye_asm_coverage")
        self.f_flye_asm_coverage.pack(fill="x", padx=6, pady=2)
        self.f_medaka_model = LabeledEntry(lrf, "medaka_model (override)")
        self.f_medaka_model.pack(fill="x", padx=6, pady=2)

        pol = ttk.Labelframe(parent, text="  Polishing", bootstyle="secondary")
        pol.pack(fill="x", **pad)
        self.f_polish_rounds = LabeledEntry(pol, "polish_rounds", PARAM_DEFAULTS["polish_rounds"])
        self.f_polish_rounds.pack(fill="x", padx=6, pady=2)

        qc = ttk.Labelframe(parent, text="  Quality control", bootstyle="secondary")
        qc.pack(fill="x", **pad)
        self.v_runmerqury = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            qc, text="runmerqury (short-read mode only)", variable=self.v_runmerqury,
            bootstyle="round-toggle",
        ).pack(anchor="w", padx=6, pady=4)
        self.f_busco_lineage = LabeledEntry(qc, "busco_lineage (e.g. fungi_odb12)")
        self.f_busco_lineage.pack(fill="x", padx=6, pady=2)
        self.f_compleasm_db = LabeledEntry(qc, "compleasm_db (override)", browse="dir")
        self.f_compleasm_db.pack(fill="x", padx=6, pady=2)

    def _build_progress(self, parent):
        top = ttk.Frame(parent, padding=(8, 0, 8, 8))
        top.pack(fill="x")

        btn_row = ttk.Frame(top)
        btn_row.pack(fill="x")
        self.run_btn = ttk.Button(
            btn_row, text="Run", command=self.start_run, bootstyle="success", width=12
        )
        self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(
            btn_row, text="Stop", command=self.stop_run, bootstyle="danger", width=12,
            state="disabled",
        )
        self.stop_btn.pack(side="left", padx=(6, 0))
        self.open_out_btn = ttk.Button(
            btn_row, text="Open output folder", command=self._open_outdir,
            bootstyle="info-outline", state="disabled",
        )
        self.open_out_btn.pack(side="left", padx=(6, 0))

        self.status_var = tk.StringVar(value="Idle")
        self.status_label = ttk.Label(
            top, textvariable=self.status_var, font=("", 13, "bold"), bootstyle="secondary"
        )
        self.status_label.pack(anchor="w", pady=(10, 4))

        self.progress = ttk.Progressbar(
            top, mode="determinate", maximum=100, bootstyle="success-striped"
        )
        self.progress.pack(fill="x", pady=(0, 4))
        self.progress_label = ttk.Label(top, text="0 / 0 process instances complete")
        self.progress_label.pack(anchor="w")

        tree_frame = ttk.Labelframe(parent, text="  Per-process status", bootstyle="info")
        tree_frame.pack(fill="both", expand=False, padx=8, pady=(0, 8))
        columns = ("name", "tag", "progress", "status")
        self.tree = ttk_raw.Treeview(tree_frame, columns=columns, show="headings", height=12)
        for col, label, width in [
            ("name", "Process", 220),
            ("tag", "Tag", 120),
            ("progress", "Done / Total", 100),
            ("status", "Status", 130),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)

        log_frame = ttk.Labelframe(parent, text="  Log", bootstyle="info")
        log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.log_text = tk.Text(log_frame, wrap="none", state="disabled", height=15, borderwidth=0)
        log_scroll = ttk_raw.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        log_scroll.pack(side="right", fill="y", pady=4)

    # ----------------------------------------------------------------- theme
    def _on_theme_change(self, event=None):
        self.style.theme_use(self.v_theme.get())
        self._apply_theme_colors()

    def _apply_theme_colors(self):
        c = self.style.colors
        self.log_text.configure(
            background=c.bg, foreground=c.fg, insertbackground=c.fg,
            selectbackground=c.selectbg, selectforeground=c.selectfg,
        )
        self.log_text.tag_configure("error", foreground=c.danger)
        self.tree.tag_configure("done", foreground=c.success)
        self.tree.tag_configure("cached", foreground=c.secondary)
        self.tree.tag_configure("running", foreground=c.warning)
        self.tree.tag_configure("failed", foreground=c.danger)
        self._left_scroll.sync_bg(c.bg)

    # -------------------------------------------------------------- command
    def _validate(self):
        errors = []
        strain = self.f_strain.get()
        outdir = self.f_outdir.get()
        if not strain:
            errors.append("Strain / sample ID is required.")
        if not outdir:
            errors.append("Output directory is required.")

        r1, r2 = self.f_r1.get(), self.f_r2.get()
        lr, lr_type = self.f_lr.get(), self.v_lr_type.get()
        has_sr = bool(r1 and r2)
        has_lr = bool(lr)

        if not has_sr and not has_lr:
            errors.append("Provide short reads (R1+R2), long reads, or both.")
        if bool(r1) != bool(r2):
            errors.append("R1 and R2 must both be set, or both left empty.")
        if has_sr and len(r1.split(",")) != len(r2.split(",")):
            errors.append("R1 and R2 must list the same number of comma-separated files.")
        if has_lr and not lr_type:
            errors.append("lr_type is required when long reads are given.")
        if self.f_flye_asm_coverage.get() and not self.f_flye_genome_size.get():
            errors.append("flye_asm_coverage requires flye_genome_size.")

        pipeline_dir = Path(self.f_pipeline_dir.get())
        if not (pipeline_dir / "main.nf").exists():
            errors.append(f"No main.nf found in {pipeline_dir}")

        return errors

    def _build_command(self):
        args = ["nextflow", "run", "main.nf"]

        def add(flag, value):
            if value:
                args.extend([f"--{flag}", value])

        add("strain", self.f_strain.get())
        add("outdir", self.f_outdir.get())
        add("r1", self.f_r1.get())
        add("r2", self.f_r2.get())
        add("lr", self.f_lr.get())
        add("lr_type", self.v_lr_type.get())
        add("threads", self.f_threads.get())
        add("max_memory", self.f_max_memory.get())

        def add_if_changed(flag, entry_widget):
            val = entry_widget.get()
            if val and val != PARAM_DEFAULTS.get(flag, object()):
                add(flag, val)

        add_if_changed("species", self.f_species)
        add_if_changed("decontam_alcr_cutoff", self.f_decontam_alcr)
        add_if_changed("decontam_sdr_cutoff", self.f_decontam_sdr)
        add_if_changed("filtlong_min_length", self.f_filtlong_len)
        add_if_changed("filtlong_keep_percent", self.f_filtlong_pct)
        add_if_changed("polish_rounds", self.f_polish_rounds)
        if self.v_ont_mode.get() != PARAM_DEFAULTS["ont_mode"]:
            add("ont_mode", self.v_ont_mode.get())

        add("flye_genome_size", self.f_flye_genome_size.get())
        add("flye_asm_coverage", self.f_flye_asm_coverage.get())
        add("medaka_model", self.f_medaka_model.get())
        add("busco_lineage", self.f_busco_lineage.get())
        add("getorganelle_db", self.f_getorganelle_db.get())
        add("compleasm_db", self.f_compleasm_db.get())

        if self.v_skip_decontam.get():
            args.append("--skip_decontam")
        if self.v_runmerqury.get():
            args.append("--runmerqury")

        if self.v_profile.get() != "standard":
            args.extend(["-profile", self.v_profile.get()])
        if self.v_resume.get():
            args.append("-resume")
        if self.v_stub.get():
            args.append("-stub-run")

        return args

    # ------------------------------------------------------------- running
    def start_run(self):
        errors = self._validate()
        if errors:
            messagebox.showerror("Fix these before running", "\n".join(f"• {e}" for e in errors))
            return

        args = self._build_command()
        env = os.environ.copy()
        if self.f_nxf_ver.get():
            env["NXF_VER"] = self.f_nxf_ver.get()
        if self.f_java_home.get():
            env["JAVA_HOME"] = self.f_java_home.get()

        self.tracker = ProcessTracker()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree_rows.clear()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._append_log("$ " + " ".join(args) + "\n")

        try:
            self.proc = subprocess.Popen(
                args,
                cwd=str(Path(self.f_pipeline_dir.get())),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            messagebox.showerror("nextflow not found", "Could not launch `nextflow`. Is it on your PATH?")
            return

        self.running = True
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.open_out_btn.configure(state="disabled")
        self.status_var.set("Running...")
        self.status_label.configure(bootstyle="info")
        self.progress.configure(mode="indeterminate", bootstyle="info-striped")
        self.progress.start(15)

        threading.Thread(target=self._read_stream, args=(self.proc,), daemon=True).start()

    def stop_run(self):
        if self.proc and self.running:
            self.proc.terminate()
            self._append_log("\n[GUI] Sent terminate signal to nextflow.\n", error=True)

    def _read_stream(self, proc):
        for line in proc.stdout:
            self.log_queue.put(("line", line))
        proc.wait()
        self.log_queue.put(("exit", proc.returncode))

    def _poll_log_queue(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "line":
                    self._handle_line(payload)
                elif kind == "exit":
                    self._handle_exit(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _handle_line(self, line):
        is_error = line.startswith("ERROR") or "Error executing process" in line
        self._append_log(line if line.endswith("\n") else line + "\n", error=is_error)

        failed_match = FAILED_PROC_RE.search(line)
        if failed_match:
            proc_name = canonicalize_name(failed_match.group(1).split(" (")[0].strip())
            self.tracker.mark_failed(proc_name)

        parsed = parse_status_line(line)
        if parsed:
            self.tracker.update(parsed)
        if parsed or failed_match:
            self._refresh_progress()

    def _handle_exit(self, returncode):
        self.running = False
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self._refresh_progress()

        if returncode == 0:
            self.status_var.set("Completed successfully")
            self.status_label.configure(bootstyle="success")
            self.progress.configure(bootstyle="success")
            self.open_out_btn.configure(state="normal")
        else:
            self.status_var.set(f"Exited with code {returncode}")
            self.status_label.configure(bootstyle="danger")
            self.progress.configure(bootstyle="danger")

    def _refresh_progress(self):
        for name, parsed in self.tracker.rows():
            status = self.tracker.status_of(parsed)
            values = (name, parsed["tag"], f"{parsed['done']} / {parsed['total']}", STATUS_ICON[status])
            if name in self.tree_rows:
                self.tree.item(self.tree_rows[name], values=values, tags=(status,))
            else:
                item = self.tree.insert("", "end", values=values, tags=(status,))
                self.tree_rows[name] = item

        done, total = self.tracker.overall_fraction()
        if total > 0:
            pct = 100.0 * done / total
            self.progress.configure(value=pct)
            self.progress_label.configure(text=f"{done} / {total} process instances complete ({pct:.0f}%)")

    def _append_log(self, text, error=False):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text, ("error",) if error else ())
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _open_outdir(self):
        outdir = self.f_outdir.get()
        if outdir and Path(outdir).exists():
            subprocess.Popen(["xdg-open", outdir])


if __name__ == "__main__":
    app = BagASMGui()
    app.mainloop()
