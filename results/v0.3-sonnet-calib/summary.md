# TokenTrial results: v0.3-sonnet-calib

Model `claude-sonnet-5-5`, mode `subscription` (API-equivalent cost), 2 tasks × 5 arms × 1 repeats = 10 runs. 95% CIs from a 10,000-resample hierarchical bootstrap (tasks, then runs).

| Arm | Solved | Cost per solved task (95% CI) | vs baseline (95% CI) | Mean cost/run | Verdict |
|---|---|---|---|---|---|
| `baseline` | 2/2 | $0.0614 ($0.0526 to $0.0703) | — | $0.0614 | reference |
| `noop-hook` | 2/2 | $0.0584 ($0.0562 to $0.0607) | -5% (-20% to +15%) | $0.0584 | control: SessionStart-hook side effect |
| `rtk-v1.2.0` | 2/2 | $0.0722 ($0.0623 to $0.0820) | +17% (-11% to +56%) | $0.0722 | reference |
| `caveman-v4.1.0` | 2/2 | $0.0654 ($0.0639 to $0.0669) | +6% (-9% to +27%) | $0.0654 | reference |
| `headroom` | 2/2 | $0.0744 ($0.0415 to $0.1072) | +21% (-21% to +52%) | $0.0744 | reference |

## Benchmarked model only (excluding Claude Code's background calls)

| Arm | Runs with background call | Cost per solved task (95% CI) | vs baseline (95% CI) |
|---|---|---|---|
| `baseline` | 2/2 | $0.0604 ($0.0515 to $0.0692) | — |
| `noop-hook` | 0/2 | $0.0584 ($0.0562 to $0.0607) | -3% (-19% to +18%) |
| `rtk-v1.2.0` | 2/2 | $0.0711 ($0.0612 to $0.0810) | +18% (-12% to +57%) |
| `caveman-v4.1.0` | 0/2 | $0.0654 ($0.0639 to $0.0669) | +8% (-8% to +30%) |
| `headroom` | 0/2 | $0.0744 ($0.0415 to $0.1072) | +23% (-19% to +55%) |

## Tools vs the `noop-hook` control

Same SessionStart-hook side effect on both sides, so this isolates the tool itself.

| Arm | Cost per solved task vs `noop-hook` (95% CI) |
|---|---|
| `rtk-v1.2.0` | +24% (+11% to +35%) |
| `caveman-v4.1.0` | +12% (+10% to +14%) |
| `headroom` | +27% (-32% to +91%) |

## Tools vs their matched control

Each control reproduces the tool's known side effects on Claude Code (a SessionStart hook, or routing through a local proxy) without the tool itself.

| Arm | Matched control | Cost per solved task vs control (95% CI) |
|---|---|---|
| `rtk-v1.2.0` | `baseline` | +17% (-11% to +56%) |
| `caveman-v4.1.0` | `noop-hook` | +12% (+10% to +14%) |

## Mean tokens per run, by type

Benchmarked model only.

| Arm | Fresh input | Cache write 5m | Cache write 1h | Cache read | Output | Turns |
|---|---|---|---|---|---|---|
| `baseline` | 9 | 0 | 7,241 | 68,605 | 2,451 | 6.0 |
| `noop-hook` | 7 | 0 | 7,602 | 50,350 | 2,298 | 7.5 |
| `rtk-v1.2.0` | 12 | 0 | 8,577 | 99,052 | 2,686 | 10.0 |
| `caveman-v4.1.0` | 9 | 0 | 8,554 | 73,380 | 2,381 | 8.0 |
| `headroom` | 8 | 0 | 11,820 | 51,346 | 2,193 | 7.0 |

## Mean cost per run, by type (USD, API-equivalent)

Fresh input includes the background model's calls; the last column shows that part.

| Arm | Fresh input | Cache write | Cache read | Output | of which background model |
|---|---|---|---|---|---|
| `baseline` | 0.00102 | 0.02896 | 0.00686 | 0.02459 | 0.00108 |
| `noop-hook` | 0.00001 | 0.03041 | 0.00504 | 0.02298 | 0.00000 |
| `rtk-v1.2.0` | 0.00103 | 0.03431 | 0.00991 | 0.02694 | 0.00108 |
| `caveman-v4.1.0` | 0.00002 | 0.03422 | 0.00734 | 0.02381 | 0.00000 |
| `headroom` | 0.00002 | 0.04728 | 0.00513 | 0.02193 | 0.00000 |

## Solved runs by task

| Task | `baseline` | `noop-hook` | `rtk-v1.2.0` | `caveman-v4.1.0` | `headroom` |
|---|---|---|---|---|---|
| `js-csv-quoted-fields` | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| `py-pytest-cart-pricing` | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
