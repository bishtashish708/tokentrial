#!/usr/bin/env bash
# Hidden check for py-cron-next: visible tests plus ~200 reference cases.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
rm -rf tests && mkdir -p tests
cp "$TASK_DIR"/hidden_tests/* tests/
python3 -m pytest -q -p no:cacheprovider tests >/dev/null 2>&1
