process FINALIZE_MITOGENOME {
    tag "${strain}"
    label 'process_low'
    container 'quay.io/biocontainers/seqkit:2.13.0--he881be0_0'

    publishDir "${params.outdir}/mitochondrion", mode: 'copy'

    input:
    tuple val(strain), path(fasta)

    output:
    tuple val(strain), path("${strain}_mitogenome.fasta")

    script:
    """
    cp ${fasta} ${strain}_mitogenome.fasta
    """

    stub:
    """
    touch ${strain}_mitogenome.fasta
    """
}
