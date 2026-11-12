# TokenTrial

**Does your token-saving tool actually save money?**

TokenTrial is an open benchmark for the token-saving tools that coding agents use, such as
[RTK](https://github.com/rtk-ai/rtk), [caveman](https://github.com/JuliusBrussee/caveman),
[headroom](https://github.com/headroomlabs-ai/headroom), context-mode and CLAUDE.md variants.
It runs the same coding tasks with and without each tool and reports the number that matters:
**dollars per correctly solved task**.

> **v0.2 results (2026-11-12, 400 runs, Haiku 5.5, verified prices):**
> - **rtk** v1.1.0 *raised* cost per solved task by **36%** (95% CI +17% to +53%). Compressed test
>   and git output led the agent to re-run commands and take extra turns.
> - **caveman** v4.0.1 had **no measurable effect** (−0%, CI −10% to +11%) against a control that
>   reproduces a Claude Code side effect it triggers.
> - A do-nothing arm alone moved cost by +11%.
>
> Leaderboard: https://bishtashish708.github.io/tokentrial/ · Details:
> [`results/v0.2/FINDINGS.md`](results/v0.2/FINDINGS.md). Pilot:
> [`results/pilot-v0.1/FINDINGS.md`](results/pilot-v0.1/FINDINGS.md).

> Status: alpha. The runner, the arms, verified prices and `report` work. v0.1 and v0.2 have run.
> A static leaderboard is generated from `results/v0.2/summary.json` by `scripts/make_site.py`
> into `docs/`. See [docs/PLAN.md](docs/PLAN.md).

## Why

Token-saving tools publish large savings figures, usually counted on the tokens they compress.
But an agent's bill is made of four token types with very different prices:

| Token type   | Typical price relative to fresh input |
|--------------|---------------------------------------|
| Fresh input  | 1x                                    |
| Cache write  | about 1.25x (5 min) or 2x (1 h)       |
| Cache read   | about 0.05x to 0.1x                   |
| Output       | about 5x                              |

A tool can cut 90% of the tokens it touches and still not lower the bill. That happens if those
tokens were cheap cache reads, if the tool breaks the prompt cache, or if the agent needs more
turns or fails more tasks. [Quesma's analysis of RTK](https://quesma.com/blog/does-rtk-make-ai-coding-cheaper/)
is one example: it questioned whether a headline saving of 89% turned into a lower total cost.
TokenTrial makes this kind of check repeatable, public, and applicable to any tool.

## Methodology (planned)

1. **Tasks with checkable answers.** Each task is a small repo plus a hidden check script
   (tests or an exact output). A run is "solved" only if the check passes. Agents don't grade
   themselves.
2. **Arms.**
   - `baseline`: the unmodified agent.
   - `noop`: a control arm. It goes through the same install and wiring steps as a tool but
     changes nothing. Any difference between `noop` and `baseline` is noise.
   - One arm per tool, installed at a pinned version with its documented setup. The v0.1
     pilot tests `rtk` and `caveman`.
3. **Same conditions.** Same model, agent version, prompt, task snapshot and limits for
   every arm. Arms run interleaved, not in blocks, so API-side drift affects them all equally.
   Each (task, arm) pair runs N times (default 3 in the pilot).
4. **Full token accounting.** Usage is taken from API responses for every call in a run and
   split into fresh input, cache write (5 min / 1 h), cache read and output. It's then priced
   from a versioned table ([`pricing.toml`](src/tokentrial/data/pricing.toml)) for Anthropic
   and Amazon Bedrock.
5. **Headline metric.** `total cost of all runs / number of solved runs`, per arm. Also
   reported: solve rate, cost per run, turns per run, and the cost split by token type.
6. **Uncertainty.** 95% confidence intervals from a bootstrap that resamples tasks, then runs
   within each task. Differences are reported against `baseline`, with the `noop` gap shown
   next to them. A tool counts as "saving money" only if its interval clears both.
7. **Reproducibility.** Raw usage records, the tool versions, the price table and the code
   commit are published with every leaderboard entry.

## Usage

TokenTrial runs on your **Claude Code subscription by default**. No API key is needed. It
drives `claude --print --output-format stream-json` headlessly, records token usage for every API
call, and prices that usage at API rates. This gives an API-equivalent cost for each run.

```bash
uv sync
uv run tokentrial doctor                          # checks claude is installed and logged in (no model call)
uv run tokentrial run --dry-run                   # show the planned run matrix
uv run tokentrial run --arm baseline --arm noop   # run on the subscription
uv run tokentrial run --resume --out runs/pilot   # continue after a usage limit
uv run tokentrial run --mode api                  # optional: bill ANTHROPIC_API_KEY instead
uv run tokentrial report                          # aggregate runs and build the leaderboard (coming soon)
```

Defaults are set for a low-cost pilot: Claude Haiku 5.5, 3 repeats, and caps of $30 total and $1
per run (API-equivalent). Subscription usage limits make runs slower. When one is hit, TokenTrial
saves progress, prints when to come back, and exits with code 3. `--resume` continues without
repeating finished runs.

Install the pinned tool arms once with `uv run tokentrial install-arms`. Then
`uv run tokentrial report --runs runs/<exp> --export-raw` writes `summary.md`, `summary.json` and
scrubbed raw data to `results/<exp>/`.

## Leaderboard

Published on GitHub Pages from `docs/`: https://bishtashish708.github.io/tokentrial/. Regenerate
it with `uv run python scripts/make_site.py results/<exp> docs/index.html`.

## Roadmap

- **v0.1 pilot (2 weeks, on a Claude Code subscription):** 5 tasks × 4 arms (`baseline`, `noop`,
  `rtk`, `caveman`) × 3 repeats, so 60 runs on Claude Haiku 5.5. API-equivalent cost, budget caps,
  `--resume` across usage limits, bootstrap CIs, and a static leaderboard. See
  [docs/PLAN.md](docs/PLAN.md).
- **v0.2 (done):** 10 tasks, including 5 with large pytest and git output, × 5 arms (adding a
  `noop-hook` control) × 8 repeats = 400 runs on a subscription, with verified prices.
- **v0.3 (prepared, not run):** 18 tasks across Python, Node, C, SQL and bash; rtk v1.2.0 and
  caveman v4.1.0 next to the v0.2 pins; headroom with a proxy-only control; Haiku 5.5 and
  Sonnet 5.5. See the [v0.3 plan](docs/PLAN.md#v03-plan-proposed-not-started).
- **Later:** more tools (context-mode, CLAUDE.md variants), more agents and models, effort-level
  sweeps, and a template so tool authors can submit their own arm.
- **Later:** a CI job that reruns the leaderboard when a tool releases a new version, and
  cost-versus-latency plots.

## Contributing

Issues and task proposals are welcome. A good task is small, takes a few minutes for an agent,
and has a check that can't pass by accident.

## License

[MIT](LICENSE)
