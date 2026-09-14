process FASTP {
    tag "${strain}"
    label 'process_medium'
    container 'quay.io/biocontainers/fastp:1.3.6--h43da1c4_0'

    publishDir "${params.outdir}/trimmed_reads", mode: 'copy'

    input:
    tuple val(strain), path(r1), path(r2)   // r1/r2: one or more lane FASTQs per direction

    output:
    tuple val(strain), path("${strain}_R1.trimmed.fastq.gz"), path("${strain}_R2.trimmed.fastq.gz"), emit: reads
    path "${strain}.fastp.html", emit: html, optional: true
    path "${strain}.fastp.json", emit: json, optional: true

    script:
    """
    # Multiple lanes of the same library are pooled by concatenating the
    # (optionally gzipped) FASTQs; concatenated multi-member gzip is valid
    # and fastp reads it correctly. fastp itself decides whether to
    # gunzip on read purely from the .fastq.gz name, not the actual file
    # content -- a plain-text lane file just `cat`-ed into a .gz-named
    # merge crashes it ("invalid gzip header found"). gzip -t (BusyBox-
    # compatible, confirmed inside this container; zcat -f is not) checks
    # each lane file's real compression state so plain and gzipped lanes
    # can even be mixed across --r1/--r2. This pooling/normalizing always
    # happens, even with --skip_trimming, since every downstream step
    # expects one real-gzip R1/R2 file per strain regardless.
    normalize_gzip() {
        for f in "\$@"; do
            if gzip -t "\$f" 2>/dev/null; then
                cat "\$f"
            else
                gzip -c "\$f"
            fi
        done
    }
    normalize_gzip ${r1.join(' ')} > ${strain}_R1.merged.fastq.gz
    normalize_gzip ${r2.join(' ')} > ${strain}_R2.merged.fastq.gz

    if [ "${params.skip_trimming}" = "true" ]; then
        # Skip fastp entirely -- no adapter/quality/length trimming, no
        # HTML/JSON QC report, just the pooled/gzip-normalized reads
        # untouched.
        mv ${strain}_R1.merged.fastq.gz ${strain}_R1.trimmed.fastq.gz
        mv ${strain}_R2.merged.fastq.gz ${strain}_R2.trimmed.fastq.gz
    else
        fastp \\
            -i ${strain}_R1.merged.fastq.gz -I ${strain}_R2.merged.fastq.gz \\
            -o ${strain}_R1.trimmed.fastq.gz -O ${strain}_R2.trimmed.fastq.gz \\
            --detect_adapter_for_pe \\
            --thread ${task.cpus} \\
            --html ${strain}.fastp.html \\
            --json ${strain}.fastp.json

        rm ${strain}_R1.merged.fastq.gz ${strain}_R2.merged.fastq.gz
    fi
    """

    stub:
    """
    touch ${strain}_R1.trimmed.fastq.gz ${strain}_R2.trimmed.fastq.gz ${strain}.fastp.html ${strain}.fastp.json
    """
}
