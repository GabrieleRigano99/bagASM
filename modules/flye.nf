process FLYE {
    tag "${strain}"
    label 'process_high'
    container 'quay.io/biocontainers/flye:2.9.6--py310h5850263_1'

    publishDir "${params.outdir}/assembly/flye", mode: 'copy'

    input:
    tuple val(strain), path(lr), val(lr_type)   // lr: one or more long-read FASTQs

    output:
    tuple val(strain), path("${strain}_flye_assembly.fasta"), emit: assembly
    tuple val(strain), path("${strain}_flye_assembly_graph.gfa"), emit: graph
    path "${strain}_flye_assembly_info.txt", emit: info

    script:
    // --nano-hq targets modern high-accuracy (super/Dorado) ONT basecalls;
    // --nano-raw targets older/lower-accuracy runs (e.g. R9, fast/hac calling)
    // — pick via --ont_mode raw when --lr_type ont.
    def read_flag = [
        'ont'         : (params.ont_mode == 'raw' ? '--nano-raw' : '--nano-hq'),
        'pacbio-clr'  : '--pacbio-raw',
        'pacbio-hifi' : '--pacbio-hifi'
    ][lr_type]
    if (!read_flag) {
        error "Unknown --lr_type '${lr_type}': expected ont, pacbio-clr or pacbio-hifi"
    }
    """
    # Flye accepts multiple files (e.g. several runs/flowcells of the same
    # library) directly after the platform flag, no concatenation needed.
    flye \\
        ${read_flag} ${lr.join(' ')} \\
        --out-dir flye_out \\
        --threads ${task.cpus}

    cp flye_out/assembly.fasta ${strain}_flye_assembly.fasta
    cp flye_out/assembly_graph.gfa ${strain}_flye_assembly_graph.gfa
    cp flye_out/assembly_info.txt ${strain}_flye_assembly_info.txt
    """

    stub:
    """
    touch ${strain}_flye_assembly.fasta ${strain}_flye_assembly_graph.gfa ${strain}_flye_assembly_info.txt
    """
}
