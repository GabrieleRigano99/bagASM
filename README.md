# bagASM - An easy to use _de novo_ Genome Assembly Pipeline!

![bagASM_logo.png](bagASM_logo.png)

bagASM has been takes Illumina short reads, PacBio/ONT long reads, or both, and produces a decontaminated, polished
nuclear assembly plus a separately extracted mitochondrial genome.

See [PIPELINE_SCHEME.txt](PIPELINE_SCHEME.txt) for the full flow (all five
run modes), output layout, and a running list of real-data bugs found and
fixed, with rationale for each.

## Requirements

- Nextflow `>=25.04.6,<26`, Java 21
- Docker, with the local (non-remote) executor — several steps depend on
  Docker-specific behavior (see caveats in PIPELINE_SCHEME.txt)

## Setup

The GetOrganelle `fungus_mt` reference database downloads automatically on
first run and is cached in `assets/getorganelle_db/` (override with
`--getorganelle_db`) — not re-downloaded on later runs. Same idea for
compleasm's BUSCO lineage data, cached in `assets/compleasm_db/` (override
with `--compleasm_db`) whenever `--busco_lineage` is set.

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

## Quality control

QUAST and Qualimap bamqc always run on the final assembly. Add
`--busco_lineage fungi_odb12` (or any BUSCO lineage name) to also run
compleasm. `--runmerqury` (short-read mode only) turns on Redundans' own
bundled Merqury k-mer QV/completeness check.
