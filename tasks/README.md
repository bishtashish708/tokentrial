# Tasks

One directory per task:

```
tasks/<id>/
  task.toml   # prompt, time and turn limits, tags
  repo/       # starting files the agent sees
  check.sh    # hidden from the agent; exit 0 = solved
  solution/   # reference fix; CI checks that check.sh passes on it and fails on repo/
```

Tasks are added in v0.1 week 1 (see `docs/PLAN.md`).
