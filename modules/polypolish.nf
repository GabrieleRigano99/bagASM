process POLYPOLISH {
    tag "${strain}"
    label 'process_high'
    // Published on Docker Hub, pulled automatically. Rebuild only if you
    // change docker/polish_env/Dockerfile:
    //   docker build -t gabrielerigano/bagasm-polish:1.0 docker/polish_env
    container 'gabrielerigano/bagasm-polish:1.0'

    publishDir "${params.outdir}/assembly/polished", mode: 'copy'

    input:
    tuple val(strain), path(assembly), path(r1), path(r2)

    output:
    tuple val(strain), path("${strain}_polished.fasta"), emit: fasta
    // Every intermediate round (round0 = pre-polish input, through roundN =
    // final), strain-prefixed so QUAST_ROUNDS can tell rounds apart across
    // strains once staged together; only consumed if --quast_per_round is set.
    tuple val(strain), path("${strain}_round*.fasta"), emit: rounds

    script:
    """
    cp ${assembly} ${strain}_round0.fasta

    # minibwa: successor to bwa-mem, ~3x faster at comparable accuracy;
    # -a (report all alignments) matches Polypolish's own bwa-mem-based
    # tutorial, via minibwa's "mem" legacy-CLI subcommand.
    for i in \$(seq 1 ${params.polish_rounds}); do
        prev=\$((i - 1))
        minibwa index ${strain}_round\${prev}.fasta
        minibwa mem -t ${task.cpus} -a ${strain}_round\${prev}.fasta ${r1} > align_1.sam
        minibwa mem -t ${task.cpus} -a ${strain}_round\${prev}.fasta ${r2} > align_2.sam

        polypolish filter --in1 align_1.sam --in2 align_2.sam \\
            --out1 filtered_1.sam --out2 filtered_2.sam
        polypolish polish ${strain}_round\${prev}.fasta filtered_1.sam filtered_2.sam > ${strain}_round\${i}.fasta

        rm -f align_1.sam align_2.sam filtered_1.sam filtered_2.sam
    done

    cp ${strain}_round${params.polish_rounds}.fasta ${strain}_polished.fasta
    """

    stub:
    """
    touch ${strain}_polished.fasta
    for i in \$(seq 0 ${params.polish_rounds}); do
        touch ${strain}_round\${i}.fasta
    done
    """
}
