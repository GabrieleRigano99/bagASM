process GET_ORGANELLE_SETUP {
    label 'process_low'
    container 'quay.io/biocontainers/getorganelle:1.7.7.1--pyhdfd78af_0'

    // Cached permanently in params.getorganelle_db: downloaded once, reused by
    // every future run regardless of --strain, unlike the regular work dir.
    storeDir params.getorganelle_db

    output:
    path 'LabelDatabase', emit: label_db
    path 'SeedDatabase',  emit: seed_db

    script:
    """
    get_organelle_config.py -a fungus_mt --config-dir \$(pwd)
    """

    stub:
    """
    mkdir -p LabelDatabase SeedDatabase
    """
}
