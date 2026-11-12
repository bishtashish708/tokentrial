# TokenTrial results: pilot-v0.1

Model `claude-haiku-5-5`, mode `subscription` (API-equivalent cost), 5 tasks × 4 arms × 3 repeats = 60 runs. 95% CIs from a 10,000-resample hierarchical bootstrap (tasks, then runs).

| Arm | Solved | Cost per solved task (95% CI) | vs baseline (95% CI) | Mean cost/run | Verdict |
|---|---|---|---|---|---|
| `baseline` | 15/15 | $0.0054 ($0.0037 to $0.0073) | — | $0.0054 | reference |
| `noop` | 15/15 | $0.0049 ($0.0037 to $0.0061) | -10% (-30% to +6%) | $0.0049 | noise floor |
| `rtk` | 15/15 | $0.0046 ($0.0038 to $0.0054) | -15% (-38% to +10%) | $0.0046 | inconclusive (CI includes no change or overlaps the noise floor) |
| `caveman` | 15/15 | $0.0038 ($0.0029 to $0.0048) | -29% (-46% to -14%) | $0.0038 | inconclusive (CI includes no change or overlaps the noise floor) |

## Benchmarked model only (excluding Claude Code's background calls)

| Arm | Runs with background call | Cost per solved task (95% CI) | vs baseline (95% CI) |
|---|---|---|---|
| `baseline` | 15/15 | $0.0044 ($0.0027 to $0.0063) | — |
| `noop` | 15/15 | $0.0038 ($0.0027 to $0.0051) | -12% (-36% to +7%) |
| `rtk` | 15/15 | $0.0035 ($0.0028 to $0.0043) | -19% (-44% to +14%) |
| `caveman` | 0/15 | $0.0038 ($0.0029 to $0.0048) | -13% (-36% to +15%) |

## Mean tokens per run, by type

Benchmarked model only.

| Arm | Fresh input | Cache write 5m | Cache write 1h | Cache read | Output | Turns |
|---|---|---|---|---|---|---|
| `baseline` | 10 | 0 | 11,105 | 85,986 | 2,594 | 8.1 |
| `noop` | 10 | 0 | 8,989 | 76,832 | 2,536 | 8.5 |
| `rtk` | 9 | 0 | 7,818 | 71,033 | 2,538 | 7.4 |
| `caveman` | 10 | 0 | 9,092 | 83,142 | 2,356 | 7.5 |

## Mean cost per run, by type (USD, API-equivalent)

Fresh input includes the background model's calls; the last column shows that part.

| Arm | Fresh input | Cache write | Cache read | Output | of which background model |
|---|---|---|---|---|---|
| `baseline` | 0.00097 | 0.00222 | 0.00086 | 0.00136 | 0.00103 |
| `noop` | 0.00097 | 0.00180 | 0.00077 | 0.00134 | 0.00103 |
| `rtk` | 0.00097 | 0.00156 | 0.00071 | 0.00134 | 0.00103 |
| `caveman` | 0.00000 | 0.00182 | 0.00083 | 0.00118 | 0.00000 |

## Solved runs by task

| Task | `baseline` | `noop` | `rtk` | `caveman` |
|---|---|---|---|---|
| `js-chunk-remainder` | 3/3 | 3/3 | 3/3 | 3/3 |
| `log-link-failure` | 3/3 | 3/3 | 3/3 | 3/3 |
| `py-duration-spec` | 3/3 | 3/3 | 3/3 | 3/3 |
| `py-ledger-parens` | 3/3 | 3/3 | 3/3 | 3/3 |
| `read-audit-writer` | 3/3 | 3/3 | 3/3 | 3/3 |
