#!/usr/bin/env bash
# Hidden check for sql-monthly-revenue: restore the visible tests and fixture, add the
# hidden seeded dataset, and run everything against the agent's reports/monthly_revenue.sql.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
[ -f reports/monthly_revenue.sql ] || exit 1
rm -rf tests && mkdir -p tests
cp "$TASK_DIR"/hidden_tests/* tests/
python3 -m unittest discover -s tests >/dev/null 2>&1
