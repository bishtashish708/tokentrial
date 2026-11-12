# Show HN draft

> Draft only. Not posted.

## Title

Show HN: TokenTrial – do token-saving tools cut Claude Code's bill?

(67 characters; HN limit is 80. Alternative: "Show HN: TokenTrial – rtk raised Claude Code's cost per solved task 36%", 71 characters)

## URL

https://github.com/bishtashish708/tokentrial

## Body

TokenTrial is a small open benchmark for the token-saving tools people add to coding agents. It runs
the same tasks with and without a tool, checks each answer with a hidden test, and reports dollars
per correctly solved task with bootstrap confidence intervals. The cost includes every token type:
input, cache writes, cache reads and output.

The first real run: 10 tasks × 5 arms × 8 repeats = 400 Claude Code runs on Haiku 5.5, which cost
$2.87 API-equivalent on a subscription.

**What we found**

- **rtk v1.1.0 raised cost per solved task by 36%** (95% CI +17% to +53%). rtk compresses shell
  output such as pytest and git logs, and by its own count it did remove up to 4,500 tokens of
  output per run. But on the tasks where it compressed the most, the agent re-ran commands with
  `rtk bypass` to see the full output (88 times in 80 runs) and took more turns: 8.2 → 13.4 on one
  task. Each extra turn re-reads the cached context, which costs more than the trimmed output
  saved. This matches Quesma's earlier analysis.
- **caveman v4.0.1 showed a 29% saving in our pilot, which turned out to come from Claude Code
  itself.** Claude Code 2.1.252 makes a small background call to generate a session title, and
  skips it whenever *any* SessionStart hook is configured. caveman installs one. A do-nothing
  SessionStart hook (`true`) reproduces the effect. Against that control, caveman's effect on cost
  is −0% (CI −10% to +11%). It did cut output tokens by about 11%. But output is only about 40%
  of the bill here, so the effect disappears in the noise.
- **A do-nothing arm moved cost by +11%** (CI −2% to +24%). Small before/after comparisons of agent
  cost are mostly noise.

**Caveats**

- One model (Haiku 5.5) and one Claude Code version (2.1.252). That version doesn't recognize the
  Haiku 5.5 model ID, which affects every arm equally.
- The tasks are synthetic and small to medium. Haiku solved 396 of 400 runs, so the comparison
  rests on cost, not solve rate.
- The tools are pinned to rtk v1.1.0 and caveman v4.0.1. Newer releases (rtk v1.2.0, caveman v4.1.0)
  were 3 days old when the runs were pinned, so they weren't tested.
- Costs are API-equivalent: usage reported by Claude Code, priced at list prices. All prices were
  checked against the Anthropic and AWS Bedrock pages, and the sources are in the repo.
- These results say nothing about large real repos, where outputs and contexts are much bigger and
  the trade-off could differ.

The tool authors haven't reviewed this yet. I'd welcome corrections from them or anyone else,
especially if the arm setup doesn't match how the tools are meant to be used.

**Reproduce**

```
git clone https://github.com/bishtashish708/tokentrial && cd tokentrial
uv sync
uv run tokentrial doctor
uv run tokentrial install-arms    # pinned rtk + caveman, checksum/commit verified
uv run tokentrial run --repeats 8 --seed 2 --out runs/v0.2 \
  --arm baseline --arm noop --arm noop-hook --arm rtk --arm caveman
uv run tokentrial report --runs runs/v0.2
```

It runs on a Claude Code subscription by default; `--mode api` bills an API key instead. Runs
checkpoint and pause cleanly on usage limits (`--resume`). Raw per-run records and scrubbed agent
transcripts are in `results/v0.2/raw/`.

Leaderboard: https://bishtashish708.github.io/tokentrial/
Write-up: https://github.com/bishtashish708/tokentrial/blob/main/results/v0.2/FINDINGS.md

Next: harder tasks where solve rates differ, Sonnet, newer tool versions, and more tools
(headroom, context-mode, CLAUDE.md variants). Task proposals are welcome.
