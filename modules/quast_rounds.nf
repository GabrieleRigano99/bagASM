process QUAST_ROUNDS {
    tag "${strain}"
    label 'process_medium'
    container 'quay.io/biocontainers/quast:5.3.0--py310pl5321h5140242_1'
    publishDir "${params.outdir}/qc/quast_rounds", mode: 'copy'

    input:
    tuple val(strain), path(rounds)

    output:
    path("${strain}_quast_rounds"), emit: report

    script:
    // QUAST's own multi-assembly comparison mode: one report.tsv with one
    // column per input, in the order given on the command line — so the
    // round*.fasta inputs must be sorted numerically here (round10 would
    // otherwise sort before round2 lexicographically) rather than relying
    // on however Nextflow staged the glob.
    def sorted = rounds.sort { a, b ->
        def na = (a.name =~ /_round(\d+)\.fasta$/)[0][1] as int
        def nb = (b.name =~ /_round(\d+)\.fasta$/)[0][1] as int
        na <=> nb
    }
    def labels = sorted.collect { (it.name =~ /_round(\d+)\.fasta$/)[0][1] }.collect { "round${it}" }
    """
    quast.py \\
        ${sorted.join(' ')} \\
        --fungus --eukaryote \\
        -l ${labels.join(',')} \\
        -o ${strain}_quast_rounds \\
        -t ${task.cpus}
    """

    stub:
    """
    mkdir -p ${strain}_quast_rounds
    """
}
