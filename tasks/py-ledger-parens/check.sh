#!/usr/bin/env bash
# Hidden check for py-ledger-parens. Runs in the agent's workspace.
# Restores the original tests (in case the agent edited them), then runs them.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
mkdir -p tests
cp "$TASK_DIR/hidden_tests/test_ledger.py" tests/test_ledger.py
python3 -m unittest discover -s tests >/dev/null 2>&1
