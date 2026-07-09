FROM songweidocker/chlomito:v1

# The upstream image installs everything under /root with mode 700, so it
# only runs as UID 0. This pipeline runs all other containers as the host's
# non-root user (docker.runOptions -u $(id -u):$(id -g)) so output files come
# out owned by the invoking user, not root. Relax /root to world-readable +
# traversable (not writable) so chlomito works under that same non-root policy.
RUN chmod -R a+rX /root
