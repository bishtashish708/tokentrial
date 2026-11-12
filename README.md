# TokenTrial

**Does your token-saving tool actually save money?**

TokenTrial is an open benchmark for the token-saving tools that coding agents use, such as
[RTK](https://github.com/rtk-ai/rtk), [caveman](https://github.com/JuliusBrussee/caveman),
[headroom](https://github.com/headroomlabs-ai/headroom), context-mode and CLAUDE.md variants.
It runs the same coding tasks with and without each tool and reports the number that matters:
**dollars per correctly solved task**.

> Status: pre-alpha. The CLI is a stub and nothing has been measured yet. See
> [docs/PLAN.md](docs/PLAN.md) for the first version.

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
   - One arm per tool, installed at a pinned version with its documented setup.
3. **Same conditions.** Same model, agent version, prompt, task snapshot and limits for
   every arm. Arms run interleaved, not in blocks, so API-side drift affects them all equally.
   Each (task, arm) pair runs N times (default 5).
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

```bash
uv sync
uv run tokentrial --help
uv run tokentrial run --dry-run            # show the planned run matrix
uv run tokentrial run --arm baseline --arm rtk --repeats 5
uv run tokentrial report                   # aggregate runs and build the leaderboard
```

`run` and `report` only print a plan for now. Real execution comes in v0.1.

## Leaderboard

Results will be published as a static site on GitHub Pages from this repository.

## Roadmap

- **v0.1 (2 weeks):** 20 tasks, a baseline, a `noop` control and 3 tool arms, on one agent
  (Claude Code) and one model. Anthropic and Bedrock pricing, bootstrap CIs, and a static
  leaderboard. See [docs/PLAN.md](docs/PLAN.md).
- **v0.2:** more tools (context-mode, CLAUDE.md variants) and a template so tool authors can
  submit their own arm.
- **v0.3:** more agents and models, effort-level sweeps, and a larger task set built from
  real-repo bug fixes.
- **Later:** a CI job that reruns the leaderboard when a tool releases a new version, and
  cost-versus-latency plots.

## Contributing

Issues and task proposals are welcome. A good task is small, takes a few minutes for an agent,
and has a check that can't pass by accident.

## License

[MIT](LICENSE)
