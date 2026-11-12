# r/LocalLLaMA draft (short)

> Draft only. Not posted. This sub focuses on local models. Frame the post around method and the
> general lesson, and check its rules on posts about closed models first.

## Title

Do token-compression tools actually save money for coding agents? A 400-run controlled test says "not necessarily"

## Body

I built a small open benchmark, **TokenTrial**. It runs coding-agent tasks with and without a
token-saving tool, grades each answer with a hidden test, and reports cost per *solved* task with
bootstrap confidence intervals. The first run used Claude Code with Haiku 5.5. The method is
agent-agnostic, and I'd like to add open-model agents next.

Results:
- **Output compression can raise cost.** rtk (compresses shell output) raised cost per solved task
  by 36% (95% CI +17% to +53%). The agent re-ran commands to see what was cut and took more turns.
  With prompt caching, every extra turn re-reads the whole context.
- **Check for side effects.** caveman (terse answers) looked 29% cheaper. That turned out to come
  from the agent skipping a background call whenever a session hook exists. Against a do-nothing
  hook, the effect was about zero.
- **Noise is large.** A do-nothing arm alone moved cost by 11%.

Caveats: one model, synthetic tasks, pinned tool versions.

Repo, with method and raw data: https://github.com/bishtashish708/tokentrial

Suggestions for open-model agents and runners to support are welcome.
