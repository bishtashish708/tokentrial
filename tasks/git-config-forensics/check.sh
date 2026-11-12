#!/usr/bin/env bash
# Hidden check for git-config-forensics: "<sha> <tag>", sha may be abbreviated (>= 7).
set -euo pipefail
[ -f ANSWER.txt ] || exit 1
read -r sha tag rest < <(tr -d '`' < ANSWER.txt; echo) || true
expected=12e056cf6543475f035ccc98c1d5870ffdb34517
[ -n "${sha:-}" ] && [ ${#sha} -ge 7 ] && [ "${expected#"$sha"}" != "$expected" ] || exit 1
[ "${tag:-}" = "v1.4" ]
