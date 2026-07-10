# bagASM - An easy to use _de novo_ Genome Assembly Pipeline!

![bagASM_logo.png](bagASM_logo.png)

bagASM turns raw sequencing reads into a clean genome. Feed it Illumina
short reads, PacBio or ONT long reads, or both together, and it hands back
a decontaminated, polished nuclear assembly — plus the mitochondrial
genome, extracted separately and ready on its own.

It's built on Nextflow, so it scales from a laptop to a cluster without you
touching a line of code, and every run picks its own path automatically
based on whatever reads you point it at.

For the full technical picture — every branch of the pipeline broken down
by sequencing platform, the output folder layout, and a running log of
real bugs found (and fixed) along the way — see
[PIPELINE_SCHEME.txt](PIPELINE_SCHEME.txt).

**[Read the full documentation →](https://gabrielerigano99.github.io/bagASM/)**
A friendlier, example-driven walkthrough of every parameter, built with
Sphinx and deployed automatically on every push (see
[`.github/workflows/docs.yml`](.github/workflows/docs.yml)). It's also set
up to build on [Read the Docs](https://readthedocs.org) if you connect the
repo there instead. To build it locally:
`pip install -r docs/requirements.txt && sphinx-build -b html docs docs/_build`.

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
gap-fill with Redundans, strip out organelle contamination with chlomito,
then polish with Polypolish.

```bash
nextflow run GabrieleRigano99/bagASM \
  --r1 R1.fq.gz --r2 R2.fq.gz \
  --strain StrainID --outdir results
```

### 2. Long reads only

Point it at PacBio or ONT reads instead and it assembles with Flye, then
polishes with whatever suits the platform — medaka for ONT, racon for
PacBio-CLR, or nothing at all for PacBio-HiFi, which is already accurate
enough on its own.

```bash
nextflow run GabrieleRigano99/bagASM \
  --lr reads.fq.gz --lr_type ont \
  --strain StrainID --outdir results
```

`--lr_type` is one of `ont`, `pacbio-clr`, or `pacbio-hifi`.

### 3. Long reads + short reads

Give it both, and the short reads take over polishing duty from
medaka/racon — Polypolish tends to do a more thorough job when it has the
option. Having short reads around also means chlomito can run here too,
stripping organelle contamination the same way it does in short-read-only
mode (it has no long-read input option, so it sits out Mode 2 entirely).

```bash
nextflow run GabrieleRigano99/bagASM \
  --lr reads.fq.gz --lr_type ont \
  --r1 R1.fq.gz --r2 R2.fq.gz \
  --strain StrainID --outdir results
```

---

Every one of these accepts `StrainID` and `results` as just placeholders —
swap in your own sample name and output folder. Run
`nextflow run GabrieleRigano99/bagASM --help` for the complete option list:
multi-lane input (`--r1 a.fq.gz,b.fq.gz`), `--polish_rounds`, `--ont_mode`,
Filtlong/chlomito/medaka tuning, and more.

## Quality control

Every run finishes with QUAST and Qualimap bamqc checking over the final
assembly, no flags needed. Add `--busco_lineage fungi_odb12` (or any BUSCO
lineage name) to also run compleasm. `--runmerqury` (short-read mode only)
turns on Redundans' own bundled Merqury k-mer QV/completeness check.
