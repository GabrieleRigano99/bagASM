process FILTLONG {
    tag "${strain}"
    label 'process_medium'
    container 'quay.io/biocontainers/filtlong:0.3.1--h077b44d_0'

    publishDir "${params.outdir}/trimmed_reads", mode: 'copy'

    input:
    tuple val(strain), path(lr)   // lr: one or more long-read FASTQs

    output:
    tuple val(strain), path("${strain}_lr.filtered.fastq.gz"), emit: reads

    script:
    """
    # filtlong takes a single (optionally gzipped) input file; pool multiple
    # runs/flowcells of the same library first, same as the other long-read
    # steps.
    cat ${lr.join(' ')} > ${strain}_lr.merged.fastq.gz

    filtlong \\
        --min_length ${params.filtlong_min_length} \\
        --keep_percent ${params.filtlong_keep_percent} \\
        ${strain}_lr.merged.fastq.gz \\
        | gzip > ${strain}_lr.filtered.fastq.gz

    rm ${strain}_lr.merged.fastq.gz
    """

    stub:
    """
    touch ${strain}_lr.filtered.fastq.gz
    """
}
