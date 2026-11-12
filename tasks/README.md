# Tasks

One directory per task:

```
tasks/<id>/
  task.toml   # prompt, time and turn limits, tags
  repo/       # starting files the agent sees
  check.sh    # hidden from the agent; exit 0 = solved
  solution/   # reference fix; CI checks that check.sh passes on it and fails on repo/
```

Tasks with a `hidden_tests/` directory restore those tests before checking, so an agent
can't pass by editing or deleting tests. Exact-answer tasks check `ANSWER.txt`.

The v0.1 pilot tasks are listed in `docs/PLAN.md`. `tests/test_tasks.py` checks that every
`check.sh` fails on `repo/` and passes on `repo/` + `solution/`.
