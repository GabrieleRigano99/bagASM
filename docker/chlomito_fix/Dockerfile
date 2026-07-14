FROM songweidocker/chlomito:v1

# The upstream image installs everything under /root with mode 700, so it
# only runs as UID 0. This pipeline runs all other containers as the host's
# non-root user (docker.runOptions -u $(id -u):$(id -g)) so output files come
# out owned by the invoking user, not root. Relax /root to world-readable +
# traversable (not writable) so chlomito works under that same non-root policy.
RUN chmod -R a+rX /root

# chlomito's contig-renaming step (Reformatted_Genome.fasta) keeps whatever
# characters the input assembly's headers already have, then later stages
# interpolate those names unquoted into shell commands (os.system, not
# subprocess with an arg list) -- a header containing "|" (Redundans' own
# "scaffoldN|sizeNNNNN" naming convention, confirmed against real output) is
# parsed by the shell as an actual pipe operator, breaking every downstream
# per-contig command. Not fixable in this Dockerfile (the "|" comes from
# our own pipeline's Redundans step, not from anything baked into the
# image) -- worked around instead by sanitizing "|" out of the assembly
# passed to chlomito, see modules/chlomito.nf.
#
# chlomito's own internal mitogenome re-extraction (GetOrganelle_assemble.py,
# invoked by __main__.py below) turned out to have three separate, unrelated
# bugs stacked on top of each other once actually exercised for real (all
# confirmed against real Sporothrix data, not guessed):
#   1. Its species dispatch checks for the literal string "fungus", but
#      chlomito's own CLI (-species) only accepts "fungi" -- so `database`
#      is never assigned and the real get_organelle_from_reads.py call is
#      skipped. This runs inside an unchecked multiprocessing.Pool worker
#      (apply_async, result never .get()'d), so the resulting NameError is
#      silently swallowed rather than raised.
#   2. Even with #1 fixed, chlomito's own bundled copy of GetOrganelle has
#      never had its reference database installed (`get_organelle_config.py
#      -a fungus_mt`) -- a separate, one-time setup step from the one this
#      pipeline's own GetOrganelle module already does for itself.
#   3. Even with #2 done, chlomito's bundled get_organelle_config.py itself
#      throws `KeyError: '0.0.1'` in its own version/hash lookup table --
#      an internal bug in this specific frozen dependency snapshot.
# Rather than keep patching an increasingly deep stack of bugs in a
# re-extraction step that's fundamentally redundant (this pipeline already
# runs its own real, validated GetOrganelle extraction upstream), this
# import is patched to skip GetOrganelle_assemble.py entirely and instead
# use that already-correct mitogenome directly: modules/chlomito.nf now
# stages it into the process work dir as "our_mitogenome.fasta", and this
# patch copies it straight into both paths chlomito's own comparison logic
# (mito_identify.py, unmodified) expects to find it at.
RUN sed -i \
    "s|^    os.system('python GetOrganelle_assemble.py %s %s %s'%(ngs1,ngs2,species))\$|    os.system('cp ../our_mitogenome.fasta ./organelle_db/mito_db.fasta')\n    os.system('cp ../our_mitogenome.fasta ./organelle_db/mito_genome.fasta')|" \
    /root/miniconda3/envs/getorganelle_env_2/lib/python3.8/site-packages/chlomito/__main__.py

# chlomito's own runtime code (confirmed by reading its .command.log under a
# real non-root run) unconditionally rm's and re-populates
# /opt/organelle_db/{mito,chlo}_genome.fasta and stages its bundled
# GetOrganelle_assemble.py/mito_identify.py scripts into /opt/scripts on
# every invocation -- it does not fall back gracefully if that fails. Under
# this pipeline's non-root policy every one of those operations silently
# failed with "Permission denied"/"No such file or directory" (root-owned
# /opt, and some files under it were even mode 600), but the process still
# exited 0 -- so chlomito silently skipped ever extracting the sample's own
# mitogenome and fell back to comparing against whatever stale reference
# genome happened to already be baked into the image from the upstream
# maintainer's own unrelated 2022 test run, meaning real contamination was
# never actually detected. Making /opt writable lets chlomito's own
# regeneration step succeed instead of silently no-op'ing.
RUN chmod -R a+rwX /opt
