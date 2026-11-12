#!/usr/bin/env bash
# Hidden check for js-chunk-remainder: restore the original tests, then run them.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
mkdir -p test
cp "$TASK_DIR/hidden_tests/text.test.js" test/text.test.js
node --test >/dev/null 2>&1
