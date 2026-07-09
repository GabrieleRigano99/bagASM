process REDUNDANS {
    tag "${strain}"
    label 'process_high'
    container 'quay.io/biocontainers/redundans:2.01--py310pl5321h43eeafb_0'

    publishDir "${params.outdir}/assembly/redundans", mode: 'copy'

    input:
    tuple val(strain), path(scaffolds), path(r1), path(r2)

    output:
    tuple val(strain), path("${strain}_redundans_scaffolds.fasta"), emit: scaffolds

    script:
    def mem_gb = Math.max(1, (int) (task.memory.toGiga()))
    """
    redundans.py \\
        -f ${scaffolds} \\
        -i ${r1} ${r2} \\
        --limit 1 \\
        -t ${task.cpus} -m ${mem_gb} \\
        -o redundans_out

    cp redundans_out/scaffolds.reduced.fa ${strain}_redundans_scaffolds.fasta
    """

    stub:
    """
    touch ${strain}_redundans_scaffolds.fasta
    """
}
