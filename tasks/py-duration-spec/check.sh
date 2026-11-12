#!/usr/bin/env bash
# Hidden check for py-duration-spec: the full specification tests.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
mkdir -p tests
cp "$TASK_DIR/hidden_tests/test_durations.py" tests/test_durations.py
python3 -m unittest discover -s tests >/dev/null 2>&1
