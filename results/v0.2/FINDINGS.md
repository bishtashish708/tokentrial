# v0.2: findings

Run on 2026-11-12. Claude Code 2.1.252 headless on a Claude Code subscription, model
`claude-haiku-5-5`. 10 tasks × 5 arms × 8 repeats = 400 runs; 396 solved. The total
API-equivalent cost was $2.87, priced with **verified** prices (see `pricing.toml`; checked
2026-11-12 against the Anthropic and AWS Bedrock pricing pages). No usage limit was hit. No call
crossed Haiku 5.5's 100K-token long-context threshold.

- Generated tables: [`summary.md`](summary.md), plus [`summary.json`](summary.json).
- Raw data: [`raw/`](raw/), with the home path and username scrubbed.
- Tool versions: rtk v1.1.0, caveman v4.0.1.

## Headline

| Arm | Solved | Cost per solved task | vs baseline (95% CI) | vs `noop-hook` (95% CI) |
|---|---|---|---|---|
| `baseline` | 80/80 | $0.0068 | — | |
| `noop` (noise floor) | 80/80 | $0.0076 | +11% (−2% to +24%) | |
| `noop-hook` (control) | 79/80 | $0.0062 | −9% (−24% to +7%) | — |
| **`rtk`** | 80/80 | $0.0093 | **+36% (+17% to +53%)** | **+49% (+26% to +81%)** |
| `caveman` | 77/80 | $0.0062 | −9% (−21% to +5%) | −0% (−10% to +11%) |

1. **rtk made runs more expensive.** Cost per solved task rose 36% against baseline. That's beyond
   the noise floor, and it rises to 49% against the matching hook control.
2. **caveman had no measurable cost effect once a Claude Code side effect is controlled for**
   (−0% against `noop-hook`, 95% CI −10% to +11%).
3. **A do-nothing arm moved cost by +11%** (`noop` against `baseline`). Single runs, or a handful,
   cannot tell a real saving from noise.

## Why rtk cost more

rtk was active: its hook fired in 73 of 80 runs, and the other 7 made no Bash calls. It rewrote
`pytest` and `git log/show/diff`. By its own accounting it saved 30–4,500 tokens of command output
per run. But the agent took more turns where rtk compressed the most:

| Task | Turns, baseline → rtk | `rtk bypass` re-runs per run | Cost, rtk ÷ baseline |
|---|---|---|---|
| `py-cron-tz` | 8.2 → 13.4 | 4.9 | 1.37 |
| `py-cron-next` | 6.0 → 9.6 | 1.8 | 1.47 |
| `py-pytest-cart-pricing` | 7.8 → 11.1 | 2.2 | 1.57 |
| `git-regression-hunt` | 8.5 → 11.6 | 2.0 | 1.64 |
| Tasks with little rtk activity (5 tasks) | about the same | 0–0.1 | 0.92–1.25 |

- **Bypassing the compression.** The agent repeatedly re-ran commands with `rtk bypass`, which rtk's
  own instructions suggest when compressed output is unusable. In total it did this 88 times in 80
  runs.
- **Extra turns cost more than the savings.** Each extra turn re-reads the whole cached context.
  rtk runs averaged 139K cache-read and 15K cache-write tokens, against 93K and 10K for baseline.
  That outweighs the few hundred to few thousand output tokens rtk removed.
- **One unexplained case.** On `log-link-failure` (+86%) the agent didn't use rtk at all; it used
  Read and Grep. The difference there is in which path the agent took to explore, and it's not
  attributed to rtk.

## Why caveman's pilot saving disappeared

- **The background call.** In the pilot, caveman looked 29% cheaper. Claude Code 2.1.252 makes a
  background `claude-haiku-4-5` call to generate a session title (`source=generate_session_title`,
  about 940 input and 11 output tokens, about $0.001). It skips this call whenever **any**
  `SessionStart` hook is configured.
- **How that was established.** Probe sessions showed a no-op `true` hook in project settings
  suppresses the call. An empty plugin or a `UserPromptSubmit` hook does not. caveman with its mode
  set to `off` still suppresses it, because its SessionStart hook still runs.
- **What it means for caveman.** caveman's marketplace and global installs register the same hook.
  So users do get this "saving", but it comes from Claude Code, not from caveman's compression.
- **The new control.** The `noop-hook` arm, a do-nothing SessionStart hook, had the background call
  in 0 of 80 runs; baseline, noop and rtk had it in 80 of 80. Against that control, caveman is −0%.
- **Output tokens.** caveman cut mean output by about 11% against `noop-hook` (5,185 against 5,796
  tokens). Output is only about 40% of a run's cost here, and cache reads and writes don't change,
  so the effect on the bill is lost in the noise.
- **First-session nudge fixed.** v0.2 also seeds caveman's "nudge already shown" state, so runs
  model a long-time user. In the pilot, every caveman run got a one-time statusline nudge.

## Solve rates

396 of 400 runs solved. The 4 failures:
- `caveman`: 2 on `py-cron-tz` and 1 on `git-config-forensics`
- `noop-hook`: 1 on `py-cron-tz`

That's too few to compare arms on correctness. Haiku 5.5 solved every calibration run of the new
hard tasks; even DST-aware cron scheduling was solved in 3 of 3 calibration runs. The comparison
therefore still rests on cost.

## Method notes

- **Repeats.** Chosen from the pilot's variance (`scripts/power_from_pilot.py`). A lognormal
  no-effect model predicted a noise-floor half-width of ±6% at 8 repeats. Resampling the pilot
  predicted ±12%. The observed noop interval was about ±13%, so task-level variation, not run-to-run
  noise, dominates. More tasks would narrow it more than more repeats.
- **New tasks.** 5 tasks were added with large pytest and git output:
  `py-pytest-cart-pricing`, `git-regression-hunt`, `git-config-forensics`, `py-cron-next` and
  `py-cron-tz`. Hidden cases are generated from reference implementations and cross-checked against
  independent implementations.
- **Comparisons.** Each arm is compared with baseline, paired by task, using a task-then-run
  hierarchical bootstrap (10,000 resamples). Tool arms are also compared with `noop-hook`.

## Limitations

- **Narrow setup.** One model (Haiku 5.5), one agent version, and small-to-medium synthetic tasks.
  Claude Code 2.1.252 does not recognize `claude-haiku-5-5`: it logs `unrecognized_model` and
  assumes a 200K context window. That's the same for every arm.
- **Older tool versions.** rtk v1.2.0 and caveman v4.1.0 had been out only 3 days when these runs
  were pinned, so they weren't tested.
- **API-equivalent cost.** Costs are computed from list prices and Claude Code's reported usage. Runs
  used a subscription, so nothing was billed per token.
- **Mixed confidence.** The rtk result is consistent across the tasks where rtk acts, and it agrees
  with [Quesma's analysis](https://quesma.com/blog/does-rtk-make-ai-coding-cheaper/). The caveman
  result is a null result with a CI of about ±10%.
