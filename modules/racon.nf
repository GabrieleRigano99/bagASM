process RACON {
    tag "${strain}"
    label 'process_high'
    container 'gabrielerigano/bagasm-racon:1.0'
    // Build first: docker build -t gabrielerigano/bagasm-racon:1.0 docker/racon_env

    publishDir "${params.outdir}/assembly/polished", mode: 'copy'

    input:
    tuple val(strain), path(assembly), path(lr)   // lr: one or more long-read FASTQs

    output:
    tuple val(strain), path("${strain}_polished.fasta"), emit: fasta

    script:
    """
    # racon's <sequences> argument takes a single file (unlike minimap2, which
    # accepts multiple read files); pool multiple runs/flowcells first.
    cat ${lr.join(' ')} > ${strain}_lr.merged.fastq.gz

    minimap2 -t ${task.cpus} -ax map-pb ${assembly} ${strain}_lr.merged.fastq.gz > overlaps.sam
    racon -t ${task.cpus} ${strain}_lr.merged.fastq.gz overlaps.sam ${assembly} > ${strain}_polished.fasta

    rm ${strain}_lr.merged.fastq.gz
    """

    stub:
    """
    touch ${strain}_polished.fasta
    """
}
