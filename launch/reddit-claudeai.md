# r/ClaudeAI draft

> Draft only. Not posted. Check the subreddit's self-promotion rules and post flair first.

## Title

I benchmarked rtk and caveman in Claude Code over 400 runs. rtk raised cost per solved task 36%; caveman's saving came from a Claude Code side effect.

## Body

I wanted to know whether token-saving add-ons actually lower what Claude Code costs, so I built
**TokenTrial**, a small open benchmark. It runs the same tasks with and without each tool, grades
each answer with a hidden test, and reports **dollars per correctly solved task**. Each run is
priced on all four token types, not only the tokens the tool compresses.

**Setup:**
- Claude Code 2.1.252 running headless, on Haiku 5.5
- 10 tasks × 5 arms × 8 repeats = 400 runs
- About $2.87 API-equivalent, run on a Pro/Max subscription

| Arm | Solved | Cost per solved task vs baseline (95% CI) |
|---|---|---|
| noop (does nothing) | 80/80 | +11% (−2% to +24%) |
| noop-hook (empty SessionStart hook) | 79/80 | −9% (−24% to +7%) |
| **rtk v1.1.0** | 80/80 | **+36% (+17% to +53%)** |
| caveman v4.0.1 | 77/80 | −9% (−21% to +5%); −0% vs noop-hook |

**rtk.** It did compress pytest and git output. But where it compressed the most, Claude re-ran the
commands with `rtk bypass` to see what was cut (88 times across 80 runs) and took more turns. On the
DST cron task, turns went from 8.2 to 13.4. Each turn re-reads the whole cached context, so the
extra turns cost more than the trimmed output saved.

**caveman, and something worth knowing about Claude Code.**
- Claude Code makes a small background Haiku 4.5 call in each session to generate a title.
- If *any* SessionStart hook is configured, it skips that call. A hook that just runs `true` is
  enough.
- caveman uses a SessionStart hook, which is why it looked 29% cheaper in my pilot.
- Compared with an empty hook, caveman's cost effect is about zero. It did cut output tokens by
  about 11%, but output is only about 40% of the cost in these runs.

**General lesson:** a do-nothing arm moved cost by 11%. Most of the bill is cache reads and writes,
so anything that adds turns tends to cost more than it saves.

**Caveats:**
- One model and one Claude Code version.
- Synthetic small-to-medium tasks; Haiku solved nearly everything.
- Pinned tool versions (newer releases weren't tested).
- Large real repos may behave differently.

The tool authors haven't reviewed this yet, and corrections are welcome.

- Repo, with full method and raw data: https://github.com/bishtashish708/tokentrial
- Leaderboard: https://bishtashish708.github.io/tokentrial/

You can rerun it on your own subscription with `uv run tokentrial install-arms` and then
`uv run tokentrial run`. It pauses on usage limits and resumes with `--resume`.
