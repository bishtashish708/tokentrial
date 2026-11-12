#!/usr/bin/env bash
# Hidden check for log-link-failure: exact path:line, tolerating whitespace and backticks.
set -euo pipefail
[ -f ANSWER.txt ] || exit 1
got=$(tr -d '[:space:]`' < ANSWER.txt)
[ "$got" = "src/net/packet.c:212" ]
