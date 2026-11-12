# Courtesy issue draft for JuliusBrussee/caveman

> Draft only. Not filed. Repository: https://github.com/JuliusBrussee/caveman

## Title

Independent benchmark of caveman v4.0.1 in Claude Code, and a SessionStart side effect worth knowing about

## Body

Hi, and thanks for caveman. I've been building **TokenTrial**
(https://github.com/bishtashish708/tokentrial), an open benchmark that runs coding-agent tasks with
and without a token-saving tool and reports cost per correctly solved task. caveman v4.0.1 was one
of the first tools tested. I'm sharing the results before posting them anywhere, so you can check
the setup and push back if anything's off.

**Setup**
- Claude Code 2.1.252, headless (`claude -p`), model `claude-haiku-5-5`.
- 10 tasks × 8 repeats per arm. Answers are checked with hidden tests.
- Cost covers every API call, priced by token type.

**A Claude Code side effect you may want to know about.** In a smaller pilot, caveman looked 29%
cheaper per solved task. Most of that came from Claude Code, not from caveman's compression:
- Claude Code 2.1.252 makes a small background `claude-haiku-4-5` call to generate a session title
  (about 940 input and 11 output tokens). It **skips that call whenever any `SessionStart` hook is
  configured**.
- caveman's SessionStart hook triggers the skip. So does a project hook that only runs `true`, and
  so does caveman with its mode set to `off`.
- An empty plugin or a `UserPromptSubmit` hook does not trigger the skip.

So caveman users really do avoid that call. But any SessionStart hook would avoid it too, which is
why I compared caveman with a do-nothing SessionStart hook.

**Result**
- **−9% vs baseline (95% CI −21% to +5%), and −0% vs the do-nothing-hook control (CI −10% to
  +11%).** That's no measurable cost effect in this setup.
- Mean output fell about 11% against the control (5,185 vs 5,796 tokens).
- Output was only about 40% of a run's cost here; cache reads and writes make up most of the rest.
  So the output saving didn't show up in the total.
- Solve rate was 77/80 (2 misses on a DST-aware cron task, 1 on a git forensics task), against
  79–80/80 for the other arms. That's too few failures to read anything into.

**How caveman was set up.** Please tell me if this differs from how you'd recommend running it.
- caveman v4.0.1 at commit `d262ab3`, loaded with `--plugin-dir` and
  `CAVEMAN_DEFAULT_MODE=caveman`. It was confirmed active in 80/80 runs.
- The "nudge already shown" marker was pre-seeded, so runs model a returning user rather than a
  first session.
- caveman's state files were removed after each run.
- I didn't test a marketplace install directly, to avoid modifying my global config. It registers
  the same SessionStart hook, so I'd expect the same behavior.

**Caveats.** One model (Haiku already writes fairly concise output), one Claude Code version,
synthetic small-to-medium tasks, and a single caveman version. v4.1.0 came out shortly before the
runs were pinned and wasn't tested. Larger tasks with longer answers could well show a different
result.

**Links**
- Write-up: https://github.com/bishtashish708/tokentrial/blob/main/results/v0.2/FINDINGS.md
  (see "Why caveman's pilot saving disappeared")
- Raw records and scrubbed transcripts:
  https://github.com/bishtashish708/tokentrial/tree/main/results/v0.2/raw
- The caveman adapter: `src/tokentrial/arms.py` (`_setup_caveman`)
- Reproduce: `uv run tokentrial install-arms`, then
  `uv run tokentrial run --repeats 8 --arm baseline --arm noop-hook --arm caveman`

I'd welcome a critique of the method, or a configuration you think represents caveman better. I'll
include your response, or a rerun, in the published results. Feel free to close this if it isn't
useful here.
