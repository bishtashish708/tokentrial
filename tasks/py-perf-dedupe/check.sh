#!/usr/bin/env bash
# Hidden check for py-perf-dedupe: restore the tests, then run visible tests, seeded
# reference cases and the 200k-record timed batch (child processes are killed on timeout).
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
rm -rf tests && mkdir -p tests
cp "$TASK_DIR"/hidden_tests/* tests/
python3 -m unittest discover -f -s tests >/dev/null 2>&1
