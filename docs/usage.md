# Usage

## How mode selection works

bagASM doesn't have a `--mode` flag. It looks at which of `--r1`/`--r2`
(Illumina short reads) and `--lr`/`--lr_type` (PacBio/ONT long reads) you've
given it, and picks one of three paths:

| You provide | Mode | Assembler | Polisher |
|---|---|---|---|
| `--r1` + `--r2` only | **Short-read** | SPAdes | Polypolish |
| `--lr` + `--lr_type` only | **Long-read** | Flye | medaka / racon / none, by platform |
| Both | **Long+short hybrid** | Flye | Polypolish |

`--strain` (a sample/strain ID used to name output files) and `--outdir`
are required in every mode.

:::{note}
Nextflow reserves single-dash flags for its own launcher (`-resume`,
`-profile`, `-w`, ...), so inputs are `--r1`/`--r2`/`--lr` (double-dash),
not the `-1`/`-2` convention tools like `bwa` or `samtools` use.
:::

## Requirements

- Nextflow `>=25.04.6,<26`, Java 21
- Docker, with the local (non-remote) executor. Several steps depend on
  Docker-specific behavior — chlomito shells out to sibling containers via
  a mounted Docker socket, so remote/cloud executors and Singularity aren't
  supported. See the repo's `PIPELINE_SCHEME.txt` for the full list of
  Docker-specific caveats.

## Getting the pipeline

```bash
nextflow pull GabrieleRigano99/bagASM
```

No local clone is required after that — `nextflow run GabrieleRigano99/bagASM`
works directly. If you'd rather work from a checkout, clone the repo and
run `nextflow run main.nf` instead; every command on this page works
either way.

## Setup

Nothing needs installing by hand. Every tool runs in its own Docker
container, pulled automatically on first use. Two reference databases
download themselves the first time they're actually needed, and are
reused on every later run:

- GetOrganelle's organelle-type database (`fungus_mt` by default) →
  cached in `assets/getorganelle_db/<species>/` (override the location
  with `--getorganelle_db`)
- compleasm's BUSCO lineage data → cached in `assets/compleasm_db/`
  (override with `--compleasm_db`), only downloaded if you set
  `--busco_lineage`

## Multiple lanes or sequencing runs

`--r1`, `--r2`, and `--lr` each accept a comma-separated list of files, to
pool several lanes or runs of the **same** library:

```bash
--r1 L001_R1.fq.gz,L002_R1.fq.gz --r2 L001_R2.fq.gz,L002_R2.fq.gz
```

`--r1` and `--r2` must list the same number of files, in matching order.
This is for multiple lanes/runs of one library — not for genuinely
distinct library preparations (different insert sizes, mixed
paired-end/mate-pair), which aren't supported.

---

## Mode 1 — short reads only

```bash
nextflow run GabrieleRigano99/bagASM \
  --r1 R1.fq.gz --r2 R2.fq.gz \
  --strain StrainID --outdir results
```

Steps: `fastp` (adapter/quality trimming) → `SPAdes` 4.3.0 (assembly) →
`GetOrganelle` (mitogenome extraction, from the assembly graph, falling
back to slower read-based extraction if the graph doesn't resolve a single
scaffold) → `Redundans` (scaffolding + gap-filling) → `chlomito`
(organelle-contamination removal) → `Polypolish` (polishing, via minibwa)
→ rename and sort by length.

Parameters specific to this mode:

| Flag | Default | Meaning |
|---|---|---|
| `--species` | `fungus_mt` | Organelle type GetOrganelle extracts — see [Organelle extraction](#organelle-extraction) |
| `--chlomito_mito_alcr_cutoff` | `0.1` | chlomito mitochondrial ALCR cutoff |
| `--chlomito_mito_sdr_cutoff` | `0.1` | chlomito mitochondrial SDR cutoff |
| `--polish_rounds` | `3` | Number of minibwa + Polypolish iterations |
| `--runmerqury` | `false` | Also run Redundans' bundled Merqury k-mer QV/completeness check |

## Mode 2 — long reads only

```bash
nextflow run GabrieleRigano99/bagASM \
  --lr reads.fq.gz --lr_type ont \
  --strain StrainID --outdir results
```

`--lr_type` is one of `ont`, `pacbio-clr`, or `pacbio-hifi`, and it drives
which assembler preset and which polisher run:

| `--lr_type` | Filtlong first? | Flye preset | Polisher |
|---|---|---|---|
| `ont` | yes | `--nano-hq` (or `--nano-raw`, see `--ont_mode`) | medaka |
| `pacbio-clr` | yes | `--pacbio-raw` | racon |
| `pacbio-hifi` | no | `--pacbio-hifi` | none — HiFi is already ~99.9% accurate |

Redundans and chlomito are **not** run in this mode: Flye assemblies are
already long-read-scaffolded, and organelle decontamination wasn't
requested for this path.

Parameters specific to this mode:

| Flag | Default | Meaning |
|---|---|---|
| `--filtlong_min_length` | `1000` | Discard long reads shorter than this (ont/pacbio-clr only) |
| `--filtlong_keep_percent` | `90` | Keep only this percentage of reads by score (ont/pacbio-clr only) |
| `--ont_mode` | `hq` | Flye ONT preset: `hq` (modern/Dorado-Guppy-sup) or `raw` (R9/older basecalls) |
| `--flye_genome_size` | unset | Estimated genome size, e.g. `35m` — Flye `-g`/`--genome-size` |
| `--flye_asm_coverage` | unset | Downsample to this per-base coverage for the initial assembly — Flye `--asm-coverage`; requires `--flye_genome_size` |
| `--medaka_model` | unset (auto-detect) | Override medaka's basecall-based model choice (`ont` only) |
| `--species` | `fungus_mt` | Same as Mode 1 — GetOrganelle still runs, from Flye's assembly graph |

:::{warning}
`--flye_asm_coverage` without `--flye_genome_size` is rejected immediately
with a clear error — Flye itself needs the genome size estimate to know
what "coverage" means, and this pipeline checks that combination up front
rather than letting Flye fail partway through a long run.
:::

## Mode 3 — long reads + short reads

```bash
nextflow run GabrieleRigano99/bagASM \
  --lr reads.fq.gz --lr_type ont \
  --r1 R1.fq.gz --r2 R2.fq.gz \
  --strain StrainID --outdir results
```

Identical to Mode 2 through assembly and mitogenome extraction (Filtlong
still runs for ont/pacbio-clr, the assembler preset is still chosen by
`--lr_type`), but whenever short reads are also given, they take over
polishing from medaka/racon: Polypolish runs instead, using the same
`--polish_rounds` parameter as Mode 1. This override happens regardless of
`--lr_type` — even for `pacbio-hifi`, which otherwise skips polishing
entirely in Mode 2.

---

## Organelle extraction

Every mode extracts an organelle genome via
[GetOrganelle](https://github.com/Kinggerm/GetOrganelle), separately from
the nuclear assembly. `--species` controls which organelle type, and
accepts any of GetOrganelle's own vocabulary:

`embplant_pt`, `embplant_mt`, `embplant_nr`, `fungus_mt` (default),
`fungus_nr`, `animal_mt`, `other_pt` — or several joined by comma, e.g.
`embplant_pt,embplant_mt`.

:::{note}
The output folder and filename (`mitochondrion/<strain>_mitogenome.fasta`)
stay fixed regardless of `--species` — naming doesn't adapt if you extract
a plastid or nuclear-ribosomal sequence instead of a mitochondrion.
:::

## Quality control

Every run finishes with two checks on the final assembly, no flags
required:

- **QUAST** 5.3.0 (`--fungus --eukaryote`), reference-free contiguity and
  gene-prediction stats
- **Qualimap bamqc** 2.3, fed by realigning the run's own reads back onto
  the final assembly (minibwa for the short-read branch, minimap2 with the
  platform-appropriate preset for the long-read branch)

Two more are opt-in:

| Flag | Default | Adds |
|---|---|---|
| `--busco_lineage` | unset | **compleasm** 0.2.8 (BUSCO-style gene completeness) against the named lineage, e.g. `fungi_odb12`. Skipped entirely if unset — there's no sensible default lineage. |
| `--runmerqury` | `false` | Redundans' bundled **Merqury** k-mer QV/completeness check (short-read mode only) |

## Resources and execution

| Flag | Default | Meaning |
|---|---|---|
| `--threads` | `20` | Threads for `process_high`/`process_medium` steps (capped to available CPUs) |
| `--max_memory` | unset (physical RAM − 4 GB) | Override the memory cap, e.g. if Docker is configured with less memory than the host |

Three execution profiles are available via `-profile`:

```bash
-profile standard   # local executor (default)
-profile slurm       # Slurm cluster
-profile sge         # SGE cluster
```

## Output layout

```text
<outdir>/
├── trimmed_reads/
│   ├── <strain>_R1.trimmed.fastq.gz         (short-read modes)
│   ├── <strain>_R2.trimmed.fastq.gz
│   ├── <strain>.fastp.html / .json
│   └── <strain>_lr.filtered.fastq.gz        (long-read modes, ont/pacbio-clr only)
├── assembly/
│   ├── spades/                              (short-read mode only)
│   ├── flye/                                (long-read modes only)
│   ├── redundans/                           (short-read mode only)
│   ├── chlomito/                            (short-read mode only)
│   ├── polished/
│   └── <strain>_genome.fasta                (final assembly)
├── mitochondrion/
│   ├── get_organelle_from_assembly/
│   ├── get_organelle_from_reads/            (short-read mode, only if the fallback triggered)
│   └── <strain>_mitogenome.fasta            (final mitogenome, every mode)
├── qc/
│   ├── quast/<strain>_quast/
│   ├── qualimap/<strain>_qualimap/
│   └── compleasm/<strain>_compleasm/        (only if --busco_lineage is set)
└── pipeline_info/
    ├── execution_report.html
    ├── execution_timeline.html
    ├── execution_trace.txt
    └── pipeline_dag.svg
```

For the full breakdown of every process in every mode — including the
GFA/fastg format handling, the chlomito docker-socket requirement, and the
complete list of real bugs found and fixed along the way — see
[`PIPELINE_SCHEME.txt`](https://github.com/GabrieleRigano99/bagASM/blob/main/PIPELINE_SCHEME.txt)
in the repository.

## Full `--help`

```bash
nextflow run GabrieleRigano99/bagASM --help
```

prints all of the above directly from the pipeline itself, always in sync
with the installed version.
