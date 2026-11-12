# Pilot v0.1: findings

Run on 2026-11-12. Claude Code 2.1.252 headless on a Claude Code subscription, model
`claude-haiku-5-5`, 5 tasks × 4 arms × 3 repeats = 60 runs. All 60 runs solved their task.
The total API-equivalent cost was $0.28, and no usage limit was hit.

- Generated tables: [`summary.md`](summary.md), plus [`summary.json`](summary.json).
- Raw data: [`raw/`](raw/), with the home path and username scrubbed.
- Prices are list-price estimates that haven't been verified yet (see `pricing.toml`), so
  these results are **not leaderboard-grade**.

## Headline

| Arm | Cost per solved task, all calls | vs baseline (95% CI) | Benchmarked model only, vs baseline (95% CI) |
|---|---|---|---|
| `baseline` | $0.0054 | — | — |
| `noop` (noise floor) | $0.0049 | −10% (−30% to +6%) | −12% (−36% to +7%) |
| `rtk` v1.1.0 | $0.0046 | −15% (−38% to +10%) | −19% (−44% to +14%) |
| `caveman` v4.0.1 | $0.0038 | −29% (−46% to −14%) | −13% (−36% to +15%) |

**Neither tool shows a saving distinguishable from noise in this pilot.** The no-op control
alone came out 10% "cheaper" than baseline. At this sample size, differences of ±30% are within
noise.

## What is behind the numbers

1. **caveman's −29% comes almost entirely from a Claude Code side effect, not from shorter
   answers.**
   - In every non-caveman session (45 of 45), Claude Code made one small background call on
     `claude-haiku-4-5`: 938 input and 11 output tokens, about $0.001 or 20% of a run.
   - With the caveman plugin loaded it never did (0 of 15).
   - Counting only the benchmarked model, caveman is −13%, the same as `noop`.
   - caveman's mean output was 2,356 tokens against 2,594 for baseline (−9%) and 2,536 for noop
     (−2%). That's a small effect at most.
   - It is still open whether a user with caveman installed from the marketplace also skips
     that background call, or whether it's specific to loading it with `--plugin-dir` in
     headless mode.
2. **rtk was active but had little to compress.**
   - Its hook fired on Bash calls and rewrote `ls`, `cat`, `grep` and `read`-style commands.
     Per run it saved 0–164 tokens, against roughly 90K input-side tokens.
   - It did not rewrite `npm test` or `python3 -m unittest` in these tasks.
   - On `read-audit-writer` the agent mostly used the built-in Read and Grep tools, which rtk
     doesn't intercept.
   - Its −15% point estimate is in line with the noop control's −10%.
3. **Cost is dominated by cache writes and cache reads, not output.**
   - For baseline, the mean cost per run was $0.0054: cache writes $0.0022, output $0.0014,
     background call about $0.0010, cache reads $0.0009.
   - Every cache write used the 1-hour TTL.
   - A tool that only trims output or command text can't move much of this bill.

## Limitations

- **Too easy for Haiku.** Every arm solved every task, so solve rate can't separate the arms. The
  comparison rests on cost alone.
- **Small sample.** 5 tasks × 3 repeats gives wide intervals: the noise floor alone spans about
  36 percentage points.
- **caveman ran in its first-session state every time.** Its session-start text includes a
  one-time nudge to "proactively offer" a statusline setup. The adapter resets caveman's state
  before each run, so every run saw it. A long-time user would not, so this may slightly
  penalize caveman. To fix in v0.2 by pre-seeding the "nudge shown" state.
- **Claude Code doesn't recognize `claude-haiku-5-5`.** Version 2.1.252 logs `unrecognized_model`
  for it and assumes a 200K context window. That's the same for every arm, but a newer Claude
  Code may behave differently.
- **One agent, one model, small toy tasks.** These numbers say nothing about large real repos,
  where command output and context are much bigger.

## Suggested next steps

- Find out why loading caveman removes Claude Code's background call, and whether a marketplace
  install does the same.
- Seed caveman's steady-state user state.
- Add harder tasks with large command outputs, where rtk's filters apply (pytest, cargo, git log).
- Increase repeats so the noise floor is narrow enough to resolve effects of around 10%.
