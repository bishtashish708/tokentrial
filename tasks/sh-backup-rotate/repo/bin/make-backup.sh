#!/usr/bin/env bash
# make-backup.sh - archive a directory into a timestamped tarball.
#
#   make-backup.sh PREFIX SRC DIR
#
# Creates DIR/PREFIX-YYYYMMDDTHHMMSS.tar.gz (UTC) and prints its path. The name format is
# the one rotate-backups.sh expects.

set -eu

if [ $# -ne 3 ]; then
    echo "usage: ${0##*/} PREFIX SRC DIR" >&2
    exit 2
fi

prefix=$1
src=$2
dest=$3

case $prefix in
    '' | *.* | */*)
        echo "${0##*/}: PREFIX must be non-empty and contain no '.' or '/'" >&2
        exit 2
        ;;
esac
[ -d "$src" ] || { echo "${0##*/}: not a directory: $src" >&2; exit 2; }
[ -d "$dest" ] || { echo "${0##*/}: not a directory: $dest" >&2; exit 2; }

stamp=$(date -u +%Y%m%dT%H%M%S)
out="$dest/$prefix-$stamp.tar.gz"
tmp="$dest/.partial-$prefix-$stamp"  # dot-file: invisible to rotation

trap 'rm -f "$tmp"' EXIT
(cd "$src" && tar -cf - .) | gzip -c >"$tmp"
mv "$tmp" "$out"
trap - EXIT

echo "$out"
