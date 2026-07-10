process REDUNDANS {
    tag "${strain}"
    label 'process_high'
    // Derived from the upstream biocontainers image with a `cp` shim (see
    // docker/redundans_fix/cp-shim.sh): that image ships only BusyBox
    // coreutils, whose `cp` doesn't support GNU's `-t DEST` syntax, which
    // --runmerqury's meryl integration relies on ("cp: invalid option -- 't'",
    // crashing merqury_statistics() before it can parse meryl's output).
    // Confirmed on real data: without the shim this fails 100% of the time
    // --runmerqury is used, not just on tiny/edge-case inputs. Published on
    // Docker Hub, pulled automatically. Rebuild only if you change
    // docker/redundans_fix/*:
    //   docker build -t gabrielerigano/bagasm-redundans:1.0 docker/redundans_fix
    container 'gabrielerigano/bagasm-redundans:1.0'

    publishDir "${params.outdir}/assembly/redundans", mode: 'copy'

    input:
    tuple val(strain), path(scaffolds), path(r1), path(r2)

    output:
    tuple val(strain), path("${strain}_redundans_scaffolds.fasta"), emit: scaffolds
    path("${strain}_merqury_results"), emit: merqury, optional: true

    script:
    def mem_gb = Math.max(1, (int) (task.memory.toGiga()))
    def merqury_opt = params.runmerqury ? '--runmerqury' : ''
    """
    redundans.py \\
        -f ${scaffolds} \\
        -i ${r1} ${r2} \\
        --limit 1 \\
        -t ${task.cpus} -m ${mem_gb} \\
        -o redundans_out \\
        ${merqury_opt}

    cp redundans_out/scaffolds.reduced.fa ${strain}_redundans_scaffolds.fasta
    if [ -d redundans_out/merqury_results ]; then
        cp -r redundans_out/merqury_results ${strain}_merqury_results
    fi
    """

    stub:
    """
    touch ${strain}_redundans_scaffolds.fasta
    mkdir -p ${strain}_merqury_results
    """
}
