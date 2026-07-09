# bagASM

![bagASM.png](bagASM_logo.png)

Fungal genome assembly pipeline (Nextflow DSL2). Takes Illumina short reads,
PacBio/ONT long reads, or both, and produces a decontaminated, polished
nuclear assembly plus a separately extracted mitochondrial genome.

See [PIPELINE_SCHEME.txt](PIPELINE_SCHEME.txt) for the full flow (all five
run modes), output layout, and a running list of real-data bugs found and
fixed, with rationale for each.

## Requirements

- Nextflow `>=25.04.6,<26`, Java 21
- Docker, with the local (non-remote) executor — several steps depend on
  Docker-specific behavior (see caveats in PIPELINE_SCHEME.txt)

## Setup

No manual image build needed — `gabrielerigano/bagasm-polish:1.0`,
`gabrielerigano/bagasm-racon:1.0`, and `gabrielerigano/bagasm-chlomito:1.0`
are published on Docker Hub and pulled automatically on first use. The
`docker/*/Dockerfile` sources are kept in the repo for transparency/rebuilds
only.

The GetOrganelle `fungus_mt` reference database downloads automatically on
first run and is cached in `assets/getorganelle_db/` (override with
`--getorganelle_db`) — not re-downloaded on later runs.

## Usage

Pull once, then run by GitHub path (no local clone needed):

```bash
nextflow pull GabrieleRigano99/bagASM
```

Short reads only:

```bash
nextflow run GabrieleRigano99/bagASM \
  --r1 R1.fq.gz --r2 R2.fq.gz \
  --strain StrainID --outdir results
```

Long reads (optionally with short reads for polishing):

```bash
nextflow run GabrieleRigano99/bagASM \
  --lr reads.fq.gz --lr_type ont \
  [--r1 R1.fq.gz --r2 R2.fq.gz] \
  --strain StrainID --outdir results
```

(Or clone the repo and use `nextflow run main.nf` the same way, if you'd
rather work from a local checkout.)

`--lr_type` is one of `ont`, `pacbio-clr`, `pacbio-hifi`. Run
`nextflow run GabrieleRigano99/bagASM --help` for the full option list,
including multi-lane input (`--r1 a.fq.gz,b.fq.gz`), `--polish_rounds`,
`--ont_mode`, and the chlomito/medaka tuning knobs.

## Layout

```
main.nf                  entry point: mode selection + workflow wiring
nextflow.config           params, resource labels, container/profile settings
modules/                  one process per file
docker/*/Dockerfile       custom image sources (published pre-built, see "Setup")
assets/getorganelle_db/   cached reference database (gitignored, auto-populated)
```
