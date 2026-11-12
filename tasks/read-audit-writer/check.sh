#!/usr/bin/env bash
# Hidden check for read-audit-writer: exact dotted name, tolerating whitespace,
# backticks, and a module:function separator.
set -euo pipefail
[ -f ANSWER.txt ] || exit 1
got=$(tr -d '[:space:]`' < ANSWER.txt | tr ':' '.')
[ "$got" = "shopcore.audit.ledger.write_refund_entry_v2" ]
