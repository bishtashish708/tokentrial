#!/usr/bin/env bash
# Hidden check for js-lru-ttl-cache: visible tests plus 300 generated operation sequences
# (scripts/make_lru_ttl_task.py), restored from the task directory.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
rm -rf test && mkdir -p test
cp "$TASK_DIR"/hidden_tests/* test/
node --test test/lru.test.js test/ttl.test.js test/memoize.test.js test/sequences.test.js >/dev/null 2>&1
