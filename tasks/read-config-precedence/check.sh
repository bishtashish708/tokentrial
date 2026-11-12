#!/usr/bin/env bash
# Hidden check for read-config-precedence: exact integer, tolerating whitespace and
# backticks.
set -euo pipefail
[ -f ANSWER.txt ] || exit 1
got=$(tr -d '[:space:]`' < ANSWER.txt)
[ "$got" = "6946816" ]
