# bagASM - An easy to use _de novo_ Genome Assembly Pipeline!

![bagASM_logo.png](bagASM_logo.png)

bagASM is a user friendly pipeline accepting Illumina short reads, PacBio or ONT long reads, or both together, and it hands back
a (mitochondrial/plastidial) decontaminated, polished nuclear and mitochondrial
genome, extracted separately and ready on its own.

For the full technical picture — every branch of the pipeline broken down
by sequencing platform, the output folder layout, and a running log of
real bugs found (and fixed) along the way — see
[PIPELINE_SCHEME.txt](PIPELINE_SCHEME.txt).

**[Read the full documentation here!](https://gabrielerigano99.github.io/bagASM/)**


## Requirements

- Nextflow `>=25.04.6,<26`, Java 21
- Docker, with the local (non-remote) executor — several steps depend on
  Docker-specific behavior (see caveats in PIPELINE_SCHEME.txt)

## Setup

There's nothing to install by hand. The pipeline pulls its own containers,
and the reference data it needs downloads itself the first time it's
actually used:

- GetOrganelle's `fungus_mt` database → cached in `assets/getorganelle_db/`
  (override with `--getorganelle_db`)
- compleasm's BUSCO lineage data → cached in `assets/compleasm_db/`
  (override with `--compleasm_db`), only if you ask for `--busco_lineage`

After that first run, neither gets downloaded again.

## Get it

```bash
nextflow pull GabrieleRigano99/bagASM
```

No local clone required — `nextflow run GabrieleRigano99/bagASM` works
straight from that. (If you'd rather work from a checkout, clone the repo
and run `nextflow run main.nf` the same way; every example below works
either way.)

## The three ways to run it

There's no mode flag to remember — bagASM looks at which reads you've
given it and picks the right path itself.

### 1. Short reads only

The classic route: trim with fastp, assemble with SPAdes, scaffold and
gap-fill with Redundans, strip out organelle contamination with a native
ALCR+SDR detector (see below), then polish with Polypolish.

```bash
nextflow run GabrieleRigano99/bagASM \
  --r1 R1.fq.gz --r2 R2.fq.gz \
  --strain StrainID --outdir results
```

### 2. Long reads only

Point it at PacBio or ONT reads instead and it assembles with Flye, strips
out organelle contamination the same way (aligning the long reads
themselves this time, since no short reads are available), then polishes
with whatever suits the platform — medaka for ONT, racon for PacBio-CLR,
or nothing at all for PacBio-HiFi, which is already accurate enough on its
own.

```bash
nextflow run GabrieleRigano99/bagASM \
  --lr reads.fq.gz --lr_type ont \
  --strain StrainID --outdir results
```

`--lr_type` is one of `ont`, `pacbio-clr`, or `pacbio-hifi`.

### 3. Long reads + short reads

Give it both, and the short reads take over polishing duty from
medaka/racon — Polypolish tends to do a more thorough job when it has the
option. Organelle decontamination also switches to aligning the short
reads instead of the long ones, for a higher-confidence read of depth and
coverage.

```bash
nextflow run GabrieleRigano99/bagASM \
  --lr reads.fq.gz --lr_type ont \
  --r1 R1.fq.gz --r2 R2.fq.gz \
  --strain StrainID --outdir results
```

---

Every one of these accepts `StrainID` and `results` as just placeholders —
swap in your own sample name and output folder.


<code>nextflow run GabrieleRigano99/bagASM --help</code> (full output)

```text
   _                    _    ____  __  __
  | |__   __ _  __ _   / \  / ___||  \/  |
  | '_ \ / _' |/ _' | / _ \ \___ \| |\/| |
  | |_) | (_| | (_| |/ ___ \ ___) | |  | |
  |_.__/ \__,_|\__, /_/   \_\____/|_|  |_|
               |___/

  bagASM — fungal genome assembly pipeline
  Version 1.0.0  •  Bioinformatics and Computational Genomics LAB, UniME
  Main Developer  •  Gabriele Rigano - ORCID https://orcid.org/0009-0008-1928-6789

  USAGE:  nextflow run main.nf [options]

────────────────────────────────────────────────────────────────────────
  MODE 1  —  short reads only
────────────────────────────────────────────────────────────────────────

  fastp -> SPAdes -> GetOrganelle -> Redundans -> decontaminate -> Polypolish -> rename/sort

    nextflow run main.nf --r1 R1.fq.gz --r2 R2.fq.gz --strain StrainID --outdir results

  REQUIRED
    --r1 / --r2          Illumina paired reads (fastq/fastq.gz)
    --strain             Strain/sample ID used for output naming
    --outdir             Output directory

────────────────────────────────────────────────────────────────────────
  MODE 2  —  long reads only  (PacBio/ONT; switches assembler to Flye)
────────────────────────────────────────────────────────────────────────

  Filtlong -> Flye -> GetOrganelle -> polish -> rename/sort
  Filtlong and the polisher are both chosen automatically from --lr_type:
    ont          -> Filtlong then medaka
    pacbio-clr   -> Filtlong then racon
    pacbio-hifi  -> no Filtlong, no polish  (already highly accurate)

    nextflow run main.nf --lr reads.fq.gz --lr_type ont --strain StrainID --outdir results

  REQUIRED
    --lr                 Long-read FASTQ(.gz)
    --lr_type            ont | pacbio-clr | pacbio-hifi
    --strain / --outdir   as in MODE 1

────────────────────────────────────────────────────────────────────────
  MODE 3  —  long reads + short reads  (short reads polish instead)
────────────────────────────────────────────────────────────────────────

  Same as MODE 2 through Flye/mitogenome extraction, but --r1/--r2 (if given)
  always override medaka/racon with Polypolish, regardless of --lr_type.

    nextflow run main.nf --lr reads.fq.gz --lr_type ont \
        --r1 R1.fq.gz --r2 R2.fq.gz --strain StrainID --outdir results

────────────────────────────────────────────────────────────────────────
  MULTIPLE LANES/RUNS OF THE SAME LIBRARY
────────────────────────────────────────────────────────────────────────

  Pass a comma-separated list to --r1/--r2/--lr to pool several lanes or
  runs of one library, e.g.:
    --r1 L001_R1.fq.gz,L002_R1.fq.gz --r2 L001_R2.fq.gz,L002_R2.fq.gz
  --r1 and --r2 must list the same number of files, in matching lane order.
  This is for multiple lanes/runs of the SAME library, not distinct library
  preps (different insert sizes, mixed PE/MP) — those aren't supported.

────────────────────────────────────────────────────────────────────────
  OPTIONAL
────────────────────────────────────────────────────────────────────────

    --species            Organelle type to extract [fungus_mt], passed to
                        GetOrganelle's -F/-a. One of:
                          embplant_pt | embplant_mt | embplant_nr | fungus_mt | fungus_nr | animal_mt | other_pt
                        or several joined by comma, e.g. embplant_pt,embplant_mt
    --threads            Threads for process_high steps [20]
    --ont_mode            Flye ONT preset [hq]: hq (--nano-hq, modern/Dorado-Guppy-sup)
                        | raw (--nano-raw, R9/low-quality basecalls)  (--lr_type ont only)
    --filtlong_min_length    Discard reads shorter than this [1000]
                        (--lr_type ont/pacbio-clr only)
    --filtlong_keep_percent  Keep only this % of reads by score [90]
                        (--lr_type ont/pacbio-clr only)
    --flye_genome_size    Expected genome size, e.g. 35m — Flye -g/--genome-size  (long-read mode only)
    --flye_asm_coverage   Downsample to this per-base coverage for the initial disjointig
                        assembly — Flye --asm-coverage; requires --flye_genome_size
                        (long-read mode only)
    --medaka_model        Override medaka's auto-detected model  (--lr_type ont only)
    --skip_decontam       Skip organelle decontamination entirely [false]  (all modes)
    --decontam_alcr_cutoff  ALCR cutoff for organelle decontamination [0.1]  (all modes)
    --decontam_sdr_cutoff   SDR cutoff, same context [0.1]  (all modes)
    --polish_rounds       Number of minibwa+Polypolish iterations [3]
    --runmerqury          Run Redundans' built-in Merqury k-mer QV/completeness [false]  (MODE 1 only)
    --busco_lineage       BUSCO lineage for compleasm, e.g. fungi_odb12 — if unset, compleasm is skipped
    --max_memory          Override memory cap for process_high/long steps

────────────────────────────────────────────────────────────────────────
  QUALITY CONTROL  —  runs on the final assembly in every mode
────────────────────────────────────────────────────────────────────────

  QUAST (contiguity/gene-prediction stats) and Qualimap bamqc (read-mapping
  stats, from the assembly's own reads realigned back to it) always run.
  compleasm (BUSCO-style gene completeness) runs only if --busco_lineage is set.

────────────────────────────────────────────────────────────────────────
  NOTE: Nextflow reserves single-dash options for its own launcher flags, so
  inputs are passed as --r1/--r2/--lr (double-dash) rather than the -1/-2
  convention used by tools like bwa/samtools.
────────────────────────────────────────────────────────────────────────
```

## Quality control

Every run finishes with QUAST and Qualimap bamqc checking over the final
assembly, no flags needed. Add `--busco_lineage fungi_odb12` (or any BUSCO
lineage name) to also run compleasm. `--runmerqury` (short-read mode only)
turns on Redundans' own bundled Merqury k-mer QV/completeness check.
