# bagASM

A Nextflow DSL2 pipeline for fungal genome assembly. Feed it Illumina short
reads, PacBio or ONT long reads, or both together, and it hands back a
decontaminated, polished nuclear assembly plus a separately extracted
mitochondrial genome.

The pipeline picks its own path automatically based on which inputs you
give it — there's no mode flag to set yourself. See
[Usage](usage.md) for a full walkthrough of all three modes, every
parameter, and the output layout.

Source, issue tracking, and the running log of real-data bugs found (and
fixed) along the way live at
[github.com/GabrieleRigano99/bagASM](https://github.com/GabrieleRigano99/bagASM).

```{toctree}
:maxdepth: 2
:caption: Contents

usage
```
