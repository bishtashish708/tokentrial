# X / LinkedIn thread draft

> Draft only. Not posted. Each post is at most 280 characters, for X. For LinkedIn, join them into
> one post and drop the numbering.

**1/**
Do token-saving tools for coding agents actually save money?

I ran 400 controlled Claude Code runs (Haiku 5.5, 10 tasks, 8 repeats) and measured $ per *correctly
solved* task, counting every token type.

Short answer: not in this setup. 🧵

**2/**
rtk v1.1.0 raised cost per solved task by 36% (95% CI +17% to +53%).

It did compress pytest/git output. But the agent re-ran commands with `rtk bypass` to see what was
cut, and took more turns. Each turn re-reads the cached context.

**3/**
caveman v4.0.1 looked 29% cheaper in my pilot.

That came from Claude Code: it skips a background title-generation call whenever *any*
SessionStart hook exists. caveman has one. Against a do-nothing hook, caveman's effect was −0%
(±10%).

**4/**
Two general lessons:
• A do-nothing arm moved cost by +11%. Small before/after tests mostly measure noise.
• Most of an agent's bill is cache reads and writes. Anything that adds turns tends to cost more
  than it saves.

**5/**
Caveats: one model, one Claude Code version, synthetic tasks, pinned tool versions. Real large repos
may differ. Corrections welcome.

It's open source, with raw data, and costs about $3 API-equivalent to rerun on a subscription:
https://github.com/bishtashish708/tokentrial
