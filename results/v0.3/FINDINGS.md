# v0.3: findings

Run on 2026-11-12 and 13. Claude Code headless on a Claude Code subscription; costs are
API-equivalent at verified list prices (`src/tokentrial/data/pricing.toml`). 18 tasks.

| Phase | Model | Design | Runs solved | API-equivalent cost | Claude Code |
|---|---|---|---|---|---|
| A | `claude-haiku-5-5` | 18 tasks × 9 arms × 5 repeats = 810 | 805 | $7.85 | 2.1.252 (447 runs), then 2.1.322 (363 runs) |
| B | `claude-sonnet-5-5` | 18 tasks × 7 arms × 3 repeats = 378 | 373 | $17.76 | 2.1.322 |

- Generated tables: [`../v0.3-haiku/summary.md`](../v0.3-haiku/summary.md) and
  [`../v0.3-sonnet/summary.md`](../v0.3-sonnet/summary.md), plus `summary.json` next to each.
- Raw data: [`../v0.3-haiku/raw/`](../v0.3-haiku/raw/) and [`../v0.3-sonnet/raw/`](../v0.3-sonnet/raw/),
  with the home path and username scrubbed.
- Tool versions: rtk v1.1.0 and v1.2.0, caveman v4.0.1 and v4.1.0, headroom 0.42.0. Commits and
  checksums are in `src/tokentrial/tools.py`.
- One 60% pause of the five-hour usage window (phase B, 02:35–02:45 UTC). No budget stop, no
  long-context call.

## Headline

Each tool is compared with its **matched control**: the arm that reproduces the tool's known side
effects on Claude Code without the tool (see [Controls](#controls)).

| Arm | Haiku 5.5: solved | Haiku: vs matched control (95% CI) | Sonnet 5.5: solved | Sonnet: vs matched control (95% CI) |
|---|---|---|---|---|
| `noop` (noise floor, vs `baseline`) | 89/90 | +3% (−9% to +16%) | 54/54 | −1% (−8% to +6%) |
| `rtk` v1.1.0 (vs `baseline`) | 90/90 | +4% (−10% to +22%) | — | — |
| `rtk` v1.2.0 (vs `baseline`) | 90/90 | +5% (−6% to +18%) | 53/54 | +5% (−8% to +21%) |
| `caveman` v4.0.1 (vs `noop-hook`) | 89/90 | −10% (−21% to +4%) | — | — |
| `caveman` v4.1.0 (vs `noop-hook`) | 90/90 | −8% (−19% to +5%) | 52/54 | **+25% (+12% to +44%)** |
| `headroom` 0.42.0 (vs `headroom-passthrough`) | 89/90 | −6% (−19% to +8%) | 54/54 | −2% (−9% to +7%) |

1. **No tool saved money beyond the noise floor** on either model.
2. **caveman v4.1.0 made Sonnet runs 25% more expensive.** Its SessionStart hook adds about 1,850
   tokens of instructions to every session, and Sonnet's output, already short, didn't get any
   shorter. On Haiku, where output fell about 17%, the two roughly cancel.
3. **rtk's v0.2 penalty replicated on the tasks where rtk does the most work.** Across all 18
   tasks it averages +4–5% (inconclusive), because most of the new tasks give rtk little to do. On
   the four Bash-heavy tasks identified in v0.2, it was +38% for v1.1.0 on Haiku (CI +9% to +81%)
   and +36% for v1.2.0 on Sonnet (CI +5% to +114%).
4. **headroom had no measurable effect.** It compressed requests in every run but removed only
   about 2% of input tokens.
5. **Claude Code updated itself mid-run** and the new version dropped the background call behind
   caveman's apparent pilot saving. See [The Claude Code update](#the-claude-code-update).

## caveman: a fixed cost that only pays off when output shrinks

caveman's SessionStart hook injects its instructions (about 5,000 characters) into every session.
That shows up as extra cache-write tokens in the first API call:

| | First-call cache write, median: control → caveman v4.1.0 | Output tokens per run: control → caveman v4.1.0 | Cost vs control |
|---|---|---|---|
| Haiku 5.5 | 792 → 2,638 | 8,941 → 7,443 (−17%) | −8% (−19% to +5%) |
| Sonnet 5.5 | 1,096 → 2,952 | 1,697 → 1,761 (+4%) | +25% (+12% to +44%) |

- **Sonnet doesn't have much prose to cut.** Its runs averaged about 1,750 output tokens, mostly
  tool calls and code, in 4–5 turns. caveman makes prose terse; it doesn't shorten code.
- **The added context is paid for on every run.** Sonnet's 1-hour cache writes cost $4 per million
  tokens, so about 1,850 extra tokens is roughly $0.007 a run against a $0.045 baseline. Each later
  turn also re-reads it from cache.
- **On Haiku the saving and the cost roughly cancel.** Haiku writes about 5× more output, and
  caveman cut it by about 17%. caveman v4.0.1 and v4.1.0 behaved alike (−10% and −8%).
- **Against plain baseline, caveman on Haiku looks cheaper:** −12% (−22% to −2%) for v4.0.1 and
  −11% (−20% to −0%) for v4.1.0, and `summary.md`'s automatic verdict labels both "cheaper than
  baseline". Part of that is the skipped title call on the 2.1.252 runs, which the `noop-hook`
  control also gets. Against that control the difference is within the noise.
- This fits Shobhan Roy's arithmetic
  ([Level Up, August 2026](https://levelup.gitconnected.com/89-of-my-coding-agent-bill-was-cache-traffic-and-most-token-saving-tools-cannot-reach-it-a5c6eb314c9e)):
  output is a minority of the bill, so a terseness tool's ceiling is low, and here its own context
  sets a floor.

## rtk: same mechanism, diluted by the task mix

| Subset | rtk v1.1.0, Haiku | rtk v1.2.0, Haiku | rtk v1.2.0, Sonnet |
|---|---|---|---|
| All 18 tasks | +4% (−10% to +22%) | +5% (−6% to +18%) | +5% (−8% to +21%) |
| The 4 Bash-heavy tasks from v0.2¹ | **+38% (+9% to +81%)** | +22% (−1% to +60%) | **+36% (+5% to +114%)** |
| The 8 new v0.3 tasks | −8% (−21% to +8%) | +1% (−11% to +18%) | — |

¹ `py-cron-tz`, `py-cron-next`, `py-pytest-cart-pricing`, `git-regression-hunt`. These were
identified from v0.2's data, before the v0.3 runs, but the subset wasn't written into the v0.3 plan
as an endpoint. Treat it as a replication check, not a pre-registered test.

- **Haiku still bypasses rtk.** It ran `rtk bypass` 59 times in 90 runs with v1.1.0 (88 in 80 in
  v0.2) and 53 times with v1.2.0. v1.2.0 roughly halved bypasses on `py-cron-tz` (4.4 → 2.2 per run),
  and its cost there was close to baseline.
- **Sonnet almost never bypasses** (once in 54 runs), but it still took more turns on these tasks
  (for example 3.7 → 5.7 on `py-cron-tz`), and every extra turn re-reads the cached context. That's
  the mechanism JetBrains reported for rtk v0.43.0 on Sonnet 5
  ([July 2026](https://blog.jetbrains.com/ai/2026/07/rtk-claude-code-token-savings/)).
- **Why the 18-task average is small.** Most of the new tasks are short C, Node, SQL and bash fixes
  where rtk has few commands to rewrite. The average depends on the task mix, and that's a reason to
  report where a tool acts, not just the mean.

## headroom: it compresses, but very little

- **It was active.** The headroom proxy compressed requests in every headroom run (about 7.5 of 9
  requests per Haiku run, 4.2 of 5.2 per Sonnet run), and its MCP server connected each time.
- **It removed very little.** Across runs it took out about 2.2% of input tokens (Haiku) and 2.3%
  (Sonnet), by its own `/stats` accounting.
- **Against the pass-through proxy it's −6% on Haiku and −2% on Sonnet, both within the noise.**
- **Installing headroom has a cost of its own on Haiku.** The pass-through control (proxy, MCP
  server and `ENABLE_TOOL_SEARCH=true`, with compression off) came out +17% against `noop-hook`
  (CI +3% to +32%), with more turns (10.0 vs 8.7). On Sonnet it was +2% (CI −8% to +15%). This
  setup cost is why headroom is compared with the pass-through control rather than with baseline.

## The Claude Code update

The runner used the `claude` on `PATH`. Claude Code auto-updated from 2.1.252 to 2.1.322 at about
20:38 UTC on 2026-11-12, after 447 of the 810 Haiku runs. All 378 Sonnet runs used 2.1.322.

- **The arms were affected roughly equally.** Each Haiku arm had 36–45 of its 90 runs on 2.1.322.
- **2.1.322 doesn't make the background title call.** On 2.1.252, Claude Code made a small
  `claude-haiku-4-5` call to title the session unless a SessionStart hook was configured (see
  [v0.2](../v0.2/FINDINGS.md#why-cavemans-pilot-saving-disappeared)). On 2.1.322 no arm made it:
  0 of 363 Haiku runs and 0 of 378 Sonnet runs. So the `noop-hook` control only differs from
  baseline on 2.1.252.
- **Splitting by version doesn't change the conclusions.** Each version's intervals are wide, since
  each holds about half the data, but the directions agree:

| Haiku, vs matched control | Claude Code 2.1.252 (447 runs) | Claude Code 2.1.322 (363 runs) |
|---|---|---|
| `noop` vs `baseline` | −7% (−21% to +11%) | +23% (−2% to +59%) |
| `rtk` v1.1.0 | +7% (−15% to +32%) | +0% (−24% to +32%) |
| `rtk` v1.2.0 | +5% (−15% to +29%) | +11% (−8% to +35%) |
| `caveman` v4.0.1 | −4% (−24% to +18%) | −17% (−35% to +11%) |
| `caveman` v4.1.0 | −13% (−27% to +3%) | −5% (−26% to +28%) |
| `headroom` | +6% (−16% to +37%) | −5% (−35% to +45%) |

The next version of the runner will set `DISABLE_AUTOUPDATER=1` for the agent and stop if the
Claude Code version changes during an experiment.

## Controls

| Control | Reproduces | Used for |
|---|---|---|
| `noop` | Same install steps as a tool, changes nothing | The noise floor |
| `noop-hook` | A do-nothing SessionStart hook (on 2.1.252 this skips the title call) | caveman |
| `headroom-passthrough` | headroom's proxy, MCP server and tool search, with compression off | headroom |
| `baseline` | Unmodified Claude Code | rtk (its PreToolUse hook has no known side effect) |

A probe also confirmed that setting `ANTHROPIC_BASE_URL` to Anthropic's own URL doesn't skip the
title call, so headroom's effect on it comes from routing through a local proxy.

## Solve rates

1,178 of 1,188 runs solved. The 10 failures are spread across arms, with at most 2 for any arm:

- **Haiku:** `py-cron-tz` (headroom, caveman v4.0.1), `git-regression-hunt` (noop-hook) and
  `c-ring-buffer` (noop).
- **Sonnet:** `py-cron-tz` (rtk v1.2.0, caveman v4.1.0), `sh-backup-rotate` (baseline, caveman
  v4.1.0) and `sql-monthly-revenue` (noop-hook).

That's too few failures to compare arms on correctness, so the comparison still rests on cost.

## Haiku 5.5 vs Sonnet 5.5

- **Sonnet costs about 4.7× as much per solved task** ($0.046 vs $0.0097 at baseline). It takes
  half as many turns (4.5 vs 8.8) and writes about a fifth of the output (1,735 vs 8,518 tokens),
  but its per-token prices are higher.
- **Sonnet's noise floor is tighter:** −1% (−8% to +6%) against +3% (−9% to +16%) for Haiku.
- **Cache writes are a larger share of Sonnet's bill** (about 54% vs 34% for Haiku). That's why a
  fixed block of extra context, like caveman's instructions, shows up more on Sonnet.

## Method notes

- **Design.** Tasks, arms and repeats ran in a seeded random order (seed 3), with both phases on
  the same machine and never concurrently. The run matrix, usage estimates and pause rules are in
  [docs/PLAN.md](../../docs/PLAN.md).
- **New tasks.** 8 tasks were added for variety: C, Node (2), SQLite, bash, a performance task, a
  multi-file CLI feature and an exact-answer configuration question. Each fails on its starting
  repo, passes with the reference solution and fails with the visible tests blanked. Hidden cases
  are cross-checked against an independent implementation.
- **Statistics.** Same as v0.2: cost per solved task, compared paired by task with a task-then-run
  hierarchical bootstrap (10,000 resamples). The version split and task subsets above use the same
  bootstrap on the filtered records (`summarize()` in `src/tokentrial/report.py`).
- **Activation.** rtk's hook fired and rewrote commands, caveman's mode was on in every caveman
  run, and headroom's proxy compressed requests in every headroom run.

## Limitations

- **Synthetic, small-to-medium tasks.** Long sessions with large repos may give compression tools
  more to work with.
- **The Claude Code version changed during phase A** (see above). Phase B used one version only.
- **Default configurations.** Each tool ran as its documentation describes. rtk and caveman's
  maintainers were invited to critique the setup
  ([rtk#5087](https://github.com/rtk-ai/rtk/issues/5087),
  [caveman#1519](https://github.com/JuliusBrussee/caveman/issues/1519)).
- **Fewer Sonnet repeats** (3 vs 5) and fewer Sonnet arms (no v1.1.0/v4.0.1 comparison).
- **API-equivalent cost.** Computed from list prices and Claude Code's reported usage, not from an
  invoice.
