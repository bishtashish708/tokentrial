#!/usr/bin/env bash
# Tests for bin/rotate-backups.sh. Run with: bash tests/run-tests.sh
# Works with bash 3.2 and newer. Uses a fresh temporary directory per test.

set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SCRIPT="$ROOT/bin/rotate-backups.sh"
BASH_BIN=${BASH:-bash}

TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/rotate-tests.XXXXXX")
trap 'rm -rf "$TMP_ROOT"' EXIT

pass=0
fail=0
current=

# ------------------------------------------------------------------ helpers

begin() {
    current=$1
    T="$TMP_ROOT/$(printf '%03d' $((pass + fail)))"
    mkdir -p "$T/backups"
    D="$T/backups"
    C="$T/rotate.conf"
    : >"$C"
    test_failed=0
}

# conf LINE...: write the config file, one argument per line.
conf() {
    printf '%s\n' "$@" >"$C"
}

# mk NAME...: create backup files; mtime follows the timestamp in the name when there is one.
mk() {
    local name ts
    for name in "$@"; do
        : >"$D/$name"
        ts=$(printf '%s\n' "$name" | sed -n 's/.*-\([0-9]\{8\}\)T\([0-9]\{4\}\)\([0-9]\{2\}\).*/\1\2.\3/p')
        if [ -n "$ts" ]; then
            touch -t "$ts" "$D/$name"
        fi
    done
}

# run ARGS...: run the script, capturing stdout in $OUT and the exit status in $RC.
run() {
    OUT=$("$BASH_BIN" "$SCRIPT" "$@" 2>"$T/stderr")
    RC=$?
}

# remaining: sorted listing of the backup directory, one name per line.
remaining() {
    (cd "$D" && ls -1A | LC_ALL=C sort)
}

check() {
    # check DESCRIPTION EXPECTED ACTUAL
    if [ "$2" != "$3" ]; then
        test_failed=1
        echo "FAIL [$current] $1"
        echo "  expected: $(printf '%s' "$2" | sed 's/^/    /')"
        echo "  actual:   $(printf '%s' "$3" | sed 's/^/    /')"
    fi
}

end() {
    if [ "$test_failed" -eq 0 ]; then
        pass=$((pass + 1))
        echo "ok   [$current]"
    else
        fail=$((fail + 1))
    fi
}

lines() {
    printf '%s\n' "$@"
}

# ------------------------------------------------------------------ tests

begin "dry run lists the oldest backups and deletes nothing"
conf "# keep prefix" "2 db"
mk db-20250101T020000.sql.gz db-20250102T020000.sql.gz db-20250103T020000.sql.gz \
    db-20250104T020000.sql.gz db-20250105T020000.sql.gz
before=$(remaining)
run --dry-run --config "$C" "$D"
check "exit status" 0 "$RC"
check "stdout" "$(lines \
    'would delete: db-20250101T020000.sql.gz' \
    'would delete: db-20250102T020000.sql.gz' \
    'would delete: db-20250103T020000.sql.gz' \
    'summary: kept 2, would delete 3')" "$OUT"
check "directory unchanged" "$before" "$(remaining)"
end

begin "real run deletes and reports"
conf "3 web"
mk web-20240301T000000.tar web-20240302T000000.tar web-20240303T000000.tar \
    web-20240304T000000.tar
run --config "$C" "$D"
check "exit status" 0 "$RC"
check "stdout" "$(lines 'deleted: web-20240301T000000.tar' 'summary: kept 3, deleted 1')" "$OUT"
check "remaining" "$(lines web-20240302T000000.tar web-20240303T000000.tar web-20240304T000000.tar)" \
    "$(remaining)"
end

begin "keep larger than the number of backups"
conf "10 web"
mk web-20240301T000000.tar web-20240302T000000.tar
run --config "$C" "$D"
check "stdout" "summary: kept 2, deleted 0" "$OUT"
check "remaining" "$(lines web-20240301T000000.tar web-20240302T000000.tar)" "$(remaining)"
end

begin "unrelated files are never touched or counted"
conf "1 db"
mk db-20250101T000000.sql db-20250102T000000.sql notes.txt db-latest.sql cache-20200101T000000.bin
run --config "$C" "$D"
check "stdout" "$(lines 'deleted: db-20250101T000000.sql' 'summary: kept 1, deleted 1')" "$OUT"
check "remaining" "$(lines cache-20200101T000000.bin db-20250102T000000.sql db-latest.sql notes.txt)" \
    "$(remaining)"
end

begin "names with spaces"
conf "1 my site"
mk "my site-20250101T000000.tar.gz" "my site-20250201T000000.tar.gz" "my site-20250301T000000.tar.gz"
run --config "$C" "$D"
check "stdout" "$(lines \
    'deleted: my site-20250101T000000.tar.gz' \
    'deleted: my site-20250201T000000.tar.gz' \
    'summary: kept 1, deleted 2')" "$OUT"
check "remaining" "my site-20250301T000000.tar.gz" "$(remaining)"
end

begin "a prefix that is a prefix of another prefix"
conf "1 db" "2 db-archive"
mk db-20250101T000000.sql db-20250102T000000.sql \
    db-archive-20240101T000000.tar db-archive-20240102T000000.tar db-archive-20240103T000000.tar
run --dry-run --config "$C" "$D"
check "stdout" "$(lines \
    'would delete: db-20250101T000000.sql' \
    'would delete: db-archive-20240101T000000.tar' \
    'summary: kept 3, would delete 2')" "$OUT"
end

begin "keep 0 deletes every backup of the prefix"
conf "0 tmp" "1 db"
mk tmp-20250101T000000.dump tmp-20250102T000000.dump db-20250101T000000.sql
run --config "$C" "$D"
check "stdout" "$(lines \
    'deleted: tmp-20250101T000000.dump' \
    'deleted: tmp-20250102T000000.dump' \
    'summary: kept 1, deleted 2')" "$OUT"
check "remaining" "db-20250101T000000.sql" "$(remaining)"
end

begin "usage errors exit 2"
conf "1 db"
mk db-20250101T000000.sql db-20250102T000000.sql
run
check "no arguments" 2 "$RC"
run --config "$C"
check "missing DIR" 2 "$RC"
run "$D"
check "missing --config" 2 "$RC"
run --config "$C" "$D" "$D"
check "two DIRs" 2 "$RC"
run --keep 3 --config "$C" "$D"
check "unknown option" 2 "$RC"
run "$D" --config
check "--config without value" 2 "$RC"
check "nothing on stdout" "" "$OUT"
check "nothing deleted" "$(lines db-20250101T000000.sql db-20250102T000000.sql)" "$(remaining)"
end

begin "config errors exit 3"
mk db-20250101T000000.sql db-20250102T000000.sql
run --config "$T/nope.conf" "$D"
check "missing config" 3 "$RC"
conf "x db"
run --config "$C" "$D"
check "non-numeric keep" 3 "$RC"
conf "1 db" "2 db"
run --config "$C" "$D"
check "duplicate prefix" 3 "$RC"
conf "1 db.sql"
run --config "$C" "$D"
check "dot in prefix" 3 "$RC"
check "nothing on stdout" "" "$OUT"
check "nothing deleted" "$(lines db-20250101T000000.sql db-20250102T000000.sql)" "$(remaining)"
end

begin "missing directory exits 4, but config errors come first"
conf "1 db"
run --config "$C" "$T/missing"
check "missing DIR" 4 "$RC"
conf "1"
run --config "$C" "$T/missing"
check "bad config and missing DIR" 3 "$RC"
end

# ------------------------------------------------------------------ summary

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
