#!/usr/bin/env bash
# Hidden check for js-csv-quoted-fields: visible tests plus ~400 generated cases
# (scripts/make_csv_task.py), restored from the task directory.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
rm -rf test && mkdir -p test
cp "$TASK_DIR"/hidden_tests/* test/
node --test test/csv.test.js test/report.test.js test/hidden_cases.test.js >/dev/null 2>&1
