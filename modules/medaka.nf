process MEDAKA {
    tag "${strain}"
    label 'process_high'
    container 'quay.io/biocontainers/medaka:2.2.2--py312h3050eb1_0'

    publishDir "${params.outdir}/assembly/polished", mode: 'copy'

    input:
    tuple val(strain), path(assembly), path(lr)   // lr: one or more long-read FASTQs

    output:
    tuple val(strain), path("${strain}_polished.fasta"), emit: fasta

    script:
    // model auto-selected from the input basecalls unless --medaka_model is set
    def model_opt = params.medaka_model ? "-m ${params.medaka_model}" : ''
    """
    # medaka_consensus's -i takes a single file; pool multiple runs/flowcells
    # of the same library first (valid as concatenated multi-member gzip).
    cat ${lr.join(' ')} > ${strain}_lr.merged.fastq.gz

    medaka_consensus \\
        -i ${strain}_lr.merged.fastq.gz -d ${assembly} \\
        -o medaka_out -t ${task.cpus} ${model_opt}

    cp medaka_out/consensus.fasta ${strain}_polished.fasta
    rm ${strain}_lr.merged.fastq.gz
    """

    stub:
    """
    touch ${strain}_polished.fasta
    """
}
