"""Choose repeats from pilot variance.

Simulates experiments of T tasks x R repeats by resampling the pilot's runs
(per task and arm, with replacement; pilot tasks reused to reach T), runs the
report's bootstrap on each, and reports the mean half-width of the 95% CI of
the noop-vs-baseline relative difference (the noise floor).

Usage: uv run python scripts/power_from_pilot.py results/pilot-v0.1/raw/records.jsonl
"""

import json
import random
import statistics
import sys
from collections import defaultdict

from tokentrial.report import summarize


def main(path, tasks=10, sims=12, boots=800):
    recs = [json.loads(line) for line in open(path)]
    pool = defaultdict(list)
    for r in recs:
        if r["arm"] in ("baseline", "noop"):
            pool[(r["task"], r["arm"])].append(r)
    base_tasks = sorted({t for t, _ in pool})
    rng = random.Random(0)
    print(f"pilot: {len(base_tasks)} tasks; simulating {tasks} tasks")
    for reps in (3, 5, 6, 8, 10, 12):
        widths = []
        for _ in range(sims):
            sim = []
            for i in range(tasks):
                src = base_tasks[i % len(base_tasks)]
                for arm in ("baseline", "noop"):
                    for k in range(reps):
                        r = dict(rng.choice(pool[(src, arm)]))
                        r["task"], r["run_id"] = f"t{i}", f"t{i}__{arm}__r{k}"
                        sim.append(r)
            s = summarize(sim, n_boot=boots, seed=rng.randint(0, 10**6))
            lo, hi = s["arms"]["noop"]["vs_baseline"]["ci95"]
            widths.append((hi - lo) / 2)
        print(
            f"reps={reps:2d}: noise-floor CI half-width ~ ±{statistics.mean(widths) * 100:.1f}%"
            f"  (runs per arm = {tasks * reps})"
        )


if __name__ == "__main__" and len(sys.argv) == 2:
    main(sys.argv[1])


def parametric(path, tasks=10, sims=40, boots=800):
    """No-true-effect simulation: run cost = task mean x lognormal(within-task sigma)."""
    import math

    recs = [json.loads(line) for line in open(path)]
    groups = defaultdict(list)
    for r in recs:
        groups[(r["task"], r["arm"])].append(math.log(r["cost_usd"]["total"]))
    resid = [x - statistics.mean(v) for v in groups.values() for x in v]
    n_groups = len(groups)
    sigma = math.sqrt(sum(e * e for e in resid) / (len(resid) - n_groups))
    task_means = defaultdict(list)
    for r in recs:
        task_means[r["task"]].append(r["cost_usd"]["total"])
    means = [statistics.mean(v) for v in task_means.values()]
    print(f"\nparametric: pooled within-task sigma of log cost = {sigma:.3f}")
    rng = random.Random(1)
    template = {
        "status": "solved",
        "solved": True,
        "num_turns": 1,
        "duration_s": 1,
        "usage": dict.fromkeys(
            ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output"), 0
        ),
    }
    for reps in (3, 5, 8, 10, 12, 15, 20):
        widths = []
        for _ in range(sims):
            sim = []
            for i in range(tasks):
                mu = means[i % len(means)]
                for arm in ("baseline", "noop"):
                    for k in range(reps):
                        c = mu * math.exp(rng.gauss(0, sigma) - sigma**2 / 2)
                        cost = dict.fromkeys(template["usage"], 0.0) | {"output": c, "total": c}
                        sim.append(
                            template
                            | {
                                "arm": arm,
                                "task": f"t{i}",
                                "run_id": f"t{i}{arm}{k}",
                                "cost_usd": cost,
                                "cost_main_usd": c,
                            }
                        )
            s = summarize(sim, n_boot=boots, seed=rng.randint(0, 10**6))
            lo, hi = s["arms"]["noop"]["vs_baseline"]["ci95"]
            widths.append((hi - lo) / 2)
        print(f"reps={reps:2d}: ±{statistics.mean(widths) * 100:.1f}%")
    return sigma


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[2] == "--parametric":
    parametric(sys.argv[1])
