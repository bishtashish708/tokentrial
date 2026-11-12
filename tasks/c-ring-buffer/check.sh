#!/usr/bin/env bash
# Hidden check for c-ring-buffer: restore the tests, build them, run the visible test and
# the generated operation sequences.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
mkdir -p tests
cp "$TASK_DIR/hidden_tests/test_ringbuf.c" tests/test_ringbuf.c
cp "$TASK_DIR/hidden_tests/test_ringbuf_cases.c" tests/test_ringbuf_cases.c
cp "$TASK_DIR/hidden_tests/ringbuf_cases.txt" tests/ringbuf_cases.txt
out=.tt-check
rm -rf "$out" && mkdir -p "$out"
CFLAGS="-std=c11 -Wall -Wextra -O1 -I."
cc $CFLAGS -o "$out/test_ringbuf" tests/test_ringbuf.c ringbuf.c linereader.c >/dev/null 2>&1
cc $CFLAGS -o "$out/test_cases" tests/test_ringbuf_cases.c ringbuf.c >/dev/null 2>&1
"$out/test_ringbuf" >/dev/null 2>&1
"$out/test_cases" tests/ringbuf_cases.txt >/dev/null 2>&1
rm -rf "$out"
