process SPADES {
    tag "${strain}"
    label 'process_high'
    container 'quay.io/biocontainers/spades:4.3.0--hde4eca7_0'

    publishDir "${params.outdir}/assembly/spades", mode: 'copy'

    input:
    tuple val(strain), path(r1), path(r2)

    output:
    tuple val(strain), path("${strain}_scaffolds.fasta"), emit: scaffolds
    tuple val(strain), path("${strain}_assembly_graph.fastg"), emit: graph
    path "${strain}_spades.log", emit: log

    script:
    def mem_gb = Math.max(1, (int) (task.memory.toGiga()))
    """
    spades.py \\
        -1 ${r1} -2 ${r2} \\
        -k 27,37,55,77,99,111,127 \\
        --only-assembler --careful \\
        -t ${task.cpus} -m ${mem_gb} \\
        -o spades_out

    cp spades_out/scaffolds.fasta ${strain}_scaffolds.fasta
    # fastg (not the default GFA v1.2): GetOrganelle 1.7.7.1's GFA parser
    # can't read SPAdes 4.x's GFA v1.2 ("Unrecognized GFA version number: 1.2"),
    # but SPAdes always emits this equivalent older-format graph too.
    cp spades_out/assembly_graph.fastg ${strain}_assembly_graph.fastg
    cp spades_out/spades.log ${strain}_spades.log
    """

    stub:
    """
    touch ${strain}_scaffolds.fasta ${strain}_assembly_graph.fastg ${strain}_spades.log
    """
}
