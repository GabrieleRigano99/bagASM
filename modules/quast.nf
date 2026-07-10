process QUAST {
    tag "${strain}"
    label 'process_medium'
    container 'quay.io/biocontainers/quast:5.3.0--py310pl5321h5140242_1'

    publishDir "${params.outdir}/qc/quast", mode: 'copy'

    input:
    tuple val(strain), path(assembly)

    output:
    path("${strain}_quast"), emit: report

    script:
    """
    quast.py \\
        ${assembly} \\
        --fungus --eukaryote \\
        -l ${strain} \\
        -o ${strain}_quast \\
        -t ${task.cpus}
    """

    stub:
    """
    mkdir -p ${strain}_quast
    """
}
