process RENAME_SORT {
    tag "${strain}"
    label 'process_low'
    container 'quay.io/biocontainers/seqkit:2.13.0--he881be0_0'

    publishDir "${params.outdir}/assembly", mode: 'copy'

    input:
    tuple val(strain), path(assembly)

    output:
    tuple val(strain), path("${strain}_genome.fasta"), emit: fasta

    script:
    """
    seqkit sort --by-length --reverse ${assembly} \\
        | seqkit replace -p '.+' -r "${strain}_scaffold_{nr}" \\
        > ${strain}_genome.fasta
    """

    stub:
    """
    touch ${strain}_genome.fasta
    """
}
