"""A moderate-size batch must be deduplicated quickly.

The work runs in a child process so that a slow implementation is killed instead of
hanging the test run.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

N = 20_000
LIMIT_S = 5.0
KILL_AFTER_S = 10.0

FIRST = ["Ann", "Bob", "Cy", "Dee", "Eve", "Finn", "Gus", "Hal", "Ivy", "Jo"]
DOMAINS = ["gmail.com", "googlemail.com", "outlook.com", "example.org", "corp.example.com"]
TAGS = ["vip", " VIP", "newsletter", "Lead ", "churned", ""]


class Lcg:
    def __init__(self, seed):
        self.s = seed

    def __call__(self, m):
        self.s = (self.s * 6364136223846793005 + 1442695040888963407) % 2**64
        return (self.s >> 33) % m


def make_records(n, seed):
    r = Lcg(seed)
    pool = max(1, 2 * n // 3)
    out = []
    for i in range(n):
        k = r(pool)
        email = None if r(4) == 0 else f"User.{k}+x{r(3)}@{DOMAINS[k % len(DOMAINS)]}"
        p = r(pool)
        phone = None if r(3) == 0 else f"+1 (555) {p // 10000:03d}-{p % 10000:04d}"
        out.append({
            "id": f"c{i}",
            "name": FIRST[r(len(FIRST))] if r(5) else " ",
            "email": email,
            "phone": phone,
            "updated": 1_700_000_000 + r(500),
            "tags": [TAGS[r(len(TAGS))] for _ in range(r(3))],
        })
    return out


CHILD = """
import json, sys, time
sys.path.insert(0, sys.argv[1])
from test_performance import make_records
from contactdedupe import dedupe
records = make_records(int(sys.argv[2]), 7)
start = time.perf_counter()
out = dedupe(records)
elapsed = time.perf_counter() - start
print(json.dumps({"elapsed": elapsed, "clusters": len(out),
                  "members": sum(1 + len(m["merged_ids"]) for m in out)}))
"""


class TestPerformance(unittest.TestCase):
    def test_moderate_batch(self):
        root = Path(__file__).resolve().parent.parent
        try:
            proc = subprocess.run(
                [sys.executable, "-c", CHILD, str(Path(__file__).resolve().parent), str(N)],
                cwd=root, capture_output=True, text=True, timeout=KILL_AFTER_S,
            )
        except subprocess.TimeoutExpired:
            self.fail(f"dedupe of {N} records did not finish within {KILL_AFTER_S}s")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["members"], N)
        self.assertLess(result["clusters"], N)
        self.assertLess(result["elapsed"], LIMIT_S, f"took {result['elapsed']:.2f}s")


if __name__ == "__main__":
    unittest.main()
