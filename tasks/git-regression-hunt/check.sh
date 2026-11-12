#!/usr/bin/env bash
# Hidden check for git-regression-hunt: the culprit commit's SHA, and a working fix.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
[ -f ANSWER.txt ] || exit 1
got=$(tr -d '[:space:]`' < ANSWER.txt)
expected=07cb159a8512f48f2000e7c5ec77a2b4ee8c9eba
[ ${#got} -ge 7 ] && [ "${expected#"$got"}" != "$expected" ] || exit 1
mkdir -p tests && cp "$TASK_DIR/hidden_tests/test_bucket.py" tests/test_bucket.py
python3 -m pytest -q -p no:cacheprovider tests >/dev/null 2>&1
