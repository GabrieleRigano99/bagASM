process FINAL_QC_REPORT {
    tag "${strain}"
    label 'process_low'
    // Just needs python3 for bin/combine_qc_report.py; reuses the
    // already-pulled racon image rather than adding a new dependency.
    container 'gabrielerigano/bagasm-racon:1.0'

    publishDir "${params.outdir}/qc/final_report", mode: 'copy'

    input:
    tuple val(strain), path(quast_dir), path(qualimap_dir), path(compleasm_dir)

    output:
    path("${strain}_final_report.md"), emit: report

    script:
    // compleasm_dir is the assets/NO_FILE sentinel when --busco_lineage
    // wasn't set (compleasm didn't run) — see main.nf.
    def compleasm_arg = (compleasm_dir.name == 'NO_FILE') ? '' : "--compleasm-dir ${compleasm_dir}"
    """
    combine_qc_report.py \\
        --strain ${strain} \\
        --quast-dir ${quast_dir} \\
        --qualimap-dir ${qualimap_dir} \\
        ${compleasm_arg} \\
        --output ${strain}_final_report.md
    """

    stub:
    """
    touch ${strain}_final_report.md
    """
}
