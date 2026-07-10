process DECONTAM_ORGANELLE_LR {
    tag "${strain}"
    label 'process_high'
    container 'gabrielerigano/bagasm-racon:1.0'

    publishDir "${params.outdir}/assembly/decontam_lr", mode: 'copy'

    input:
    tuple val(strain), path(assembly), path(mito_ref), path(lr), val(lr_type)

    output:
    tuple val(strain), path("${strain}_decontam.fasta"), emit: decontaminated
    path("${strain}_decontam_report.tsv"), emit: report

    script:
    // Reimplements chlomito's ALCR+SDR approach natively for long reads,
    // since chlomito itself has no long-read input mode (it requires
    // paired short reads for its depth-ratio metric) — see
    // bin/decontam_organelle_lr.py for the full rationale and the metric
    // definitions.
    def preset = [
        'ont'         : 'map-ont',
        'pacbio-clr'  : 'map-pb',
        'pacbio-hifi' : 'map-hifi'
    ][lr_type]
    """
    minimap2 -x asm5 -t ${task.cpus} ${mito_ref} ${assembly} > contigs_vs_mito.paf

    minimap2 -ax ${preset} -t ${task.cpus} ${assembly} ${lr.join(' ')} \\
        | samtools sort -@ ${task.cpus} -o reads_vs_assembly.bam -

    minimap2 -ax ${preset} -t ${task.cpus} ${mito_ref} ${lr.join(' ')} \\
        | samtools sort -@ ${task.cpus} -o reads_vs_mito.bam -

    decontam_organelle_lr.py \\
        --assembly ${assembly} \\
        --mito-ref ${mito_ref} \\
        --reads-vs-assembly-bam reads_vs_assembly.bam \\
        --reads-vs-mito-bam reads_vs_mito.bam \\
        --contigs-vs-mito-paf contigs_vs_mito.paf \\
        --alcr-cutoff ${params.lr_decontam_alcr_cutoff} \\
        --sdr-cutoff ${params.lr_decontam_sdr_cutoff} \\
        --threads ${task.cpus} \\
        --output-fasta ${strain}_decontam.fasta \\
        --output-report ${strain}_decontam_report.tsv
    """

    stub:
    """
    touch ${strain}_decontam.fasta ${strain}_decontam_report.tsv
    """
}
