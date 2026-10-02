# bagASM GUI

A desktop GUI for running the bagASM pipeline and watching progress live,
without touching the command line.

```bash
pip install --user ttkbootstrap
python3 gui/bagasm_gui.py
```

Everything else is Python standard library (`tkinter`) — `ttkbootstrap` is
the only extra dependency, used for the theming. Requires a graphical
display; won't run over a headless SSH session unless you're forwarding
X11 (`ssh -X`).

Press **F11** to maximize/restore the window. The window starts at
1900×1100 by default — resize or maximize freely, the layout adapts (the
input form on the left keeps a fixed comfortable width; the log/progress
panel on the right absorbs any extra space).

## Browser version (localhost)

```bash
python3 gui/bagasm_web.py          # opens http://localhost:8765
```

Standard library only, no `ttkbootstrap`/display needed, so it also works
over SSH with a port forward (`ssh -L 8765:localhost:8765 host`). Binds
127.0.0.1 only. Same form, run/stop and progress table as the desktop GUI,
plus `skip_trimming`, `no_careful` and `redundans_limit`. Extras: live pipeline flow diagram
(click a step to filter the log), timeline, ETA, CPU/RAM gauges, failed-task
panel (stderr tail + command), results dashboard (QUAST/compleasm/Qualimap,
contig and polishing-round charts; "Load results" works on any finished
output dir), log search, dark/light toggle, browser notification on finish.
The page itself lives in `gui/bagasm_web.html`. File paths are
typed in (browsers can't expose real paths). Options: `--port N`, `--no-browser`.

## What it does

- Form fields for every parameter `main.nf --help` exposes (required fields
  up front, everything else under "Advanced options").
- Fill in short reads, long reads, or both — same auto mode-selection
  behavior as the pipeline itself; the GUI doesn't force a mode.
- "Run" launches `nextflow run main.nf` as a subprocess (with `NXF_VER`/
  `JAVA_HOME` set from the fields at the top — override if your machine
  needs different values) and parses its own status output live to drive
  a per-process table and an overall progress bar.
- "Stop" sends the running pipeline a terminate signal.
- "-stub-run" checkbox: dry-run without any real computation, useful for
  checking your parameter combination is valid before committing to a
  real (possibly hours-long) run.
- "-resume" checkbox: same caching behavior as running it on the CLI.

## Notes

- The "main.nf directory" field defaults to the repo this GUI lives in;
  point it elsewhere if you're running a different checkout.
- Per-process status comes from parsing Nextflow's own terminal output
  (the `[hash] PROCESS_NAME | N of M ✔` lines), not a separate reporting
  channel — if Nextflow's own output format ever changes, the parsing
  regex in `bagasm_gui.py` (`STATUS_RE`) is the one place to update.
- `-profile slurm`/`-profile sge` both work from here, but only if the
  machine running the GUI is the one that should submit those jobs (e.g.
  a cluster login node with the scheduler client installed) — the GUI
  doesn't do anything special for remote execution.
- The file/directory picker dialogs (Browse buttons) open at ~90% of
  your screen size instead of Tk's cramped ~400x250 default. They can't
  actually be maximized after opening -- confirmed Tk marks them
  `-type dialog`, and window managers refuse both the maximize button and
  a programmatic zoom/fullscreen request for that window type -- so
  opening already near-fullscreen is the fix instead of fighting that.
  Implemented by resizing the dialog's own Tk toplevel
  (`.__tk_filedialog` / `.__tk_choosedir`) right after it opens (see
  `open_dialog_big()`); if a future Tk version renames these internal
  toplevels, the resize silently no-ops instead of erroring, so at worst
  you're back to the small default.
