process DECONTAM_ORGANELLE {
    tag "${strain}"
    label 'process_high'
    container 'gabrielerigano/bagasm-racon:1.0'

    publishDir "${params.outdir}/assembly/decontam", mode: 'copy'

    input:
    tuple val(strain), path(assembly), path(mito_ref), path(reads), val(platform)

    output:
    tuple val(strain), path("${strain}_decontam.fasta"), emit: decontaminated
    path("${strain}_decontam_report.tsv"), emit: report

    script:
    // Native ALCR+SDR reimplementation of chlomito's own detection approach,
    // used for every mode (short-read, long-read, and hybrid) since chlomito
    // itself proved too unreliable to depend on: eight distinct, unrelated
    // bugs turned up across four of its bundled scripts once actually
    // exercised for real (species-string mismatches, unquoted shell
    // interpolation breaking on ordinary FASTA header characters, missing
    // glue code, a stale/frozen samtools crashing under its own hardcoded
    // thread count, and more — see git history on modules/chlomito.nf and
    // docker/chlomito_fix/Dockerfile for the full trail). This reuses the
    // pipeline's own already-validated GetOrganelle extraction instead of
    // re-extracting anything, so there's no separate database/species
    // logic to get out of sync with. See bin/decontam_organelle.py for the
    // metric definitions themselves.
    //
    // "reads" is [r1, r2] for platform 'sr', or one-or-more long-read files
    // for 'ont'/'pacbio-clr'/'pacbio-hifi' — minimap2 takes any number of
    // read files after the platform flag either way, so the same command
    // shape works unmodified for both.
    def preset = [
        'sr'          : 'sr',
        'ont'         : 'map-ont',
        'pacbio-clr'  : 'map-pb',
        'pacbio-hifi' : 'map-hifi'
    ][platform]
    """
    minimap2 -x asm5 -t ${task.cpus} ${mito_ref} ${assembly} > contigs_vs_mito.paf

    minimap2 -ax ${preset} -t ${task.cpus} ${assembly} ${reads.join(' ')} \\
        | samtools sort -@ ${task.cpus} -o reads_vs_assembly.bam -

    minimap2 -ax ${preset} -t ${task.cpus} ${mito_ref} ${reads.join(' ')} \\
        | samtools sort -@ ${task.cpus} -o reads_vs_mito.bam -

    decontam_organelle.py \\
        --assembly ${assembly} \\
        --mito-ref ${mito_ref} \\
        --reads-vs-assembly-bam reads_vs_assembly.bam \\
        --reads-vs-mito-bam reads_vs_mito.bam \\
        --contigs-vs-mito-paf contigs_vs_mito.paf \\
        --alcr-cutoff ${params.decontam_alcr_cutoff} \\
        --sdr-cutoff ${params.decontam_sdr_cutoff} \\
        --threads ${task.cpus} \\
        --output-fasta ${strain}_decontam.fasta \\
        --output-report ${strain}_decontam_report.tsv
    """

    stub:
    """
    touch ${strain}_decontam.fasta ${strain}_decontam_report.tsv
    """
}