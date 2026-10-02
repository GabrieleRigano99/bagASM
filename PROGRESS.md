# bagASM — Progress log

A chronological record of what's been built, tested, and fixed on bagASM
since it started. For a condensed "what is this, where do things stand"
summary instead, see `HANDOFF.md`. For the full technical DAG and the
detailed root-cause writeups behind each fix below, see the numbered
CAVEATS section of `PIPELINE_SCHEME.txt` — that file is the authoritative
source; this is the narrative version.

## 2026-07-09 — Initial build

First working version committed (`7260633`): a Nextflow DSL2 pipeline
covering both short-read and long-read fungal genome assembly.

- **Short-read mode:** fastp → SPAdes → Redundans → chlomito (organelle
  decontamination) → Polypolish.
- **Long-read mode:** Flye → medaka/racon/Polypolish, chosen by platform.
- Custom Docker images built and published to Docker Hub the same day
  (`7aa82ef`) so the pipeline didn't require local image builds.
- `--species` flag added for GetOrganelle's organelle-type selection, with
  a full `--help` redesign (`f0ddb8b`).

Real bugs found and fixed via actual runs on real Sporothrix data
(SG03/SG04 strains), not stub-run alone:
- GetOrganelle needed a one-time database setup the biocontainer image
  doesn't ship — added a dedicated `GET_ORGANELLE_SETUP` process, cached
  via `storeDir`.
- SPAdes 4.x's assembly graph defaults to GFA v1.2, which GetOrganelle
  1.7.7.1 can't parse — switched to consuming SPAdes' `.fastg` output
  instead.
- The third-party `chlomito` tool installs everything under `/root` at
  mode 700, incompatible with this pipeline's non-root Docker execution —
  fixed with a derived image (`gabrielerigano/bagasm-chlomito:1.0`).
- Polypolish switched from bwa to **minibwa** (Heng Li's bwa-mem
  successor, ~3x faster); `--polish_rounds` (default 3) added to control
  iteration count.

## 2026-07-10 — QC suite, Filtlong, docs, long-read decontamination

Busy day — most of the pipeline's current shape landed here.

- **QC suite added** (`60f0ea1`): QUAST + Qualimap bamqc run automatically
  every mode; compleasm (BUSCO-style) runs if `--busco_lineage` is set;
  `--runmerqury` turns on Redundans' own bundled Merqury k-mer QV check.
  Found and fixed a real bug in the same pass: the stock `redundans`
  biocontainer ships only BusyBox coreutils, whose `cp` doesn't support
  GNU's `-t DEST` syntax that Merqury's meryl integration relies on —
  crashed 100% of the time until fixed with a `cp` shim
  (`gabrielerigano/bagasm-redundans:1.0`). Re-validated: real QV of 46.86.
- **Filtlong added** (`4c61e5b`): runs before Flye for `--lr_type`
  ont/pacbio-clr (skipped for pacbio-hifi, already highly accurate).
- **Flye genome-size flags** (`27e77a8`): `--flye_genome_size` and
  `--flye_asm_coverage`.
- **Docs site stood up**: Sphinx + MyST (`55998cd`), deployed to GitHub
  Pages via Actions (`23bf160`), linked from the README (`16ff470`).
  README rewritten with a proper three-mode walkthrough (`7453519`) and
  later given a fully embedded, regeneratable `--help` block (`ead956a`).
- **chlomito extended to hybrid mode** (`9f2e289`): now also runs in
  Mode 3 (long+short), between Flye's assembly and Polypolish — it has no
  long-read input option, so it still sits out Mode 2 entirely.
- **`--chlomito_species` exposed** (`071921b`): chlomito's own
  `-species {animal,plant,fungi}` flag, previously hardcoded to `"fungi"`.
- **Native long-read organelle decontamination built** (`f064f8d`): for
  Mode 2 (long-read-only), where chlomito structurally can't run (it
  requires a short-read pair for its depth-ratio metric). Rather than
  faking a synthetic short-read pair, reimplemented chlomito's own
  ALCR+SDR detection approach natively. ALCR = fraction of a contig's
  length aligning to the extracted mitogenome; SDR = contig depth ÷
  mitogenome reference depth. Validated first against synthetic data (3
  contigs: clean nuclear, mito-duplicate, HGT-like fragment) — correctly
  kept the first two, dropped the duplicate.
- **Milestone:** first fully clean, uninterrupted, real end-to-end run on
  actual Sporothrix data (strain SG04, short-read-only) — all 9 processes
  succeeded with no manual intervention. Result: 34.6 Mbp assembly, 5,608
  scaffolds, N50 ≈ 55 kb, mitogenome extracted as a single circular
  33,829 bp sequence directly from the assembly graph.

## 2026-07-11 to 2026-07-14 — Desktop GUI, chlomito retired

- **Desktop GUI built** (`gui/bagasm_gui.py`, Tkinter + ttkbootstrap):
  form-driven pipeline runner with live per-process status parsed from
  Nextflow's own terminal output, `-resume`/`-stub-run` toggles, and a
  desktop launcher (`gui/bagasm.desktop`, `gui/start_bagasm.sh`).
  Deliberately kept untracked in git — never asked to be committed.
- **chlomito retired from the active pipeline entirely** (`9ef99bd`,
  2026-07-14): after a user-reported real bug (a decontaminated output
  still contained the mitogenome), investigation traced through **8
  distinct, unrelated bugs** across 4 of chlomito's bundled scripts, all
  confirmed against real data — non-root `/opt` permissions, unquoted
  shell interpolation breaking on ordinary FASTA headers this pipeline's
  own steps produce, a commented-out line that made chlomito's own
  re-extraction never actually get used, a species-string mismatch
  silently swallowed inside an unchecked worker pool, an uninitialized
  bundled GetOrganelle database, a `KeyError` in chlomito's own version
  table, and a frozen 2017 samtools crashing under a hardcoded thread
  count. No upstream fix available — chlomito's public GitHub repo
  doesn't even contain source, only a README.
  - The Mode 2 native reimplementation was generalized and renamed
    (`decontam_organelle_lr.nf` → `decontam_organelle.nf`,
    `DECONTAM_ORGANELLE`) to replace chlomito everywhere, aliased
    (`DECONTAM_ORGANELLE_SR`/`_HYBRID`) per Nextflow's same-process rule.
  - All the scattered chlomito-era params (`--chlomito_species`,
    `--chlomito_mito_alcr_cutoff`, `--skip_lr_decontam`, etc.) were
    consolidated into just `--skip_decontam` and
    `--decontam_alcr_cutoff`/`--decontam_sdr_cutoff`, uniform across every
    mode.
  - Real-data validated: run directly against SG03's actual 206-contig
    assembly — correctly flagged and removed exactly one contaminated
    contig (ALCR 0.999, SDR 0.996), keeping the other 205.
  - `modules/chlomito.nf` deleted; the fix image and Dockerfile were left
    on disk as a documented reference of what was tried, but nothing in
    the active pipeline launches it anymore.

## Standalone real-world use — 42-strain Schenckii decontamination

Ran organelle decontamination (only that step, not the full pipeline)
against 42 already-polished, externally-assembled Sporothrix schenckii
genomes in `/home/astrogab/Schenckii/49_asm_schenckii/all_asms/`, reusing
already-extracted mitogenomes rather than re-running GetOrganelle. Handled
real edge cases directly from user clarification (one strain's mitogenome
filed under an alias, two strains with no usable mitogenome excluded).
Idempotent/resumable batch script, scratch kept on a separate volume with
immediate cleanup of large intermediates. All 42 strains succeeded, zero
failures; one genuine outlier (46 flagged contigs vs. the typical 1,
because that particular assembly was unusually fragmented overall)
investigated and confirmed real, not a bug.

## 2026-07-29 — Per-round QUAST comparison, combined final QC report

(`abe5b39`)

- **`--quast_per_round`**: Polypolish already generated every intermediate
  `round0.fasta`...`roundN.fasta` internally but only ever published the
  final one — now all rounds are emitted, and QUAST's own native
  multi-assembly comparison mode turns them into one report showing
  contiguity change across polishing (short-read/hybrid modes only, the
  ones that run Polypolish).
- **`FINAL_QC_REPORT`**: always runs now, combining QUAST + Qualimap bamqc
  + (if compleasm ran) its BUSCO-style stats into one Markdown summary per
  strain. `bin/combine_qc_report.py`'s parsing was validated directly
  against real on-disk QUAST/Qualimap/compleasm output before being wired
  in, not just synthetic formats.

## 2026-08-06 — `--redundans_limit`

(`f73917b`) Exposed Redundans' own `--limit` flag (fraction of reads
aligned for scaffolding; upstream default 0.2), which had been hardcoded
to `1` (100%) since the very first working run. Still defaults to `1` to
preserve existing behavior; validated range `(0, 1]`.

## 2026-09-03 — fastp gzip crash fixed

(`ad5d7c3`) Real user-reported bug: fastp crashed on plain (non-gzipped)
FASTQ input with "invalid gzip header found." Root cause confirmed
directly against the real fastp container: fastp decides whether to
gunzip purely from the `.gz` filename suffix, not actual content, and the
pipeline's lane-pooling step always named its merged output `.fastq.gz`
regardless of whether the source was really compressed. Fixed by checking
each lane file with `gzip -t` (confirmed BusyBox-compatible; `zcat -f` is
not) and re-gzipping on the fly only where needed — also handles a lane
list mixing gzipped and plain files. Filtlong (the long-read equivalent)
was checked and does not have this bug.

## 2026-09-14 — `--skip_trimming`

(`de962e7`) Skips fastp entirely in short-read mode — no
adapter/quality/length trimming, no HTML/JSON QC report — while lane
pooling and gzip normalization still happen, since every downstream step
needs one real-gzip R1/R2 file regardless. Built as a true skip after an
initial fastp-no-op-flags approach was explicitly rejected in favor of
actually not running fastp at all.

## 2026-09-15 — Handoff doc

`HANDOFF.md` written: condensed project summary for anyone picking this
up — what it is, where things stand, known limitations, doc pointers.

## 2026-10-02 — `--no_careful`, browser GUI

- **`--no_careful`** (`6b1470f`): drops `--careful` from SPAdes
  (short-read mode). Default `false`, so behavior is unchanged unless set.
  Wired through `modules/spades.nf`, `nextflow.config`, `main.nf` help,
  README, `docs/usage.md`, `PIPELINE_SCHEME.txt`.
- **Browser GUI** (`gui/bagasm_web.py` + `gui/bagasm_web.html`, stdlib
  only, `python3 gui/bagasm_web.py` -> http://localhost:8765, 127.0.0.1
  only, Host/Origin checks on every request). Same form/run/stop as the
  Tk GUI plus `skip_trimming`, `no_careful`, `redundans_limit`. Extras:
  server-side file/folder browser, live pipeline flow diagram (click step
  to filter log), timeline, rough ETA, CPU/RAM gauges, failed-task panel
  (`.command.err` tail + command), results dashboard (QUAST / compleasm /
  Qualimap tiles, BUSCO bar, polish-round N50, contig sizes; reuses
  `bin/combine_qc_report.py` parsers), log search, dark/light toggle,
  finish notification, form remembered across reloads.
- **Tested**: fake-`nextflow` end-to-end (failure path, results parsing),
  compleasm parser on a real old summary.txt, and a real
  `-stub-run` of the short-read pipeline on `SG04_test` through the GUI
  (13/13 steps). Fixed Nextflow's ellipsized process names
  (`GET…NELLE_FROM_ASSEMBLY`) being tracked as a separate row.
- **Not tested**: a real (non-stub) run through the GUI, so the results
  charts are unverified on real pipeline output; QUAST/Qualimap parsers on
  real files; browser Notification popup.
- **Not committed**: `gui/` (Tk and web GUI), `PROGRESS.md`, `HANDOFF.md`.

## Ongoing / not yet started

- **Benchmark paper**: discussed a species panel (Sporothrix schenckii's
  existing 42-strain set as a consistency/scale pillar, plus 2-3
  taxonomically diverse species with reference genomes for ground-truth
  validation) and tool-level comparisons (native decontamination vs.
  chlomito, polishing ablations, whole-pipeline vs. bare SPAdes/Flye,
  hifiasm as an external comparator). No benchmark data collected yet.
- **Single-end Illumina reads**: not currently supported — every
  short-read module structurally assumes a read pair. Would need rework
  in fastp, Redundans, Polypolish, and the QC alignment module, not just
  the input validation. Not started.
