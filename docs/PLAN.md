# TokenTrial plan

TokenTrial ships in tiers. **v0.1 is a low-budget pilot.** It proves the method end to end on
a small set of tasks for about $10–30 or less, or for $0 extra on a Claude Code subscription.
The full 20-task, 500-run benchmark comes later, once the pilot shows the approach is useful.

## Tiers and cost estimates

| Tier | Tasks | Arms | Repeats | Runs | Model | Estimated cost |
|---|---|---|---|---|---|---|
| **v0.1 pilot** | 5 | 4 | 3 | **60** | `claude-haiku-5-5` | **about $1–25 API, hard cap $30.** $0 extra on a subscription |
| v0.1 optional spot-check | 2 | 4 | 2 | 16 | `claude-sonnet-5-5` | about $5–15. Only if budget is left after the pilot |
| v0.2 scale-up | 20 | 5 (+ headroom) | 5 | 500 | `claude-sonnet-5-5` | about $100–300 |
| v0.3+ | 20+ | 5+ | 5 | 1,000+ | several models and agents | depends on scope. Fund with credits (see below) |

**How the pilot estimate was worked out.** Haiku 5.5 costs $0.10 per 1M input tokens and $0.50
per 1M output tokens, with cache reads at about a tenth of the input price. Those prices apply to
prompts up to 100K tokens; longer prompts cost $0.50 and $2.50.

- **Typical run:** about 300K input-side tokens (mostly cache reads) and 15K output tokens. That
  comes to about **$0.02**.
- **Heavy run:** about 1.5M input-side tokens and 50K output tokens, all at the long-prompt
  price. That comes to about **$0.40**.
- 60 runs therefore cost between about $1 and $25.

The cap of $30 also covers debugging reruns. The real cost per run is measured in the shakedown
on day 6 and replaces this guess.

## v0.1 pilot scope

| Item | Decision |
|---|---|
| Agent | Claude Code CLI, pinned version, headless mode |
| Model | `claude-haiku-5-5` (CLI default) |
| Modes | `api` (API key, billed) and `subscription` (logged-in Claude Code, API-equivalent cost) |
| Price tables | Anthropic (main). Bedrock prices filled in so the cost can also be shown at Bedrock rates |
| Arms | `baseline`, `noop` (control), `rtk`, `caveman` |
| Tasks | 5, each with a hidden check script |
| Repeats | 3 per (task, arm), so 5 × 4 × 3 = **60 runs** |
| Budget caps | `--max-usd` (total, default $30) and `--max-usd-per-run` (default $1) |
| Output | `runs/*.jsonl`, `results/summary.json`, static site on GitHub Pages |

Out of scope for v0.1: headroom, context-mode and CLAUDE.md arms; other agents; effort sweeps.

## Budget caps

`tokentrial run` keeps a running cost, priced from `pricing.toml`, after every API call.

- **`--max-usd-per-run`:** if a single agent run goes over this, it is stopped and recorded as
  `aborted_budget`, which counts as unsolved. The experiment moves on to the next run.
- **`--max-usd`:** if the total for the experiment goes over this, the experiment stops. Runs
  already recorded are kept, so `report` can still work on partial results.
- In subscription mode the caps apply to the API-equivalent cost. Nothing is billed, but the caps
  still limit how much of the usage allowance an experiment can use.
- To run without a meaningful cap, pass a large value on purpose. The defaults are set so a
  mistake can't cost more than $30.

## Subscription mode (no API key)

`--mode subscription` runs Claude Code under the user's logged-in subscription instead of an API
key.

- **Cost:** Claude Code prints token usage in headless JSON output. TokenTrial splits that usage
  by token type and prices it from its own `pricing.toml` to get an **API-equivalent cost**. It
  does not rely on any cost figure Claude Code itself reports. The exact JSON fields will be
  confirmed on day 2.
- **Slower:** subscription usage limits mean the 60 runs will likely be spread over several
  sessions or days. The runner pauses when it hits a limit and resumes, and it skips runs
  that are already recorded.
- **Less precise:** if Claude Code only reports totals for a session rather than for each call,
  the long-prompt pricing of Haiku can only be estimated. The leaderboard labels these results
  "API-equivalent (subscription)" and keeps them apart from API-billed results.

## Task set (pilot: 5)

Each task lives in `tasks/<id>/`. It has `task.toml` (prompt and limits), `repo/` (starting
files), `check.sh` (hidden from the agent, exit 0 = solved) and `solution/`. The five pilot tasks
cover the workloads that matter most to the two tools under test:

| # | Task type | Why |
|---|---|---|
| 1 | Fix a failing Python test with verbose pytest output | RTK's main target |
| 2 | Fix a failing JS test with noisy npm/jest output | RTK, in a second ecosystem |
| 3 | Small feature against spec tests | Balanced work, where caveman's terse output should show |
| 4 | Read a mid-size codebase and give an exact answer | Context-heavy, little output |
| 5 | Triage a build log and give an exact answer | Large tool output |

Each check must fail on `repo/` and pass on `solution/`. CI checks both. In v0.2 this grows to 20
tasks across 6 groups, adding JS/TS fixes, refactors and more read-heavy tasks.

## Cost model

For every API call, usage is split into `input`, `cache_write_5m`, `cache_write_1h`, `cache_read`
and `output`, then priced from `src/tokentrial/data/pricing.toml`.

- Every price row has `source` and `verified`. `report` refuses to publish while any price it
  used is unverified.
- **Haiku 5.5 long-prompt pricing:** when a call's prompt is over 100K tokens, it is priced at the
  higher rate. This is added to `pricing.toml` on day 3.

**Headline metric:** cost per solved task = Σ cost over all runs ÷ solved runs, for each arm.
Also reported: solve rate, cost per run, turns, wall time, and cost split by token type.

## Statistics

- Hierarchical bootstrap with 10,000 resamples: resample tasks, then runs within each task. Report
  the 95% CI for each arm and the paired difference from `baseline`.
- **Noise floor:** the CI of `noop − baseline`. A tool's effect counts only if its CI excludes 0
  and its point estimate is outside the noop interval.
- **Honest framing:** with 5 tasks × 3 repeats, the intervals will be wide. The pilot shows the
  method and gives a first, clearly labelled signal. It is not a final verdict. Any tool whose
  effect is "inconclusive" is reported that way.
- Arms are interleaved in a random order with a fixed seed. Each run starts from a cold workspace.

## Schedule (2 weeks)

### Week 1: harness

| Day | Deliverable |
|---|---|
| 1 | Task format, loader, `check.sh` contract. Tasks 1–2 |
| 2 | Runner: isolated workspace per run, Claude Code headless, usage capture per call. Both `api` and `subscription` modes |
| 3 | Pricing: Anthropic rows verified, Haiku long-prompt tier, Bedrock rows filled in. Budget caps wired into the runner |
| 4 | Arm adapters: `noop`, `rtk`, `caveman` at pinned versions |
| 5 | Tasks 3–5. CI validates every check |

### Week 2: pilot and leaderboard

| Day | Deliverable |
|---|---|
| 6 | Shakedown: 1 task × 4 arms × 1 repeat, capped at $2. Measure real cost per run and fix bugs |
| 7 | Bootstrap module and `report` producing `summary.json` |
| 8 | Full pilot of 60 runs, capped at $30. Spread over several days if using a subscription |
| 9 | Static leaderboard: table, CI plot, cost-by-token-type bars. Deploy to GitHub Pages |
| 10 | Write-up, invite tool authors to review their arm configs, tag v0.1 |

## Scaling up (v0.2+)

The full benchmark (20 tasks, 5 arms including headroom, 5 repeats, 500 runs, on Sonnet 5.5) starts
once the pilot gets traction: stars, issues, or tool authors engaging. Ways to fund it:

- **Cloud and API credit programs.** AWS credits (e.g. AWS Activate or the research/open-source
  credit programs) could fund Bedrock runs. Anthropic's research or startup credit programs could
  fund API runs.
- **Subscription mode at scale.** It costs nothing extra but is slow. It works for adding tasks bit
  by bit.
- **Sponsors.** Tool authors may fund their own runs. Arm configs and raw data stay public, so
  this doesn't affect fairness.

## Definition of done (v0.1)

- [ ] 5 tasks, all validated in CI
- [ ] 60 runs recorded with complete usage. Total cost ≤ $30, or run on a subscription
- [ ] Every price used marked `verified = true`
- [ ] Leaderboard live with CIs, the noop noise floor, and the mode label
- [ ] Raw data and the exact versions published
