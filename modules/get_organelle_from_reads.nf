process GET_ORGANELLE_FROM_READS {
    tag "${strain}"
    label 'process_high'
    container 'quay.io/biocontainers/getorganelle:1.7.7.1--pyhdfd78af_0'

    publishDir "${params.outdir}/mitochondrion/get_organelle_from_reads", mode: 'copy'

    input:
    tuple val(strain), path(r1), path(r2)
    path(label_db)   // GET_ORGANELLE_SETUP.out.label_db, staged as ./LabelDatabase
    path(seed_db)    // GET_ORGANELLE_SETUP.out.seed_db,  staged as ./SeedDatabase

    output:
    tuple val(strain), path("${strain}_mito_from_reads.fasta"), emit: fasta

    script:
    """
    get_organelle_from_reads.py \\
        -1 ${r1} -2 ${r2} \\
        -F fungus_mt \\
        --config-dir \$(pwd) \\
        -t ${task.cpus} \\
        -o gor_out || true

    cat gor_out/*path_sequence.fasta > ${strain}_mito_from_reads.fasta 2>/dev/null || touch ${strain}_mito_from_reads.fasta
    """

    stub:
    """
    echo ">stub_mito_contig" > ${strain}_mito_from_reads.fasta
    echo "ACGT" >> ${strain}_mito_from_reads.fasta
    """
}
