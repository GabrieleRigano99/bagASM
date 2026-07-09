process FASTP {
    tag "${strain}"
    label 'process_medium'
    container 'quay.io/biocontainers/fastp:1.3.6--h43da1c4_0'

    publishDir "${params.outdir}/trimmed_reads", mode: 'copy'

    input:
    tuple val(strain), path(r1), path(r2)   // r1/r2: one or more lane FASTQs per direction

    output:
    tuple val(strain), path("${strain}_R1.trimmed.fastq.gz"), path("${strain}_R2.trimmed.fastq.gz"), emit: reads
    path "${strain}.fastp.html", emit: html
    path "${strain}.fastp.json", emit: json

    script:
    """
    # Multiple lanes of the same library are pooled by concatenating the
    # (optionally gzipped) FASTQs; concatenated multi-member gzip is valid
    # and fastp reads it correctly.
    cat ${r1.join(' ')} > ${strain}_R1.merged.fastq.gz
    cat ${r2.join(' ')} > ${strain}_R2.merged.fastq.gz

    fastp \\
        -i ${strain}_R1.merged.fastq.gz -I ${strain}_R2.merged.fastq.gz \\
        -o ${strain}_R1.trimmed.fastq.gz -O ${strain}_R2.trimmed.fastq.gz \\
        --detect_adapter_for_pe \\
        --thread ${task.cpus} \\
        --html ${strain}.fastp.html \\
        --json ${strain}.fastp.json

    rm ${strain}_R1.merged.fastq.gz ${strain}_R2.merged.fastq.gz
    """

    stub:
    """
    touch ${strain}_R1.trimmed.fastq.gz ${strain}_R2.trimmed.fastq.gz ${strain}.fastp.html ${strain}.fastp.json
    """
}
