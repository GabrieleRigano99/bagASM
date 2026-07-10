#!/bin/sh
# The base image provides only BusyBox coreutils, whose `cp` doesn't support
# GNU's `-t DEST` (target-directory-first) syntax. Redundans' bundled
# Merqury integration (via meryl) calls `cp -t DEST SRC...`, which crashes
# with "cp: invalid option -- 't'" under BusyBox. Translate that one form to
# BusyBox-compatible `SRC... DEST` and defer to BusyBox for everything else.
if [ "$1" = "-t" ]; then
    dest="$2"
    shift 2
    exec busybox cp "$@" "$dest"
fi
exec busybox cp "$@"
