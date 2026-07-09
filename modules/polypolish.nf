process POLYPOLISH {
    tag "${strain}"
    label 'process_high'
    container 'gabrielerigano/bagasm-polish:1.0'
    // Build first: docker build -t gabrielerigano/bagasm-polish:1.0 docker/polish_env

    publishDir "${params.outdir}/assembly/polished", mode: 'copy'

    input:
    tuple val(strain), path(assembly), path(r1), path(r2)

    output:
    tuple val(strain), path("${strain}_polished.fasta"), emit: fasta

    script:
    """
    cp ${assembly} round0.fasta

    # minibwa: successor to bwa-mem, ~3x faster at comparable accuracy;
    # -a (report all alignments) matches Polypolish's own bwa-mem-based
    # tutorial, via minibwa's "mem" legacy-CLI subcommand.
    for i in \$(seq 1 ${params.polish_rounds}); do
        prev=\$((i - 1))
        minibwa index round\${prev}.fasta
        minibwa mem -t ${task.cpus} -a round\${prev}.fasta ${r1} > align_1.sam
        minibwa mem -t ${task.cpus} -a round\${prev}.fasta ${r2} > align_2.sam

        polypolish filter --in1 align_1.sam --in2 align_2.sam \\
            --out1 filtered_1.sam --out2 filtered_2.sam
        polypolish polish round\${prev}.fasta filtered_1.sam filtered_2.sam > round\${i}.fasta

        rm -f align_1.sam align_2.sam filtered_1.sam filtered_2.sam
    done

    cp round${params.polish_rounds}.fasta ${strain}_polished.fasta
    """

    stub:
    """
    touch ${strain}_polished.fasta
    """
}
