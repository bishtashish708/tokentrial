#!/usr/bin/env bash
# Hidden check for sh-backup-rotate: restore and run the visible test script, then replay
# the generated scenarios.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
mkdir -p tests
cp "$TASK_DIR/hidden_tests/run-tests.sh" tests/run-tests.sh
bash tests/run-tests.sh >/dev/null 2>&1
python3 "$TASK_DIR/hidden_tests/run_scenarios.py" "$TASK_DIR/hidden_tests/scenarios.json" \
    bin/rotate-backups.sh >/dev/null 2>&1
