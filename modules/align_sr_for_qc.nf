process ALIGN_SR_FOR_QC {
    tag "${strain}"
    label 'process_high'
    container 'gabrielerigano/bagasm-polish:1.0'

    input:
    tuple val(strain), path(assembly), path(r1), path(r2)

    output:
    tuple val(strain), path("${strain}_qc.sorted.bam"), path("${strain}_qc.sorted.bam.bai"), emit: bam

    script:
    """
    minibwa index ${assembly}
    minibwa mem -t ${task.cpus} ${assembly} ${r1} ${r2} \\
        | samtools sort -@ ${task.cpus} -o ${strain}_qc.sorted.bam -
    samtools index ${strain}_qc.sorted.bam
    """

    stub:
    """
    touch ${strain}_qc.sorted.bam ${strain}_qc.sorted.bam.bai
    """
}
