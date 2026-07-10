FROM quay.io/biocontainers/redundans:2.01--py310pl5321h43eeafb_0

# See cp-shim.sh: the base image ships only BusyBox coreutils, and
# Redundans' --runmerqury (via meryl) calls `cp -t DEST SRC...`, which
# BusyBox's cp doesn't support ("cp: invalid option -- 't'"), crashing
# merqury_statistics() before it can parse meryl's output. /usr/local/bin
# is already first in PATH ahead of /bin (where BusyBox's cp lives), so this
# shim shadows it without touching anything else in the image.
COPY cp-shim.sh /usr/local/bin/cp
RUN chmod +x /usr/local/bin/cp
