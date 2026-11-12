#!/usr/bin/env bash
# rotate-backups.sh - keep the newest N backups per prefix, delete the rest.
#
#   rotate-backups.sh [--dry-run] --config FILE DIR
#
# See SPEC.md for the exact rules and output format.

set -u

PROG=${0##*/}

usage_error() {
    echo "$PROG: $*" >&2
    echo "usage: $PROG [--dry-run] --config FILE DIR" >&2
    exit 2
}

die() {
    local code=$1
    shift
    echo "$PROG: $*" >&2
    exit "$code"
}

# Strip leading and trailing spaces/tabs.
trim() {
    local s=$1
    s=${s#"${s%%[![:blank:]]*}"}
    s=${s%"${s##*[![:blank:]]}"}
    printf '%s' "$s"
}

# ---------------------------------------------------------------- arguments

dry_run=0
config=
have_config=0
dir=
ndirs=0
opts_done=0

while [ $# -gt 0 ]; do
    arg=$1
    shift
    if [ "$opts_done" -eq 0 ]; then
        case $arg in
            --dry-run)
                dry_run=1
                continue
                ;;
            --config)
                [ $# -gt 0 ] || usage_error "--config needs a value"
                config=$1
                have_config=1
                shift
                continue
                ;;
            --)
                opts_done=1
                continue
                ;;
            -*)
                usage_error "unknown option: $arg"
                ;;
        esac
    fi
    dir=$arg
    ndirs=$((ndirs + 1))
done

[ "$have_config" -eq 1 ] || usage_error "--config is required"
[ "$ndirs" -eq 1 ] || usage_error "expected exactly one DIR"

# ---------------------------------------------------------------- config

[ -f "$config" ] && [ -r "$config" ] || die 3 "cannot read config: $config"

prefixes=()
keeps=()
nrules=0
lineno=0

while IFS= read -r line || [ -n "$line" ]; do
    lineno=$((lineno + 1))
    line=$(trim "$line")
    case $line in
        '' | '#'*) continue ;;
    esac

    keep=${line%%[[:blank:]]*}
    prefix=$(trim "${line#"$keep"}")

    case $keep in
        '' | *[!0-9]*) die 3 "$config:$lineno: KEEP must be a number" ;;
    esac
    [ ${#keep} -le 9 ] || die 3 "$config:$lineno: KEEP too large"
    [ -n "$prefix" ] || die 3 "$config:$lineno: missing prefix"
    case $prefix in
        *.* | */*) die 3 "$config:$lineno: prefix may not contain '.' or '/'" ;;
    esac
    i=0
    while [ "$i" -lt "$nrules" ]; do
        [ "${prefixes[$i]}" != "$prefix" ] || die 3 "$config:$lineno: duplicate prefix '$prefix'"
        i=$((i + 1))
    done

    prefixes[$nrules]=$prefix
    keeps[$nrules]=$keep
    nrules=$((nrules + 1))
done <"$config"

# ---------------------------------------------------------------- directory

[ -d "$dir" ] || die 4 "not a directory: $dir"

# ---------------------------------------------------------------- rotate

kept_total=0
deleted_total=0
status=0

i=0
while [ "$i" -lt "$nrules" ]; do
    prefix=${prefixes[$i]}
    keep=${keeps[$i]}
    i=$((i + 1))

    # Newest first.
    files=$(ls -t "$dir" | grep "^$prefix-")
    [ -n "$files" ] || continue
    total=$(printf '%s\n' "$files" | wc -l)

    # Everything after the first $keep lines goes, oldest first.
    old=$(printf '%s\n' "$files" | sed "1,${keep}d" | awk '{ l[NR] = $0 } END { for (n = NR; n > 0; n--) print l[n] }')
    nold=0
    [ -z "$old" ] || nold=$(printf '%s\n' "$old" | wc -l)
    kept_total=$((kept_total + total - nold))

    for f in $old; do
        if [ "$dry_run" -eq 1 ]; then
            echo "would delete: $f"
            deleted_total=$((deleted_total + 1))
        elif rm -f -- "$dir/$f"; then
            echo "deleted: $f"
            deleted_total=$((deleted_total + 1))
        else
            echo "$PROG: could not remove $dir/$f" >&2
            status=1
        fi
    done
done

if [ "$dry_run" -eq 1 ]; then
    echo "summary: kept $kept_total, would delete $deleted_total"
else
    echo "summary: kept $kept_total, deleted $deleted_total"
fi
exit "$status"
