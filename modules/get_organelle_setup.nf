process GET_ORGANELLE_SETUP {
    label 'process_low'
    container 'quay.io/biocontainers/getorganelle:1.7.7.1--pyhdfd78af_0'

    // Cached permanently, keyed by --species: downloaded once per requested
    // organelle type, reused by every future run regardless of --strain.
    // storeDir skips re-running whenever its declared outputs already exist,
    // with no regard for *which* species was requested — keying the path on
    // params.species (rather than a single shared getorganelle_db/ root)
    // keeps switching --species from silently reusing a stale cache that
    // never actually downloaded the newly-requested organelle type.
    storeDir "${params.getorganelle_db}/${params.species}"

    output:
    path 'LabelDatabase', emit: label_db
    path 'SeedDatabase',  emit: seed_db

    script:
    """
    get_organelle_config.py -a ${params.species} --config-dir \$(pwd)
    """

    stub:
    """
    mkdir -p LabelDatabase SeedDatabase
    """
}
