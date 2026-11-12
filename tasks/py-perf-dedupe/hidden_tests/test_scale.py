"""Hidden check: a full nightly batch (README) must be fast and exactly right.

The batch is generated deterministically in a child process; the child is killed if it
runs too long. The expected output digest comes from scripts/make_dedupe_task.py, which
computes it with the reference solution and an independent implementation.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

N = 200_000
LIMIT_S = 10.0  # time for the dedupe() call alone
KILL_AFTER_S = 25.0  # whole child process (interpreter start + generation + dedupe)

FIRST = ["Ann", "Bob", "Cy", "Dee", "Eve", "Finn", "Gus", "Hal", "Ivy", "Jo", "Kai", "Lu"]
DOMAINS = ["gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "fastmail.com",
           "example.org", "corp.example.com", "Example.ORG"]
TAGS = ["vip", " VIP", "newsletter", "Lead ", "churned", "", "  ", "beta", "Beta"]


class Lcg:
    def __init__(self, seed):
        self.s = seed

    def __call__(self, m):
        self.s = (self.s * 6364136223846793005 + 1442695040888963407) % 2**64
        return (self.s >> 33) % m


def _spell_email(r, k):
    domain = DOMAINS[k % len(DOMAINS)]
    local = f"user{k}"
    if r(2):
        local = ".".join(local[: 1 + r(3)]) + local[1 + r(3):] if r(2) else local.capitalize()
    if r(3) == 0:
        local += f"+tag{r(4)}"
    s = f"{local}@{domain}"
    if r(4) == 0:
        s = " " + s.upper() + " "
    roll = r(60)
    if roll == 0:
        s = s.replace("@", "")
    elif roll == 1:
        s = "+x@gmail.com"
    elif roll == 2:
        s = s.replace("@", "@@")
    return s


def _spell_phone(r, p):
    a, b, c = 200 + p // 10_000_000 % 800, p // 10000 % 1000, p % 10000
    style = r(6)
    if style == 0:
        return f"({a}) {b:03d}-{c:04d}"
    if style == 1:
        return f"+1 {a} {b:03d} {c:04d}"
    if style == 2:
        return f"{a}.{b:03d}.{c:04d}"
    if style == 3:
        return f"1{a}{b:03d}{c:04d}"
    if style == 4:
        return f"{a}-{b:03d}-{c:04d} ext"
    return f"{b:03d}-{c:04d}"  # too short: invalid


def make_records(n, seed):
    r = Lcg(seed)
    pool = max(1, 2 * n // 3)
    out = []
    for i in range(n):
        email = None if r(4) == 0 else _spell_email(r, r(pool))
        phone = None if r(3) == 0 else _spell_phone(r, r(pool) * 7919)
        out.append({
            "id": f"r{i:06d}",
            "name": FIRST[r(len(FIRST))] + (" " * r(2)) if r(6) else " " * r(2),
            "email": email,
            "phone": phone,
            "updated": 1_700_000_000 + r(400),
            "tags": [TAGS[r(len(TAGS))] for _ in range(r(4))],
        })
    return out


def digest(merged):
    import hashlib

    blob = json.dumps(merged, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode()).hexdigest()


CHILD = """
import json, sys, time
sys.path.insert(0, sys.argv[1])
from test_scale import make_records, digest
from contactdedupe import dedupe
records = make_records(int(sys.argv[2]), int(sys.argv[3]))
start = time.perf_counter()
out = dedupe(records)
elapsed = time.perf_counter() - start
print(json.dumps({"elapsed": elapsed, "digest": digest(out), "clusters": len(out)}))
"""


def run_child(n, seed, timeout):
    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, "-c", CHILD, str(Path(__file__).resolve().parent), str(n), str(seed)],
        cwd=root, capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr[-2000:])
    return json.loads(proc.stdout)


class TestScale(unittest.TestCase):
    def test_nightly_batch(self):
        expected = json.loads((Path(__file__).parent / "scale_expected.json").read_text())
        try:
            result = run_child(N, expected["seed"], KILL_AFTER_S)
        except subprocess.TimeoutExpired:
            self.fail(f"batch of {N} did not finish within {KILL_AFTER_S}s")
        self.assertEqual(result["clusters"], expected["clusters"])
        self.assertEqual(result["digest"], expected["digest"])
        self.assertLess(result["elapsed"], LIMIT_S)


if __name__ == "__main__":
    unittest.main()
