"""Generate the hidden data of tasks/py-perf-dedupe deterministically.

Usage: python3 scripts/make_dedupe_task.py

repo/ and solution/ are hand-written. This script writes
  hidden_tests/cases.json           seeded small/medium cases with expected outputs
  hidden_tests/scale_expected.json  digest of the 200k-record batch in hidden_tests/test_scale.py
and copies the visible tests into hidden_tests/.

Expected outputs come from the ORIGINAL quadratic implementation in repo/ (small cases) and
from the reference solution (large batch); every case is cross-checked against an
independent implementation below (regex/partition-based normalization, BFS over an
inverted index, separate merge code), and the script asserts they all agree.
"""

import importlib
import json
import random
import re
import shutil
import sys
import tempfile
import time
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tasks" / "py-perf-dedupe"
HIDDEN = ROOT / "hidden_tests"
SCALE_SEED = 20261112

# ---------------------------------------------------------------- independent version

_EMAIL_RE = re.compile(r"^([^@]+)@([^@]+)\Z")


def ind_email(raw):
    if raw is None:
        return None
    m = _EMAIL_RE.match(raw.strip().lower())
    if not m:
        return None
    local, domain = m.group(1), m.group(2)
    domain = {"googlemail.com": "gmail.com"}.get(domain, domain)
    if domain in ("gmail.com", "outlook.com", "hotmail.com", "fastmail.com"):
        local, _, _ = local.partition("+")
        if domain == "gmail.com":
            local = "".join(ch for ch in local if ch != ".")
    return f"{local}@{domain}" if local else None


def ind_phone(raw):
    if raw is None:
        return None
    d = re.sub(r"[^0-9]", "", raw, flags=re.ASCII)
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    return d if len(d) == 10 else None


def ind_dedupe(records):
    n = len(records)
    emails = [ind_email(r["email"]) for r in records]
    phones = [ind_phone(r["phone"]) for r in records]
    by_key = defaultdict(list)
    for i in range(n):
        if emails[i] is not None:
            by_key[("e", emails[i])].append(i)
        if phones[i] is not None:
            by_key[("p", phones[i])].append(i)
    keys_of = [[] for _ in range(n)]
    for key, members in by_key.items():
        for i in members:
            keys_of[i].append(key)
    comp = [-1] * n
    comps = []
    for start in range(n):
        if comp[start] != -1:
            continue
        cid = len(comps)
        comp[start] = cid
        members = [start]
        queue = deque([start])
        seen_keys = set()
        while queue:
            i = queue.popleft()
            for key in keys_of[i]:
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                for j in by_key[key]:
                    if comp[j] == -1:
                        comp[j] = cid
                        members.append(j)
                        queue.append(j)
        comps.append(sorted(members))
    out = []
    for members in comps:  # BFS starts at increasing positions -> already in output order
        best = members[0]
        for p in members[1:]:
            if records[p]["updated"] > records[best]["updated"]:
                best = p
        order = [best] + sorted(
            (p for p in members if p != best),
            key=lambda p: (records[p]["updated"] * -1, p),
        )
        name = next((records[p]["name"].strip() for p in order if records[p]["name"].strip()), "")
        email = next((emails[p] for p in order if emails[p] is not None), None)
        phone = next((phones[p] for p in order if phones[p] is not None), None)
        tags = sorted({t.strip().lower() for p in members for t in records[p]["tags"]} - {""})
        out.append(
            {
                "id": records[best]["id"],
                "name": name,
                "email": email,
                "phone": phone,
                "updated": records[best]["updated"],
                "tags": tags,
                "merged_ids": [records[p]["id"] for p in members if p != best],
            }
        )
    return out


# ---------------------------------------------------------------- loading repo / solution


def load_dedupe(with_solution):
    for name in list(sys.modules):
        if name == "contactdedupe" or name.startswith("contactdedupe."):
            del sys.modules[name]
    tmp = Path(tempfile.mkdtemp(prefix="dedupe-"))
    shutil.copytree(ROOT / "repo", tmp / "ws")
    if with_solution:
        shutil.copytree(ROOT / "solution", tmp / "ws", dirs_exist_ok=True)
    sys.path.insert(0, str(tmp / "ws"))
    try:
        mod = importlib.import_module("contactdedupe")
        return mod.dedupe
    finally:
        sys.path.pop(0)


# ---------------------------------------------------------------- random cases

DOMAINS = [
    "gmail.com",
    "googlemail.com",
    "GMail.com",
    "outlook.com",
    "hotmail.com",
    "fastmail.com",
    "example.com",
    "Example.com",
    "mail.example.net",
]
TAGS = ["vip", "VIP ", " vip", "lead", "Lead", "", " ", "beta", "b", "a", "Z", "z"]
NAMES = ["Ann", "ann ", "", "  ", "Bo", "Cy Young", " Dee"]


def rand_email(rng, k):
    if rng.random() < 0.06:
        return rng.choice(
            [
                "",
                "   ",
                "@x.com",
                "x@",
                "a@@b.com",
                "noat",
                "+t@gmail.com",
                "..@googlemail.com",
                "+@outlook.com",
                ".@example.com",
            ]
        )
    local = f"u{k}"
    if rng.random() < 0.3:
        local = local[0] + "." + local[1:]
    if rng.random() < 0.3:
        local += "+" + rng.choice(["", "a", "b.c", "x+y"])
    if rng.random() < 0.2:
        local = local.upper()
    s = f"{local}@{rng.choice(DOMAINS[: 3 + k % 7])}"
    if rng.random() < 0.2:
        s = "  " + s + "\t"
    return s


def rand_phone(rng, k):
    if rng.random() < 0.08:
        return rng.choice(
            [
                "",
                "12345",
                "2-555-123-4567",
                "+44 20 7946 0958",
                "555-1234",
                "1-800-FLOWERS",
                "１２３４５６７８９０",
            ]
        )
    digits = f"{555_000_0000 + k * 37:010d}"[-10:]
    style = rng.randrange(5)
    if style == 0:
        return digits
    if style == 1:
        return "1" + digits
    if style == 2:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if style == 3:
        return f"+1 {digits[:3]}.{digits[3:6]}.{digits[6:]}"
    return f" {digits[:3]} {digits[3:]} "


def rand_case(rng, n):
    pool = max(1, int(n * rng.choice([0.2, 0.5, 1.0, 2.0])))
    records = []
    for i in range(n):
        records.append(
            {
                "id": f"{rng.choice('abcxyz')}{i}",
                "name": rng.choice(NAMES),
                "email": None if rng.random() < 0.3 else rand_email(rng, rng.randrange(pool)),
                "phone": None if rng.random() < 0.35 else rand_phone(rng, rng.randrange(pool)),
                "updated": rng.randrange(5) if rng.random() < 0.5 else rng.randrange(1000),
                "tags": [rng.choice(TAGS) for _ in range(rng.randrange(4))],
            }
        )
    return records


def main():
    original = load_dedupe(with_solution=False)
    reference = load_dedupe(with_solution=True)
    assert original is not reference

    rng = random.Random(4242)
    sizes = (
        [0, 1, 2, 3]
        + [rng.randrange(2, 40) for _ in range(120)]
        + [rng.randrange(40, 200) for _ in range(30)]
        + [400, 600]
    )
    cases = []
    for n in sizes:
        records = rand_case(rng, n)
        expected = original(records)
        assert reference(records) == expected, n
        assert ind_dedupe(records) == expected, n
        cases.append({"input": records, "expected": expected})
    merged = sum(1 for c in cases for m in c["expected"] if m["merged_ids"])
    chains = sum(1 for c in cases for m in c["expected"] if len(m["merged_ids"]) >= 3)
    print(f"{len(cases)} cases, {merged} merged clusters, {chains} with >= 4 members")

    sys.path.insert(0, str(HIDDEN))
    import test_scale  # noqa: E402

    sys.path.pop(0)
    # family check: the large-batch generator, small enough for the quadratic original
    sample = test_scale.make_records(2500, SCALE_SEED)
    assert original(sample) == reference(sample) == ind_dedupe(sample)

    big = test_scale.make_records(test_scale.N, SCALE_SEED)
    t = time.perf_counter()
    ref_out = reference(big)
    elapsed = time.perf_counter() - t
    assert ref_out == ind_dedupe(big)
    print(f"scale: {len(big)} records -> {len(ref_out)} clusters, reference {elapsed:.2f}s")

    (HIDDEN / "cases.json").write_text(json.dumps(cases, ensure_ascii=True) + "\n")
    (HIDDEN / "scale_expected.json").write_text(
        json.dumps(
            {
                "seed": SCALE_SEED,
                "clusters": len(ref_out),
                "digest": test_scale.digest(ref_out),
            },
            indent=2,
        )
        + "\n"
    )
    for f in (ROOT / "repo" / "tests").glob("test_*.py"):
        shutil.copy(f, HIDDEN / f.name)


if __name__ == "__main__":
    main()
