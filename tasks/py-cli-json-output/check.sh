#!/usr/bin/env bash
# Hidden check for py-cli-json-output: restore the tests and fixtures, then run the visible
# tests plus generated text/JSON cases and error-handling cases.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
rm -rf tests && mkdir -p tests/data
cp "$TASK_DIR"/hidden_tests/*.py "$TASK_DIR"/hidden_tests/cases.json tests/
cp "$TASK_DIR"/hidden_tests/*.lock tests/data/
python3 -m unittest discover -s tests >/dev/null 2>&1
