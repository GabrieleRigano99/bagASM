process COMPLEASM {
    tag "${strain}"
    label 'process_medium'
    container 'quay.io/biocontainers/compleasm:0.2.8--pyh106432d_0'
    // compleasm downloads+caches the requested lineage into -L itself (no
    // separate setup step needed); bind-mount that persistent host directory
    // in, since it isn't a Nextflow-tracked input/output.
    containerOptions { "-v ${params.compleasm_db}:${params.compleasm_db}" }

    publishDir "${params.outdir}/qc/compleasm", mode: 'copy'

    input:
    tuple val(strain), path(assembly)

    output:
    path("${strain}_compleasm"), emit: report

    script:
    // params.compleasm_db must already exist on the host (created by main.nf
    // before any task runs) — if Docker auto-creates the bind-mount source
    // instead, it does so as root, and compleasm (running as the host's
    // non-root user) can't write its downloaded lineage into it.
    """
    compleasm run \\
        -a ${assembly} \\
        -o ${strain}_compleasm \\
        -l ${params.busco_lineage} \\
        -L ${params.compleasm_db} \\
        -t ${task.cpus}
    """

    stub:
    """
    mkdir -p ${strain}_compleasm
    """
}
