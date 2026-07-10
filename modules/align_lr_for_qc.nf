process ALIGN_LR_FOR_QC {
    tag "${strain}"
    label 'process_high'
    container 'gabrielerigano/bagasm-racon:1.0'

    input:
    tuple val(strain), path(assembly), path(lr), val(lr_type)

    output:
    tuple val(strain), path("${strain}_qc.sorted.bam"), path("${strain}_qc.sorted.bam.bai"), emit: bam

    script:
    def preset = [
        'ont'         : 'map-ont',
        'pacbio-clr'  : 'map-pb',
        'pacbio-hifi' : 'map-hifi'
    ][lr_type]
    """
    minimap2 -t ${task.cpus} -ax ${preset} ${assembly} ${lr.join(' ')} \\
        | samtools sort -@ ${task.cpus} -o ${strain}_qc.sorted.bam -
    samtools index ${strain}_qc.sorted.bam
    """

    stub:
    """
    touch ${strain}_qc.sorted.bam ${strain}_qc.sorted.bam.bai
    """
}
