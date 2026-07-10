process QUALIMAP_BAMQC {
    tag "${strain}"
    label 'process_medium'
    container 'quay.io/biocontainers/qualimap:2.3--hdfd78af_0'

    publishDir "${params.outdir}/qc/qualimap", mode: 'copy'

    input:
    tuple val(strain), path(bam), path(bai)

    output:
    path("${strain}_qualimap"), emit: report

    script:
    def mem_gb = Math.max(1, (int) (task.memory.toGiga()))
    """
    qualimap bamqc \\
        -bam ${bam} \\
        -outdir ${strain}_qualimap \\
        -outformat HTML \\
        -nt ${task.cpus} \\
        --java-mem-size=${mem_gb}G
    """

    stub:
    """
    mkdir -p ${strain}_qualimap
    """
}
