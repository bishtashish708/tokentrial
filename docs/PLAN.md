# TokenTrial v0.1 — 2-week plan

**Goal:** publish a leaderboard answering one question with error bars: *for Claude Code on
one model, do RTK, caveman, and headroom lower the dollar cost per correctly solved task?*

## Scope

| Item | v0.1 decision |
|---|---|
| Agent | Claude Code CLI, pinned version, headless mode |
| Model | `claude-sonnet-5-5` (main). Spot-check on `claude-opus-5-5` if budget allows |
| Providers | Anthropic API (main) and Amazon Bedrock (price table + one confirming run) |
| Arms | `baseline`, `noop` (control), `rtk`, `caveman`, `headroom` |
| Tasks | 20, each with a hidden check script |
| Repeats | 5 per (task, arm), so 20 × 5 × 5 = **500 runs** |
| Output | `runs/*.jsonl`, `results/summary.json`, static site on GitHub Pages |

Out of scope for v0.1: other agents, effort sweeps, context-mode and CLAUDE.md arms (v0.2).

## Task set (20)

Each task lives in `tasks/<id>/` and contains:
- `task.toml`: the prompt, a time limit, a turn limit and tags
- `repo/`: the starting files
- `check.sh`: hidden from the agent. Exit code 0 means solved

To make sure every tool gets something to work on, the tasks are spread across workloads:

| Bucket | Count | Why it matters for the tools |
|---|---|---|
| Fix a failing test (Python) | 5 | Heavy test output, which is RTK's target |
| Fix a failing test (JS/TS) | 3 | Noisy npm or jest output |
| Small feature with spec tests | 4 | Balanced read, write and run work |
| Read a large codebase and answer an exact question | 3 | Context-heavy, which is headroom's target |
| Refactor while keeping tests green | 3 | Long sessions, so cache behaviour dominates |
| Log or build-output triage (exact answer) | 2 | Large tool outputs |

Each check must fail on the starting repo and pass on a reference solution. CI checks both.

## Cost model

For every API call in a run, usage is split into `input`, `cache_write_5m`, `cache_write_1h`,
`cache_read` and `output`, then priced from `src/tokentrial/data/pricing.toml`.

- Every price row has `source` and `verified`. `report` refuses to publish while any
  price it used is unverified.
- Bedrock rows are placeholders until filled in from the AWS pricing page (day 3).

**Headline metric:** cost per solved task = Σ cost over all runs ÷ number of solved runs, for
each arm. Also reported: solve rate, mean cost per run, turns, wall time, and cost split by
token type. The split by token type is what shows *why* a tool did or didn't help.

## Statistics

- Hierarchical bootstrap with 10,000 resamples: resample tasks, then runs within each task.
- Report the 95% CI for each arm and the paired difference from `baseline`.
- Noise floor: the CI of `noop − baseline`. A tool's effect counts only if its CI excludes 0
  **and** its point estimate is outside the noop CI.
- Arms are interleaved in a random order with a fixed seed, so API drift and cache
  temperature hit all arms equally. Each run starts from a cold workspace.

## Schedule

### Week 1: harness

| Day | Deliverable |
|---|---|
| 1 | Task format, loader, `check.sh` contract. First 5 tasks |
| 2 | Runner: isolated workspace per run, run Claude Code headless, capture usage per call into JSONL |
| 3 | Pricing: Anthropic rows verified, Bedrock rows filled in. Cost-split unit tests |
| 4 | Arm adapters: `noop`, `rtk`, `caveman`, `headroom` install and uninstall scripts at pinned versions |
| 5 | Tasks 6–20. CI checks that every check fails on the start state and passes on the reference |

### Week 2: experiment and leaderboard

| Day | Deliverable |
|---|---|
| 6 | Pilot run: 5 tasks × 5 arms × 2 repeats. Fix harness bugs. Calibrate the budget |
| 7 | Bootstrap module and `report` producing `summary.json` |
| 8 | Full run of 500 runs (spread over the day to stay under rate limits) |
| 9 | Static leaderboard: table, CI plot, cost-by-token-type bars. Deploy to GitHub Pages |
| 10 | Bedrock confirming run on a subset. Write-up. Tag v0.1 |

## Budget estimate

Assume about 300K input-side tokens per run, mostly cache reads, and 15K output tokens on
Sonnet 5.5. That's roughly $0.20–$0.60 per run, so **about $100–$300** for 500 runs. The pilot
on day 6 replaces this guess with a measured number before the full run.

## Risks

- **A tool needs per-repo setup or breaks Claude Code.** Use the setup from each tool's
  README and record any failure as a result, not something to work around.
- **Too much noise.** If the noop CI is wide, increase repeats on the tasks with the highest
  variance, not across the board.
- **Price changes mid-run.** Prices are versioned with each run, and the leaderboard shows
  the price-table date.
- **Fairness complaints.** Publish the arm configs and invite tool authors to review them
  before launch.

## Definition of done

- [ ] 20 tasks, all validated in CI
- [ ] 500 runs recorded with complete usage
- [ ] All prices used marked `verified = true`
- [ ] Leaderboard live on GitHub Pages with CIs and the noop noise floor
- [ ] Raw data and the exact versions published, so anyone can rerun the analysis
