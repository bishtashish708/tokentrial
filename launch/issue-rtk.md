# Courtesy issue draft for rtk-ai/rtk

> Draft only. Not filed. Repository: https://github.com/rtk-ai/rtk

## Title

Independent benchmark of rtk v1.1.0 in Claude Code: sharing results and inviting review

## Body

Hi, and thanks for rtk. I've been building **TokenTrial**
(https://github.com/bishtashish708/tokentrial), an open benchmark that runs coding-agent tasks with
and without a token-saving tool and reports cost per correctly solved task. rtk v1.1.0 was one of
the first tools tested. The results and raw data are public in the repo, but I'm sharing them with you before announcing them anywhere, so you can check the
setup and push back if I've configured something wrong.

**Setup**
- Claude Code 2.1.252, headless (`claude -p`), model `claude-haiku-5-5`.
- 10 tasks × 8 repeats per arm. Answers are checked with hidden tests.
- Cost covers every API call, priced by token type (input, cache write, cache read, output).
- Five arms: baseline, two do-nothing controls, rtk and caveman.

**Result.** rtk's cost per solved task was **+36% vs baseline (95% CI +17% to +53%)**. Against a
control that adds a do-nothing hook, it was +49%. All 80 rtk runs solved their task.

**Where the cost came from.** rtk worked as intended:
- The hook fired in 73 of 80 runs; the other 7 made no Bash calls.
- It rewrote `pytest` and `git log/show/diff`.
- `rtk gain` reported 30–4,500 tokens saved per run.

But on the tasks where it compressed the most, the agent often re-ran the command with
`rtk bypass` (88 times across 80 runs; 4.9 per run on average on `py-cron-tz`), and took more turns:

| Task | Turns, baseline → rtk | Bypasses per run | Cost ratio |
|---|---|---|---|
| py-cron-tz | 8.2 → 13.4 | 4.9 | 1.37 |
| py-cron-next | 6.0 → 9.6 | 1.8 | 1.47 |
| py-pytest-cart-pricing | 7.8 → 11.1 | 2.2 | 1.57 |
| git-regression-hunt | 8.5 → 11.6 | 2.0 | 1.64 |

With prompt caching, each extra turn re-reads the cached context. That cost more than the trimmed
output saved. My reading is that the compressed pytest failure output sometimes left out details the
model wanted, such as full assertion diffs, so it fetched them again. That's an interpretation, not
something I've proven. The transcripts are in the raw data if you want to check.

**How rtk was set up.** Please tell me if any of this differs from the recommended setup.
- rtk v1.1.0, `rtk-aarch64-apple-darwin.tar.gz`, verified against the release `checksums.txt`.
- I ran `rtk init -g` in a throwaway HOME, then copied the generated `PreToolUse`/`Bash` hook entry
  (`rtk hook claude`) into the task workspace's `.claude/settings.json`. I also inlined `RTK.md`
  into the workspace `CLAUDE.md`. This avoids touching the user's global config.
- `RTK_TELEMETRY_DISABLED=1`. rtk's state directory was reset before each run.
- The task repos are small, so the agent may not see output as large as in the cases rtk is built
  for.

**Caveats.** One model, one Claude Code version, synthetic small-to-medium tasks, and a single rtk
version. v1.2.0 came out shortly before the runs were pinned and wasn't tested. I'd like to rerun on
the latest release.

**Links**
- Leaderboard: https://bishtashish708.github.io/tokentrial/
- Write-up: https://github.com/bishtashish708/tokentrial/blob/main/results/v0.2/FINDINGS.md
- Per-run raw records and agent transcripts (scrubbed):
  https://github.com/bishtashish708/tokentrial/tree/main/results/v0.2/raw
- The rtk adapter: `src/tokentrial/arms.py` (`_setup_rtk`)
- Reproduce: `uv run tokentrial install-arms`, then
  `uv run tokentrial run --repeats 8 --arm baseline --arm noop-hook --arm rtk`

I'd welcome a critique of the method, or a suggested configuration you think is fairer. I'll
include your response, or a rerun, in the published results. Feel free to close this if it isn't
useful here.
