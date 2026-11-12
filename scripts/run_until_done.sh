#!/usr/bin/env bash
# Resume an experiment across usage-limit pauses until it finishes.
#
# Usage: scripts/run_until_done.sh <out-dir> [extra args for `tokentrial run --resume`]
#
# `tokentrial run` exits 3 when it pauses (usage limit or --pause-at-utilization) and
# prints "Continue after YYYY-MM-DD HH:MM". This waits until then (plus a margin) and
# resumes. Any other non-zero exit (budget 4, fatal 5, not ready 2) stops the loop.
set -uo pipefail
out=${1:?usage: run_until_done.sh <out-dir> [args]}
shift
margin_s=${MARGIN_S:-300}
fallback_s=${FALLBACK_S:-1800}

while true; do
  log=$(mktemp)
  uv run tokentrial run --resume --out "$out" "$@" 2>&1 | tee "$log"
  rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 3 ]; then
    rm -f "$log"
    echo "run_until_done: tokentrial exited $rc; stopping"
    exit "$rc"
  fi
  when=$(sed -n 's/.*Continue after \([0-9-]* [0-9:]*\).*/\1/p' "$log" | tail -1)
  rm -f "$log"
  wait_s=$fallback_s
  if [ -n "$when" ]; then
    target=$(python3 -c "import sys,datetime; print(int(datetime.datetime.strptime(sys.argv[1], '%Y-%m-%d %H:%M').timestamp()))" "$when")
    wait_s=$(( target - $(date +%s) + margin_s ))
    [ "$wait_s" -lt 60 ] && wait_s=60
  fi
  echo "run_until_done: paused; resuming in ${wait_s}s (reset ${when:-unknown}) at $(date -r $(( $(date +%s) + wait_s )) '+%Y-%m-%d %H:%M' 2>/dev/null || date -d "@$(( $(date +%s) + wait_s ))" '+%Y-%m-%d %H:%M')"
  sleep "$wait_s"
done
