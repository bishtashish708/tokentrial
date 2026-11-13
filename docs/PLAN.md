# TokenTrial plan

TokenTrial ships in tiers. **v0.1 is a low-budget pilot.** It runs on a **Claude Code
subscription by default**, so it costs nothing beyond the subscription. Every run is still priced
at API rates, so results are comparable. API-key mode is kept as an option for later. The full
20-task, 500-run benchmark comes later, once the pilot shows the approach is useful.

## Status

| Piece | State |
|---|---|
| Subscription runner (`claude --print`, stream-json, usage per call) | Done, tested against a fake `claude` |
| API-equivalent cost by token type | Done |
| Budget caps (`--max-usd`, `--max-usd-per-run`) | Done, enforced during each run |
| Usage-limit detection, checkpointing, `--resume` | Done |
| `tokentrial doctor` (install and login check, no model call) | Done |
| Tasks | 5 of 5, all validated in CI (check fails on start, passes on reference) |
| Arm adapters | All 4 done. rtk v1.1.0 and caveman v4.0.1 are pinned and installed with `tokentrial install-arms` |
| Smoke run | ✅ baseline and noop: 2 of 2 solved, about $0.003 per run API-equivalent |
| Arm activation check | ✅ 2026-11-12, `js-chunk-remainder` × 4 arms: 4 of 4 solved, $0.013 in total. rtk's hook fired and rewrote commands. caveman's SessionStart and UserPromptSubmit hooks injected caveman mode. Ready for the pilot, pending the go-ahead |
| `report` and bootstrap | ✅ `tokentrial report [--export-raw]`. Task-then-run hierarchical bootstrap, paired by task, with the noop noise floor |
| Pilot run | ✅ 2026-11-12: 60 of 60 runs solved, $0.28 API-equivalent, no usage limit hit. See [`results/pilot-v0.1/FINDINGS.md`](../results/pilot-v0.1/FINDINGS.md) |
| v0.2 run | ✅ 2026-11-12: 10 tasks × 5 arms × 8 repeats = 400 runs, 396 solved, $2.87 API-equivalent, all prices verified. See [`results/v0.2/FINDINGS.md`](../results/v0.2/FINDINGS.md) |
| Leaderboard | ✅ Static page from the v0.3 and v0.2 `summary.json` files: https://bishtashish708.github.io/tokentrial/ |
| v0.3 prep | ✅ 2026-11-12: 18 tasks, new arms (rtk v1.2.0, caveman v4.1.0, headroom 0.42.0 and two controls), `--model` repeatable, `--pause-at-utilization`. Activation-checked on Haiku. See [v0.3 plan](#v03-plan) |
| v0.3 run | ✅ 2026-11-12/13: Haiku 18 × 9 × 5 = 810 runs (805 solved, $7.85) and Sonnet 18 × 7 × 3 = 378 runs (373 solved, $17.76). One 10-minute pause at 60% of the five-hour window. Claude Code auto-updated 2.1.252 → 2.1.322 after 447 Haiku runs. See [`results/v0.3/FINDINGS.md`](../results/v0.3/FINDINGS.md) |
| Next: pin the agent | Set `DISABLE_AUTOUPDATER=1` for the agent and stop a run if the Claude Code version changes |
| Checked against real Claude Code output | ✅ Smoke runs on 2026-11-12: recorded usage matches Claude Code's totals exactly (findings below) |

## Tiers and cost estimates

| Tier | Tasks | Arms | Repeats | Runs | Model | Estimated cost |
|---|---|---|---|---|---|---|
| **v0.1 pilot** | 5 | 4 | 3 | **60** | `claude-haiku-5-5` | **$0 extra on a subscription (default).** About $1–25 API-equivalent, hard cap $30 |
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
| Modes | **`subscription` (default):** logged-in Claude Code, API-equivalent cost. `api` (API key, billed) is optional, for later |
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

## Subscription mode (default, no API key)

The runner drives the Claude Code CLI headlessly under the user's logged-in subscription.

**How each run works**

1. Copy the task's `repo/` into a fresh temporary directory, `git init` it, and apply the arm's
   setup.
2. Start Claude Code headlessly and send the task prompt on stdin:

   ```
   claude --print --output-format stream-json --verbose --model <model> \
     --permission-mode dontAsk --allowedTools Read,Edit,Write,Glob,Grep,Bash \
     --setting-sources project --strict-mcp-config --disable-slash-commands \
     --no-session-persistence
   ```

   The isolation flags make every arm start from the same Claude Code configuration. User-level
   settings, MCP servers and slash commands are excluded. Only the workspace's own project
   settings apply, and that is where a tool arm installs itself. `--bare` would isolate further,
   but it can't use subscription login.
3. For subscription runs, `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` are removed from the
   agent's environment, so it can't fall back to billing an API account. `tokentrial doctor`
   checks that `claude auth status` reports a `claude.ai` login.
4. Each `assistant` event in the stream carries the API usage for that call. The runner keys usage
   by message ID, because Claude Code repeats it once per content block. It splits usage into
   fresh input, cache write (5-minute or 1-hour TTL), cache read and output, and prices it from
   `pricing.toml`. The budget caps are checked as each call arrives. If no per-call usage
   appears, the session totals from the final `result` event are used instead.
5. The run ends at the `result` event or the task timeout. The hidden `check.sh` runs on the
   workspace, which is then deleted.

Each record stores the usage by type, the cost by type (`cost_basis: api_equivalent`), the number
of API calls and turns, the duration, Claude Code's own `total_cost_usd` (for comparison only),
and the `init` event (model, tools, MCP servers) so fairness can be checked later. The raw stream
is kept in `runs/<exp>/logs/<run_id>.jsonl`.

**Usage limits, checkpointing and `--resume`**

- Subscription usage limits make this slower than API mode. The 60 pilot runs will probably take
  several sessions, possibly over a few days.
- When Claude Code reports a usage or rate limit, the runner stops cleanly. It looks for this in
  the `result` event, in an assistant error, or in stderr when there is no result. The
  interrupted run is **not** recorded. The runner prints the reset time if one is reported and
  exits with code 3.
- Progress is kept in `runs/<exp>/manifest.json` (the config) and `runs/<exp>/records.jsonl` (one
  line per finished run, appended). `tokentrial run --resume --out runs/<exp>` reloads the saved
  config, skips every run whose status is final (`solved`, `unsolved`, `aborted_budget`,
  `timeout`), retries runs that ended in `error`, and carries the spent budget forward.
- Starting a new run with an `--out` that already holds an experiment is refused, so results are
  never mixed by accident.

**Arm isolation**

- rtk is installed per workspace: `rtk init` without `-g` writes the Bash PreToolUse hook to the
  workspace's `.claude/settings.json`, plus `RTK.md` and a `CLAUDE.md` reference. rtk is put on the
  agent's PATH. The setup fails loudly if no hook was written. The binary comes from the pinned
  GitHub release and is verified against the release's `checksums.txt`.
- caveman is loaded per session with `--plugin-dir`, from a clone at the pinned tag that is
  verified against the pinned commit. Headless sessions start with caveman off unless
  `CAVEMAN_DEFAULT_MODE` is set, so the arm sets it to `caveman`. caveman's hooks keep state in
  `~/.claude/.caveman-active` and `~/.claude/.caveman-sessions/`. The adapter removes whatever a
  run created there.
- Nothing is installed into the user's global Claude Code configuration.

**Arm activation check (2026-11-12)**

- **rtk.** A project-scoped `rtk init` registers no hook, so the adapter generates the global
  install in a throwaway HOME and copies it into the workspace's project settings.
  - rtk also checks the user's real Claude settings for its hook. When it's missing, rtk prints
    "No hook installed" into every command's output, which the agent then reads. rtk is
    therefore run through a per-run shim that shows it a config view containing the hook.
  - Each run starts from fresh rtk state; `history.db` is reset. Telemetry is off.
  - In the check, the hook fired on every Bash call and rewrote `ls`, `cat` and `grep` (inside a
    pipe) to `rtk ls`, `rtk read` and `rtk grep`. `rtk gain` recorded 3 commands and 55 tokens
    saved. `npm test` itself was not rewritten.
- **caveman.** The SessionStart hook injected the caveman rules, and UserPromptSubmit added the
  "CAVEMAN MODE ACTIVE" context on each prompt. The agent's replies were visibly terse.
  - Its hooks leave files in `~/.claude`, including a one-time nudge marker that would change
    later sessions. All `.caveman*` entries a run creates are removed afterwards.
- Every record includes `hook_events` (hook activity from `--include-hook-events`) and
  `arm_metrics` (e.g. `rtk gain`), as evidence that the arm was active.

**What the smoke runs established (Claude Code 2.1.252, 2026-11-12)**

- **Usage source.** Per-message `usage` in the stream is a snapshot taken mid-stream. Its output
  count is incomplete: 12 against a real 1,116, because it misses final output and thinking
  tokens. The `result` event's `usage` is authoritative and is what gets recorded. The
  per-message snapshots, plus `thinking_tokens` estimates, are only used for live budget checks,
  which are reconciled to the final cost when the `result` event arrives.
- **Background calls.** Claude Code also makes a small background call on `claude-haiku-4-5`
  each session (938 input and 11 output tokens). It's reported in `modelUsage`, priced from
  `pricing.toml` and included in each run's cost. It's about 30% of a short Haiku 5.5 run's cost
  and identical across arms. A model with no price entry is listed in `unpriced_models`.
- **Claude Code's own `total_cost_usd` is wrong for Haiku 5.5.** Claude Code 2.1.252 logs
  `unrecognized_model` for `claude-haiku-5-5` and prices it like Opus, at $5/$25 per 1M tokens:
  it reported $0.106 against an API-equivalent $0.003. The figure is kept in records but never
  used. The same version also assumes a 200K context window for the model. That's the same for
  every arm, so the comparison is still fair.
- **Cache writes** observed so far all use the 1-hour TTL.
- **Limits.** Each session emits a `rate_limit_event` with a status, a reset time and five-hour
  and seven-day utilization. Any status other than `allowed*` pauses the experiment with that
  reset time. Utilization is recorded with every run. Error text and HTTP 429 are still detected
  as fallbacks.
- **Isolation, verified from the `init` event:** exactly 6 tools, no MCP servers, no skills,
  plugins or slash commands, `memory_paths: null` (auto-memory off), and `apiKeySource: none`
  (subscription).

## First smoke run

This is the first real run. It uses one task, the two arms that have adapters, and one repeat, so
it makes 2 Haiku sessions on the subscription. It goes to its own `--out` so it doesn't mix with
the pilot:

```bash
uv run tokentrial doctor
uv run tokentrial run --arm baseline --arm noop --repeats 1 --max-usd 2 --out runs/smoke
```

After it finishes, check `runs/smoke/records.jsonl`:

- Usage by type is non-zero.
- `cost_usd.total` is close to `reported_cost_usd`.
- `claude_init` lists only the allowed tools and no MCP servers.

Also check the raw logs for any trace of user-level CLAUDE.md or memory.

## Task set (pilot: 5)

Each task lives in `tasks/<id>/`. It has `task.toml` (prompt and limits), `repo/` (starting
files), `check.sh` (hidden from the agent, exit 0 = solved) and `solution/`. The five pilot tasks
cover the workloads that matter most to the two tools under test:

| ID | Task type | Why |
|---|---|---|
| `py-ledger-parens` | Fix a failing Python test with verbose `unittest -v` output | RTK's main target |
| `js-chunk-remainder` | Fix a failing JS test with noisy `npm test` / `node --test` output | RTK, in a second ecosystem |
| `py-duration-spec` | Implement two functions from a docstring spec. Hidden tests cover the full spec | Balanced work, where caveman's terse output should show |
| `read-audit-writer` | Trace an indirect call path (event bus → registry → settings override) and give an exact dotted name | Context-heavy, little output |
| `log-link-failure` | Find the failing `path:line` in a CI log with distractor errors (an ignored legacy error, a flaky test rerun) | Large tool output |

The build log is generated deterministically by `scripts/make_build_log.py`.

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
| 1 | ✅ Task format, loader, `check.sh` contract. ✅ Task 1 |
| 2 | ✅ Runner: isolated workspace, Claude Code headless (subscription by default), usage per call, checkpoint and `--resume`. Next: the smoke run to validate against real output |
| 3 | Pricing: Anthropic rows verified, Haiku long-prompt tier, Bedrock rows filled in. ✅ Budget caps wired into the runner |
| 4 | ✅ Arm adapters: `noop`, `rtk` (project-scoped `rtk init` hook), `caveman` (`--plugin-dir`, `CAVEMAN_DEFAULT_MODE=caveman`) |
| 5 | ✅ Tasks 2–5. ✅ CI validates every check |

### Week 2: pilot and leaderboard

| Day | Deliverable |
|---|---|
| 6 | Shakedown: 1 task × 4 arms × 1 repeat, capped at $2. Measure real cost per run and fix bugs |
| 7 | Bootstrap module and `report` producing `summary.json` |
| 8 | Full pilot of 60 runs on the subscription, capped at $30 API-equivalent. Use `--resume` across usage-limit windows |
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

## v0.3 plan

Run on 2026-11-12/13 as planned below; results in [`results/v0.3/FINDINGS.md`](../results/v0.3/FINDINGS.md).

### What changed since v0.2

- **Tasks: 10 → 18.** v0.2's intervals were driven by task-to-task variance, so v0.3 adds
  variety rather than repeats. New: `c-ring-buffer` (C), `js-csv-quoted-fields`,
  `js-lru-ttl-cache` (Node; bug fix and feature-from-spec), `sql-monthly-revenue` (SQLite),
  `sh-backup-rotate` (bash), `py-perf-dedupe` (performance), `py-cli-json-output` (multi-file
  feature) and `read-config-precedence` (code reading, exact answer). Each was validated the same
  way as before: the check fails on the start state, passes on the reference, and fails with the
  visible tests blanked. Hidden cases come from a seeded generator and are cross-checked against
  an independent implementation. Haiku solved all 8 in a single calibration run each
  (2026-11-12, $0.13), so difficulty is still a limitation; the new tasks are about 2.4× costlier
  per run than v0.2's ($0.0166 against $0.0068 on baseline).
- **Arms.**
  - `rtk-v1.2.0` and `caveman-v4.1.0` run next to the v0.2 pins, using the same adapters. Both
    releases kept the hook layout, environment variable and state paths.
  - `headroom` (0.42.0, the newest release at least two weeks old) runs a per-run
    `headroom proxy` with its MCP retrieve server, as `headroom wrap claude` does, without writing
    to `~/.claude.json`. Telemetry, the usage beacon and the subscription-usage poller are off.
  - Controls. The activation check found that **Claude Code skips its background title call when
    its traffic goes through a local proxy** (a third side effect after the SessionStart hook);
    `ANTHROPIC_BASE_URL` set to Anthropic's own URL does not cause it (`noop-baseurl`, one run).
    `headroom-passthrough` runs the same proxy and MCP server with `--no-optimize`, so `headroom`
    vs `headroom-passthrough` isolates the compression. `report` now compares each tool with its
    matched control.
- **Models.** `--model` is repeatable; each model gets its own experiment under
  `--out/<model>/`. Sonnet 5.5 prices were re-checked (unchanged; no long-context tier).
- **Shared subscription.** `--pause-at-utilization 0.6` pauses resumably (exit 3) once the
  five-hour window reaches 60%, leaving room for the other project on the same account.

### Activation check (Haiku, `py-pytest-cart-pricing`, 1 repeat)

| Arm | Solved | Cost | Evidence |
|---|---|---|---|
| `rtk-v1.2.0` | ✅ | $0.0127 | PreToolUse hook fired 4×; `rtk gain`: 8 commands, 371 tokens saved; no "No hook installed" nag |
| `caveman-v4.1.0` | ✅ | $0.0072 | SessionStart + UserPromptSubmit hooks fired; "CAVEMAN MODE ACTIVE — mode: caveman" in context |
| `headroom` | ✅ | $0.0121 | 7 requests through the proxy, 5 compressed (1,640 tokens removed); MCP server connected; no title call |
| `headroom-passthrough` | ✅ | $0.0089 | 9 requests, 0 compressed; no title call |
| `noop-baseurl` | ✅ | $0.0060 | title call still made, so a base URL alone is not the trigger |

### Proposed matrix

| Phase | Model | Tasks | Arms | Repeats | Runs |
|---|---|---|---|---|---|
| A | Haiku 5.5 | 18 | 9: baseline, noop, noop-hook, headroom-passthrough, rtk, rtk-v1.2.0, caveman, caveman-v4.1.0, headroom | 5 | **810** |
| B0 | Sonnet 5.5 calibration | 2 | 5 (baseline, noop-hook, rtk-v1.2.0, caveman-v4.1.0, headroom) | 1 | **10** |
| B | Sonnet 5.5 | 18 | 6: baseline, noop-hook, headroom-passthrough, rtk-v1.2.0, caveman-v4.1.0, headroom | 3 | **324** |

Sonnet drops `noop` (Haiku measures the noise floor), the old tool pins (the version comparison
is on Haiku) and goes to 3 repeats, because each Sonnet run costs about 16× a Haiku run.

### Usage estimate

Measured: v0.2 moved the five-hour window by about **4.2% per $1 of Haiku API-equivalent cost**
(+9 points for $2.10 in one window; +3 for $0.77 in the next) and the weekly window by about 1
point for the whole run ($2.87). Assumption: subscription usage scales with API-equivalent cost
across models. That is not documented and is the main uncertainty, which is why phase B0 exists.

| Phase | Est. API-equivalent | Five-hour window | Weekly window | Wall clock |
|---|---|---|---|---|
| A (Haiku, 810) | $9–11 (≈$0.012/run) | ≈40–45 points in total, spread over the run; never near the limit | ≈3–7% | ≈13 h (mean ≈60 s per run) |
| B0 (Sonnet, 10) | ≈$2 | ≈8 points | <1% | ≈15 min |
| B (Sonnet, 324), superseded by the B0 result below | ≈$50–70 (≈$0.15–0.20/run) | ≈210–290 points: **4–5 windows** at a 60% pause threshold | ≈20–25% (could be 10–45% if usage is not proportional to price) | ≈7 h of runs plus pauses: **1.5–3 days** |

Per-run Sonnet cost assumes the same tokens as Haiku priced at Sonnet rates (20× for input,
cache writes and output, 10× for cache reads), which gives ≈16×. Sonnet often takes fewer turns,
so this is probably high. The parallel project's own use is not included: the five-hour window
rose from 5% to 15% during this prep while tokentrial used about 1 point.

Caps: `--max-usd 20` for A and `--max-usd 90 --max-usd-per-run 2` for B (API-equivalent).

### B0 result: Sonnet calibration (2026-11-12, done)

10 runs (2 tasks × 5 arms, Sonnet 5.5): 10 of 10 solved, **$0.66 API-equivalent, mean $0.066
per run**, 5 minutes. Raw data: [`results/v0.3-sonnet-calib/`](../results/v0.3-sonnet-calib/).

- **Cost per run is about 4–8× Haiku, not 16×.** On the same tasks Sonnet averaged $0.061
  (cart pricing) and $0.072 (CSV) against Haiku's $0.008 and $0.019. Sonnet took fewer turns
  (7.7 against 8.8 on cart) and wrote much less output (about 2.4K tokens against 5–20K).
- **Usage.** The five-hour window went from 17% to 19% across the first 9 runs ($0.60), about
  **3.3 points per $1** (1.7–5 given 1-point granularity, and an upper bound because the
  compact-diff project ran at the same time). That is in line with Haiku's 4.2 points per $1,
  so usage looks roughly proportional to API-equivalent cost. Per Sonnet run: about **0.2
  points** of the five-hour window. The weekly window did not move (8%).

**Corrected phase B estimate (324 runs):** about **$21 API-equivalent** ($14–28), about **70
points of the five-hour window** (35–110), so 1–2 windows at the 60% pause threshold, about
**7% of the weekly window** (4–15%), and about 3 hours of runs plus any pauses. That is roughly a
third of the earlier estimate.

### Commands

```
uv run tokentrial run --model claude-haiku-5-5 --repeats 5 --seed 3 --max-usd 20 \
  --pause-at-utilization 0.6 --out runs/v0.3-haiku \
  --arm baseline --arm noop --arm noop-hook --arm headroom-passthrough --arm rtk \
  --arm rtk-v1.2.0 --arm caveman --arm caveman-v4.1.0 --arm headroom
uv run tokentrial run --model claude-sonnet-5-5 --repeats 1 --max-usd 5 --max-usd-per-run 2 \
  --pause-at-utilization 0.6 --out runs/v0.3-sonnet-calib \
  --task py-pytest-cart-pricing --task js-csv-quoted-fields \
  --arm baseline --arm noop-hook --arm rtk-v1.2.0 --arm caveman-v4.1.0 --arm headroom
uv run tokentrial run --model claude-sonnet-5-5 --repeats 3 --seed 3 --max-usd 90 \
  --max-usd-per-run 2 --pause-at-utilization 0.6 --out runs/v0.3-sonnet \
  --arm baseline --arm noop-hook --arm headroom-passthrough --arm rtk-v1.2.0 \
  --arm caveman-v4.1.0 --arm headroom
```

After a pause, continue with `uv run tokentrial run --resume --out <dir>`.

## Definition of done (v0.1)

- [ ] 5 tasks, all validated in CI
- [ ] 60 runs recorded with complete usage. API-equivalent total ≤ $30
- [ ] Every price used marked `verified = true`
- [ ] Leaderboard live with CIs, the noop noise floor, and the mode label
- [ ] Raw data and the exact versions published
