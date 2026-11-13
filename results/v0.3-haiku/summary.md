# TokenTrial results: v0.3-haiku

Model `claude-haiku-5-5`, mode `subscription` (API-equivalent cost), 18 tasks × 9 arms × 5 repeats = 810 runs. 95% CIs from a 10,000-resample hierarchical bootstrap (tasks, then runs).

| Arm | Solved | Cost per solved task (95% CI) | vs baseline (95% CI) | Mean cost/run | Verdict |
|---|---|---|---|---|---|
| `baseline` | 90/90 | $0.0097 ($0.0067 to $0.0133) | — | $0.0097 | reference |
| `noop` | 89/90 | $0.0099 ($0.0069 to $0.0137) | +3% (-9% to +16%) | $0.0098 | noise floor |
| `noop-hook` | 89/90 | $0.0094 ($0.0061 to $0.0136) | -3% (-17% to +12%) | $0.0093 | control: SessionStart-hook side effect |
| `headroom-passthrough` | 90/90 | $0.0109 ($0.0071 to $0.0158) | +13% (-4% to +29%) | $0.0109 | control: headroom proxy, optimization off |
| `rtk` | 90/90 | $0.0101 ($0.0072 to $0.0133) | +4% (-10% to +22%) | $0.0101 | inconclusive (CI includes no change or overlaps the noise floor) |
| `rtk-v1.2.0` | 90/90 | $0.0101 ($0.0072 to $0.0134) | +5% (-6% to +18%) | $0.0101 | inconclusive (CI includes no change or overlaps the noise floor) |
| `caveman` | 89/90 | $0.0085 ($0.0056 to $0.0121) | -12% (-22% to -2%) | $0.0084 | cheaper than baseline, beyond the noise floor |
| `caveman-v4.1.0` | 90/90 | $0.0086 ($0.0058 to $0.0122) | -11% (-20% to -0%) | $0.0086 | cheaper than baseline, beyond the noise floor |
| `headroom` | 89/90 | $0.0103 ($0.0066 to $0.0147) | +6% (-9% to +23%) | $0.0102 | inconclusive (CI includes no change or overlaps the noise floor) |

## Benchmarked model only (excluding Claude Code's background calls)

| Arm | Runs with background call | Cost per solved task (95% CI) | vs baseline (95% CI) |
|---|---|---|---|
| `baseline` | 54/90 | $0.0090 ($0.0061 to $0.0127) | — |
| `noop` | 52/90 | $0.0093 ($0.0063 to $0.0131) | +3% (-9% to +16%) |
| `noop-hook` | 0/90 | $0.0094 ($0.0061 to $0.0136) | +4% (-10% to +19%) |
| `headroom-passthrough` | 0/90 | $0.0109 ($0.0071 to $0.0158) | +21% (+4% to +37%) |
| `rtk` | 52/90 | $0.0094 ($0.0066 to $0.0126) | +4% (-10% to +23%) |
| `rtk-v1.2.0` | 46/90 | $0.0096 ($0.0067 to $0.0129) | +6% (-5% to +20%) |
| `caveman` | 0/90 | $0.0085 ($0.0056 to $0.0121) | -6% (-15% to +4%) |
| `caveman-v4.1.0` | 0/90 | $0.0086 ($0.0058 to $0.0122) | -4% (-14% to +7%) |
| `headroom` | 0/90 | $0.0103 ($0.0066 to $0.0147) | +14% (-1% to +32%) |

## Tools vs the `noop-hook` control

Same SessionStart-hook side effect on both sides, so this isolates the tool itself.

| Arm | Cost per solved task vs `noop-hook` (95% CI) |
|---|---|
| `headroom-passthrough` | +17% (+3% to +32%) |
| `rtk` | +7% (-13% to +35%) |
| `rtk-v1.2.0` | +8% (-9% to +30%) |
| `caveman` | -10% (-21% to +4%) |
| `caveman-v4.1.0` | -8% (-19% to +5%) |
| `headroom` | +10% (-8% to +32%) |

## Tools vs their matched control

Each control reproduces the tool's known side effects on Claude Code (a SessionStart hook, or routing through a local proxy) without the tool itself.

| Arm | Matched control | Cost per solved task vs control (95% CI) |
|---|---|---|
| `rtk` | `baseline` | +4% (-10% to +22%) |
| `rtk-v1.2.0` | `baseline` | +5% (-6% to +18%) |
| `caveman` | `noop-hook` | -10% (-21% to +4%) |
| `caveman-v4.1.0` | `noop-hook` | -8% (-19% to +5%) |
| `headroom` | `headroom-passthrough` | -6% (-19% to +8%) |

## Mean tokens per run, by type

Benchmarked model only.

| Arm | Fresh input | Cache write 5m | Cache write 1h | Cache read | Output | Turns |
|---|---|---|---|---|---|---|
| `baseline` | 14 | 0 | 16,372 | 151,441 | 8,518 | 8.8 |
| `noop` | 14 | 0 | 17,008 | 159,032 | 8,444 | 9.2 |
| `noop-hook` | 14 | 0 | 16,378 | 153,838 | 8,941 | 8.7 |
| `headroom-passthrough` | 16 | 0 | 18,921 | 199,311 | 10,333 | 10.0 |
| `rtk` | 14 | 0 | 17,796 | 148,752 | 8,782 | 8.6 |
| `rtk-v1.2.0` | 14 | 0 | 17,379 | 150,895 | 9,196 | 9.1 |
| `caveman` | 13 | 0 | 16,580 | 142,902 | 7,310 | 8.0 |
| `caveman-v4.1.0` | 13 | 0 | 17,190 | 148,807 | 7,443 | 8.4 |
| `headroom` | 15 | 0 | 17,933 | 165,571 | 9,868 | 10.7 |

## Mean cost per run, by type (USD, API-equivalent)

Fresh input includes the background model's calls; the last column shows that part.

| Arm | Fresh input | Cache write | Cache read | Output | of which background model |
|---|---|---|---|---|---|
| `baseline` | 0.00061 | 0.00327 | 0.00151 | 0.00430 | 0.00065 |
| `noop` | 0.00058 | 0.00340 | 0.00159 | 0.00427 | 0.00062 |
| `noop-hook` | 0.00000 | 0.00328 | 0.00154 | 0.00447 | 0.00000 |
| `headroom-passthrough` | 0.00000 | 0.00378 | 0.00199 | 0.00517 | 0.00000 |
| `rtk` | 0.00059 | 0.00356 | 0.00149 | 0.00443 | 0.00063 |
| `rtk-v1.2.0` | 0.00052 | 0.00348 | 0.00151 | 0.00464 | 0.00056 |
| `caveman` | 0.00000 | 0.00332 | 0.00143 | 0.00366 | 0.00000 |
| `caveman-v4.1.0` | 0.00000 | 0.00344 | 0.00149 | 0.00372 | 0.00000 |
| `headroom` | 0.00000 | 0.00359 | 0.00166 | 0.00493 | 0.00000 |

## Solved runs by task

| Task | `baseline` | `noop` | `noop-hook` | `headroom-passthrough` | `rtk` | `rtk-v1.2.0` | `caveman` | `caveman-v4.1.0` | `headroom` |
|---|---|---|---|---|---|---|---|---|---|
| `c-ring-buffer` | 5/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `git-config-forensics` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `git-regression-hunt` | 5/5 | 5/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `js-chunk-remainder` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `js-csv-quoted-fields` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `js-lru-ttl-cache` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `log-link-failure` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `py-cli-json-output` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `py-cron-next` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `py-cron-tz` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 4/5 | 5/5 | 4/5 |
| `py-duration-spec` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `py-ledger-parens` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `py-perf-dedupe` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `py-pytest-cart-pricing` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `read-audit-writer` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `read-config-precedence` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `sh-backup-rotate` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `sql-monthly-revenue` | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
