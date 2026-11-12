# TokenTrial results: v0.2

Model `claude-haiku-5-5`, mode `subscription` (API-equivalent cost), 10 tasks × 5 arms × 8 repeats = 400 runs. 95% CIs from a 10,000-resample hierarchical bootstrap (tasks, then runs).

| Arm | Solved | Cost per solved task (95% CI) | vs baseline (95% CI) | Mean cost/run | Verdict |
|---|---|---|---|---|---|
| `baseline` | 80/80 | $0.0068 ($0.0045 to $0.0100) | — | $0.0068 | reference |
| `noop` | 80/80 | $0.0076 ($0.0047 to $0.0116) | +11% (-2% to +24%) | $0.0076 | noise floor |
| `noop-hook` | 79/80 | $0.0062 ($0.0035 to $0.0103) | -9% (-24% to +7%) | $0.0062 | control: SessionStart-hook side effect |
| `rtk` | 80/80 | $0.0093 ($0.0057 to $0.0138) | +36% (+17% to +53%) | $0.0093 | more expensive than baseline, beyond the noise floor |
| `caveman` | 77/80 | $0.0062 ($0.0036 to $0.0101) | -9% (-21% to +5%) | $0.0060 | inconclusive (CI includes no change or overlaps the noise floor) |

## Benchmarked model only (excluding Claude Code's background calls)

| Arm | Runs with background call | Cost per solved task (95% CI) | vs baseline (95% CI) |
|---|---|---|---|
| `baseline` | 80/80 | $0.0058 ($0.0034 to $0.0090) | — |
| `noop` | 80/80 | $0.0065 ($0.0036 to $0.0105) | +13% (-2% to +29%) |
| `noop-hook` | 0/80 | $0.0062 ($0.0035 to $0.0103) | +8% (-5% to +23%) |
| `rtk` | 80/80 | $0.0082 ($0.0046 to $0.0127) | +42% (+21% to +64%) |
| `caveman` | 0/80 | $0.0062 ($0.0036 to $0.0101) | +8% (-2% to +21%) |

## Tools vs the `noop-hook` control

Same SessionStart-hook side effect on both sides, so this isolates the tool itself.

| Arm | Cost per solved task vs `noop-hook` (95% CI) |
|---|---|
| `rtk` | +49% (+26% to +81%) |
| `caveman` | -0% (-10% to +11%) |

## Mean tokens per run, by type

Benchmarked model only.

| Arm | Fresh input | Cache write 5m | Cache write 1h | Cache read | Output | Turns |
|---|---|---|---|---|---|---|
| `baseline` | 11 | 0 | 10,452 | 92,869 | 5,522 | 7.7 |
| `noop` | 12 | 0 | 12,138 | 109,487 | 5,991 | 8.0 |
| `noop-hook` | 11 | 0 | 11,148 | 103,206 | 5,796 | 8.0 |
| `rtk` | 13 | 0 | 15,386 | 139,357 | 7,514 | 9.1 |
| `caveman` | 11 | 0 | 11,691 | 105,233 | 5,185 | 7.6 |

## Mean cost per run, by type (USD, API-equivalent)

Fresh input includes the background model's calls; the last column shows that part.

| Arm | Fresh input | Cache write | Cache read | Output | of which background model |
|---|---|---|---|---|---|
| `baseline` | 0.00098 | 0.00209 | 0.00093 | 0.00283 | 0.00105 |
| `noop` | 0.00098 | 0.00243 | 0.00109 | 0.00307 | 0.00105 |
| `noop-hook` | 0.00000 | 0.00223 | 0.00103 | 0.00290 | 0.00000 |
| `rtk` | 0.00098 | 0.00308 | 0.00139 | 0.00383 | 0.00105 |
| `caveman` | 0.00000 | 0.00234 | 0.00105 | 0.00259 | 0.00000 |

## Solved runs by task

| Task | `baseline` | `noop` | `noop-hook` | `rtk` | `caveman` |
|---|---|---|---|---|---|
| `git-config-forensics` | 8/8 | 8/8 | 8/8 | 8/8 | 7/8 |
| `git-regression-hunt` | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| `js-chunk-remainder` | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| `log-link-failure` | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| `py-cron-next` | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| `py-cron-tz` | 8/8 | 8/8 | 7/8 | 8/8 | 6/8 |
| `py-duration-spec` | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| `py-ledger-parens` | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| `py-pytest-cart-pricing` | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| `read-audit-writer` | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
