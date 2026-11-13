# TokenTrial results: v0.3-sonnet

Model `claude-sonnet-5-5`, mode `subscription` (API-equivalent cost), 18 tasks × 7 arms × 3 repeats = 378 runs. 95% CIs from a 10,000-resample hierarchical bootstrap (tasks, then runs).

| Arm | Solved | Cost per solved task (95% CI) | vs baseline (95% CI) | Mean cost/run | Verdict |
|---|---|---|---|---|---|
| `baseline` | 53/54 | $0.0461 ($0.0362 to $0.0582) | — | $0.0453 | reference |
| `noop` | 54/54 | $0.0459 ($0.0356 to $0.0586) | -1% (-8% to +6%) | $0.0459 | noise floor |
| `noop-hook` | 53/54 | $0.0451 ($0.0359 to $0.0566) | -2% (-13% to +9%) | $0.0443 | control: SessionStart-hook side effect |
| `headroom-passthrough` | 54/54 | $0.0462 ($0.0363 to $0.0585) | +0% (-7% to +7%) | $0.0462 | control: headroom proxy, optimization off |
| `rtk-v1.2.0` | 53/54 | $0.0483 ($0.0380 to $0.0612) | +5% (-8% to +21%) | $0.0474 | inconclusive (CI includes no change or overlaps the noise floor) |
| `caveman-v4.1.0` | 52/54 | $0.0565 ($0.0445 to $0.0716) | +22% (+13% to +32%) | $0.0544 | more expensive than baseline, beyond the noise floor |
| `headroom` | 54/54 | $0.0454 ($0.0372 to $0.0549) | -1% (-10% to +8%) | $0.0454 | inconclusive (CI includes no change or overlaps the noise floor) |

## Benchmarked model only (excluding Claude Code's background calls)

| Arm | Runs with background call | Cost per solved task (95% CI) | vs baseline (95% CI) |
|---|---|---|---|
| `baseline` | 0/54 | $0.0461 ($0.0362 to $0.0582) | — |
| `noop` | 0/54 | $0.0459 ($0.0356 to $0.0586) | -1% (-8% to +6%) |
| `noop-hook` | 0/54 | $0.0451 ($0.0359 to $0.0566) | -2% (-13% to +9%) |
| `headroom-passthrough` | 0/54 | $0.0462 ($0.0363 to $0.0585) | +0% (-7% to +7%) |
| `rtk-v1.2.0` | 0/54 | $0.0483 ($0.0380 to $0.0612) | +5% (-8% to +21%) |
| `caveman-v4.1.0` | 0/54 | $0.0565 ($0.0445 to $0.0716) | +22% (+13% to +32%) |
| `headroom` | 0/54 | $0.0454 ($0.0372 to $0.0549) | -1% (-10% to +8%) |

## Tools vs the `noop-hook` control

Same SessionStart-hook side effect on both sides, so this isolates the tool itself.

| Arm | Cost per solved task vs `noop-hook` (95% CI) |
|---|---|
| `headroom-passthrough` | +2% (-8% to +15%) |
| `rtk-v1.2.0` | +7% (-7% to +32%) |
| `caveman-v4.1.0` | +25% (+12% to +44%) |
| `headroom` | +1% (-9% to +14%) |

## Tools vs their matched control

Each control reproduces the tool's known side effects on Claude Code (a SessionStart hook, or routing through a local proxy) without the tool itself.

| Arm | Matched control | Cost per solved task vs control (95% CI) |
|---|---|---|
| `rtk-v1.2.0` | `baseline` | +5% (-8% to +21%) |
| `caveman-v4.1.0` | `noop-hook` | +25% (+12% to +44%) |
| `headroom` | `headroom-passthrough` | -2% (-9% to +7%) |

## Mean tokens per run, by type

Benchmarked model only.

| Arm | Fresh input | Cache write 5m | Cache write 1h | Cache read | Output | Turns |
|---|---|---|---|---|---|---|
| `baseline` | 8 | 0 | 6,110 | 34,656 | 1,735 | 4.5 |
| `noop` | 9 | 0 | 6,097 | 38,376 | 1,761 | 4.7 |
| `noop-hook` | 8 | 0 | 5,935 | 35,824 | 1,697 | 4.7 |
| `headroom-passthrough` | 8 | 0 | 6,194 | 37,451 | 1,768 | 4.7 |
| `rtk-v1.2.0` | 9 | 0 | 6,388 | 40,124 | 1,780 | 4.9 |
| `caveman-v4.1.0` | 8 | 0 | 8,148 | 41,888 | 1,761 | 4.6 |
| `headroom` | 8 | 0 | 6,136 | 36,135 | 1,727 | 4.9 |

## Mean cost per run, by type (USD, API-equivalent)

Fresh input includes the background model's calls; the last column shows that part.

| Arm | Fresh input | Cache write | Cache read | Output | of which background model |
|---|---|---|---|---|---|
| `baseline` | 0.00002 | 0.02444 | 0.00347 | 0.01735 | 0.00000 |
| `noop` | 0.00002 | 0.02439 | 0.00384 | 0.01761 | 0.00000 |
| `noop-hook` | 0.00002 | 0.02374 | 0.00358 | 0.01697 | 0.00000 |
| `headroom-passthrough` | 0.00002 | 0.02477 | 0.00375 | 0.01767 | 0.00000 |
| `rtk-v1.2.0` | 0.00002 | 0.02555 | 0.00401 | 0.01780 | 0.00000 |
| `caveman-v4.1.0` | 0.00002 | 0.03259 | 0.00419 | 0.01761 | 0.00000 |
| `headroom` | 0.00002 | 0.02454 | 0.00361 | 0.01727 | 0.00000 |

## Solved runs by task

| Task | `baseline` | `noop` | `noop-hook` | `headroom-passthrough` | `rtk-v1.2.0` | `caveman-v4.1.0` | `headroom` |
|---|---|---|---|---|---|---|---|
| `c-ring-buffer` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `git-config-forensics` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `git-regression-hunt` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `js-chunk-remainder` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `js-csv-quoted-fields` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `js-lru-ttl-cache` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `log-link-failure` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `py-cli-json-output` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `py-cron-next` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `py-cron-tz` | 3/3 | 3/3 | 3/3 | 3/3 | 2/3 | 2/3 | 3/3 |
| `py-duration-spec` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `py-ledger-parens` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `py-perf-dedupe` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `py-pytest-cart-pricing` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `read-audit-writer` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `read-config-precedence` | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| `sh-backup-rotate` | 2/3 | 3/3 | 3/3 | 3/3 | 3/3 | 2/3 | 3/3 |
| `sql-monthly-revenue` | 3/3 | 3/3 | 2/3 | 3/3 | 3/3 | 3/3 | 3/3 |
