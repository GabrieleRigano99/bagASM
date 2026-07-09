process CHLOMITO {
    tag "${strain}"
    label 'process_high'
    // Derived from songweidocker/chlomito:v1 with /root made world-readable+
    // traversable (build: docker build -t gabrielerigano/bagasm-chlomito:1.0
    // docker/chlomito_fix) — the upstream image installs everything under
    // /root at mode 700, which the pipeline-wide non-root docker.runOptions
    // (-u $(id -u):$(id -g)) can't even traverse into, let alone execute.
    container 'gabrielerigano/bagasm-chlomito:1.0'
    // chlomito shells out to sibling containers internally, so the Docker socket
    // must be mounted through; this only works with the local Docker executor
    // (not Singularity/Apptainer or remote schedulers).
    containerOptions '-v /var/run/docker.sock:/var/run/docker.sock'

    publishDir "${params.outdir}/assembly/chlomito", mode: 'copy'

    input:
    tuple val(strain), path(assembly), path(r1), path(r2)

    output:
    // Confirmed against a real run: chlomito writes the decontaminated,
    // header-renamed assembly to <-output>/Reformatted_Genome.fasta,
    // alongside organelle_db/ (its internally-built mito/chlo references
    // and BLAST dbs used for the ALCR/SDR comparison).
    tuple val(strain), path("${strain}_chlomito_out/Reformatted_Genome.fasta"), emit: decontaminated
    path "${strain}_chlomito_out", emit: raw_dir

    script:
    """
    chlomito \\
        -species fungi \\
        -raw_genome ${assembly} \\
        -NGS_1 ${r1} -NGS_2 ${r2} \\
        -output ${strain}_chlomito_out \\
        -mito_ALCR_cutoff ${params.chlomito_mito_alcr_cutoff} \\
        -mito_SDR_cutoff ${params.chlomito_mito_sdr_cutoff} \\
        -threads ${task.cpus}
    """

    stub:
    """
    mkdir -p ${strain}_chlomito_out
    touch ${strain}_chlomito_out/Reformatted_Genome.fasta
    """
}
