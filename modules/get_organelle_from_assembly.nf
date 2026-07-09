process GET_ORGANELLE_FROM_ASSEMBLY {
    tag "${strain}"
    label 'process_medium'
    container 'quay.io/biocontainers/getorganelle:1.7.7.1--pyhdfd78af_0'

    publishDir "${params.outdir}/mitochondrion/get_organelle_from_assembly", mode: 'copy'

    input:
    tuple val(strain), path(graph)
    path(label_db)   // GET_ORGANELLE_SETUP.out.label_db, staged as ./LabelDatabase

    output:
    tuple val(strain), path("${strain}_mito_from_assembly.fasta"), env(N_SEQS), emit: result

    script:
    """
    get_organelle_from_assembly.py \\
        -g ${graph} \\
        -F fungus_mt \\
        --config-dir \$(pwd) \\
        -t ${task.cpus} \\
        -o goa_out || true

    # GetOrganelle names completed-path outputs '*complete*path_sequence.fasta';
    # concatenate whatever path FASTAs it produced (0 if extraction failed).
    cat goa_out/*path_sequence.fasta > ${strain}_mito_from_assembly.fasta 2>/dev/null || touch ${strain}_mito_from_assembly.fasta

    # grep -c prints a count (even 0) on both match and no-match, but exits 1
    # on no-match; chaining `|| echo 0` after it would append a second "0"
    # line instead of replacing it, so fall back via a separate default instead.
    N_SEQS_VAL=\$(grep -c '^>' ${strain}_mito_from_assembly.fasta 2>/dev/null)
    export N_SEQS=\${N_SEQS_VAL:-0}
    """

    stub:
    """
    echo ">stub_mito_contig" > ${strain}_mito_from_assembly.fasta
    echo "ACGT" >> ${strain}_mito_from_assembly.fasta
    export N_SEQS=1
    """
}
