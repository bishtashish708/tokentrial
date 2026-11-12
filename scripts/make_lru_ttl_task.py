"""Generate the hidden cases for tasks/js-lru-ttl-cache deterministically.

Usage: python3 scripts/make_lru_ttl_task.py   (needs node >= 20 on PATH)

repo/ (LRU cache without TTL, SPEC.md, visible tests), solution/ (reference lru.js and
memoize.js), check.sh and task.toml are hand-written files in the task directory. This
script (re)writes hidden_tests/: a copy of each visible test file, sequences.test.js and
sequences.json.

Each hidden case is a seeded random sequence of cache operations driven by a fake clock.
The expected trace (each operation's result plus the onEvict calls it caused) is computed
by a reference model of SPEC.md (`RefCache`, an OrderedDict in recency order) and
cross-checked against an independent naive model (`NaiveCache`: a plain list of entries
with "last used" counters, scanning for the minimum). The script asserts the two models
agree on every operation of every case, and finally that the reference JS solution
(solution/src/lru.js, run with node) produces the same traces.
"""

import json
import math
import random
import shutil
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tasks" / "js-lru-ttl-cache"
SEED = 6007
N_CASES = 300
INF = math.inf
VISIBLE_TESTS = ["lru.test.js", "ttl.test.js", "memoize.test.js"]


class RefCache:
    """Reference model of SPEC.md. OrderedDict order = recency, first = LRU."""

    def __init__(self, max_size, ttl):
        self.max_size, self.ttl, self.d = max_size, ttl, OrderedDict()

    def _drop(self, k, reason, ev):
        ev.append([k, self.d.pop(k)[0], reason])

    def _lookup(self, k, t, ev):
        if k not in self.d:
            return None
        if t >= self.d[k][1]:
            self._drop(k, "expired", ev)
            return None
        return self.d[k]

    def set(self, k, v, ttl, t, ev):
        life = ttl if ttl is not None else self.ttl
        exp = INF if life is None else t + life
        if k in self.d:
            if t < self.d[k][1]:
                self.d[k] = (v, exp)
                self.d.move_to_end(k)
                return None
            self._drop(k, "expired", ev)
        if len(self.d) >= self.max_size:
            for kk in [kk for kk, (_, e) in self.d.items() if t >= e]:
                self._drop(kk, "expired", ev)
            if len(self.d) >= self.max_size:
                self._drop(next(iter(self.d)), "lru", ev)
        self.d[k] = (v, exp)
        return None

    def get(self, k, t, ev):
        e = self._lookup(k, t, ev)
        if e is None:
            return None
        self.d.move_to_end(k)
        return e[0]

    def peek(self, k, t, ev):
        e = self._lookup(k, t, ev)
        return None if e is None else e[0]

    def has(self, k, t, ev):
        return self._lookup(k, t, ev) is not None

    def delete(self, k, t, ev):
        if k not in self.d:
            return False
        return t < self.d.pop(k)[1]

    def clear(self, t, ev):
        self.d.clear()

    def prune(self, t, ev):
        expired = [k for k, (_, e) in self.d.items() if t >= e]
        for k in expired:
            self._drop(k, "expired", ev)
        return len(expired)

    def size(self, t, ev):
        return sum(1 for _, e in self.d.values() if t < e)

    def keys(self, t, ev):
        return [k for k, (_, e) in reversed(self.d.items()) if t < e]

    def entries(self, t, ev):
        return [[k, v] for k, (v, e) in reversed(self.d.items()) if t < e]


class NaiveCache:
    """Independent model: unordered list of dicts; recency is a 'last used' stamp."""

    def __init__(self, max_size, ttl):
        self.max_size, self.ttl = max_size, ttl
        self.items = []  # {"k","v","dies","used"}
        self.stamp = 0

    def _touch(self, item):
        self.stamp += 1
        item["used"] = self.stamp

    def _find(self, k):
        for item in self.items:
            if item["k"] == k:
                return item
        return None

    def _alive(self, item, t):
        return item["dies"] is None or t < item["dies"]

    def _by_age(self):  # oldest use first
        return sorted(self.items, key=lambda it: it["used"])

    def _evict(self, item, reason, ev):
        self.items.remove(item)
        ev.append([item["k"], item["v"], reason])

    def _lookup(self, k, t, ev):
        item = self._find(k)
        if item is not None and not self._alive(item, t):
            self._evict(item, "expired", ev)
            return None
        return item

    def set(self, k, v, ttl, t, ev):
        use = self.ttl if ttl is None else ttl
        dies = None if use is None or use == INF else t + use
        item = self._find(k)
        if item is not None and self._alive(item, t):
            item["v"], item["dies"] = v, dies
            self._touch(item)
            return None
        if item is not None:
            self._evict(item, "expired", ev)
        if len(self.items) == self.max_size:
            for old in self._by_age():
                if not self._alive(old, t):
                    self._evict(old, "expired", ev)
        if len(self.items) == self.max_size:
            self._evict(self._by_age()[0], "lru", ev)
        new = {"k": k, "v": v, "dies": dies, "used": 0}
        self._touch(new)
        self.items.append(new)
        return None

    def get(self, k, t, ev):
        item = self._lookup(k, t, ev)
        if item is None:
            return None
        self._touch(item)
        return item["v"]

    def peek(self, k, t, ev):
        item = self._lookup(k, t, ev)
        return None if item is None else item["v"]

    def has(self, k, t, ev):
        return self._lookup(k, t, ev) is not None

    def delete(self, k, t, ev):
        item = self._find(k)
        if item is None:
            return False
        self.items.remove(item)
        return self._alive(item, t)

    def clear(self, t, ev):
        self.items = []

    def prune(self, t, ev):
        n = 0
        for item in self._by_age():
            if not self._alive(item, t):
                self._evict(item, "expired", ev)
                n += 1
        return n

    def _live_mru(self, t):
        return [it for it in reversed(self._by_age()) if self._alive(it, t)]

    def size(self, t, ev):
        return len(self._live_mru(t))

    def keys(self, t, ev):
        return [it["k"] for it in self._live_mru(t)]

    def entries(self, t, ev):
        return [[it["k"], it["v"]] for it in self._live_mru(t)]


def enc_ttl(x):
    if x is None:
        return None
    if isinstance(x, float) and math.isinf(x):
        return "Infinity"
    if isinstance(x, float) and math.isnan(x):
        return "NaN"
    return x


def random_case(rng):
    max_size = rng.randint(1, 5)
    r = rng.random()
    default_ttl = None if r < 0.3 else (INF if r < 0.4 else rng.randint(2, 20))
    keys = [chr(ord("a") + i) for i in range(max_size + rng.randint(1, 3))]
    ops = []
    value = 0
    for _ in range(rng.randint(25, 60)):
        kind = rng.choices(
            [
                "set",
                "get",
                "peek",
                "has",
                "delete",
                "size",
                "keys",
                "entries",
                "prune",
                "clear",
                "tick",
                "badset",
            ],
            [34, 20, 6, 6, 5, 6, 6, 3, 5, 1, 20, 2],
        )[0]
        if kind == "set":
            value += 1
            op = {"op": "set", "key": rng.choice(keys), "value": value}
            r = rng.random()
            if r < 0.35:
                op["ttl"] = rng.randint(1, 15)
            elif r < 0.45:
                op["ttl"] = INF
            ops.append(op)
        elif kind == "badset":
            value += 1
            ops.append(
                {
                    "op": "set",
                    "key": rng.choice(keys),
                    "value": value,
                    "ttl": rng.choice([0, -3, math.nan]),
                }
            )
        elif kind == "tick":
            ops.append({"op": "tick", "ms": rng.choice([0, 1, 1, 2, 3, 4, 5, 6, 9])})
        elif kind in ("get", "peek", "has", "delete"):
            ops.append({"op": kind, "key": rng.choice(keys)})
        else:
            ops.append({"op": kind})
    return {"maxSize": max_size, "ttl": default_ttl, "ops": ops}


def run_model(model, case):
    t = 1000
    trace = []
    for op in case["ops"]:
        ev = []
        name = op["op"]
        if name == "tick":
            t += op["ms"]
            continue
        if name == "set":
            ttl = op.get("ttl")
            if ttl is not None and (math.isnan(ttl) or not ttl > 0):
                trace.append({"result": "RangeError", "evicted": []})
                continue
            result = model.set(op["key"], op["value"], ttl, t, ev)
        elif name in ("get", "peek", "has", "delete"):
            result = getattr(model, name)(op["key"], t, ev)
        else:
            result = getattr(model, name)(t, ev)
        trace.append({"result": result, "evicted": ev})
    return trace


HIDDEN_TEST = r"""import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { LRUCache } from '../src/lru.js';

const CASES = JSON.parse(
  readFileSync(fileURLToPath(new URL('./sequences.json', import.meta.url)), 'utf8'),
);

const num = (x) => (x === 'Infinity' ? Infinity : x === 'NaN' ? NaN : x);

export function runCase(Cache, c) {
  let clock = 1000;
  let evicted = [];
  const options = { maxSize: c.maxSize, now: () => clock, onEvict: (k, v, r) => evicted.push([k, v, r]) };
  if (c.ttl !== null) options.ttl = num(c.ttl);
  const cache = new Cache(options);
  const trace = [];
  for (const op of c.ops) {
    if (op.op === 'tick') {
      clock += op.ms;
      continue;
    }
    evicted = [];
    let result;
    switch (op.op) {
      case 'set':
        try {
          if (op.ttl === undefined) cache.set(op.key, op.value);
          else cache.set(op.key, op.value, { ttl: num(op.ttl) });
          result = null;
        } catch (e) {
          result = e instanceof RangeError ? 'RangeError' : `unexpected ${e}`;
        }
        break;
      case 'get':
      case 'peek':
      case 'has':
      case 'delete':
        result = cache[op.op](op.key);
        break;
      case 'size':
        result = cache.size;
        break;
      case 'keys':
      case 'entries':
      case 'prune':
      case 'clear':
        result = cache[op.op]();
        break;
      default:
        throw new Error(`bad op ${op.op}`);
    }
    trace.push({ result: result === undefined ? null : result, evicted });
  }
  return trace;
}

for (const [i, c] of CASES.entries()) {
  test(`sequence #${i} (maxSize ${c.maxSize}, ttl ${c.ttl})`, () => {
    const got = runCase(LRUCache, c);
    for (let j = 0; j < c.expected.length; j++) {
      assert.deepEqual(got[j], c.expected[j], `operation #${j} of sequence #${i}`);
    }
    assert.equal(got.length, c.expected.length);
  });
}
"""

JS_RUNNER = r"""
import { LRUCache } from 'MODULE_URL';
const num = (x) => (x === 'Infinity' ? Infinity : x === 'NaN' ? NaN : x);
RUN_CASE
let data = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (d) => (data += d));
process.stdin.on('end', () => {
  const cases = JSON.parse(data);
  process.stdout.write(JSON.stringify(cases.map((c) => runCase(LRUCache, c))));
});
"""


def main():
    rng = random.Random(SEED)
    cases = []
    for _ in range(N_CASES):
        case = random_case(rng)
        ref = run_model(RefCache(case["maxSize"], case["ttl"]), case)
        naive = run_model(NaiveCache(case["maxSize"], case["ttl"]), case)
        assert ref == naive, (case, ref, naive)
        cases.append(
            {
                "maxSize": case["maxSize"],
                "ttl": enc_ttl(case["ttl"]),
                "ops": [
                    {**op, **({"ttl": enc_ttl(op["ttl"])} if "ttl" in op else {})}
                    for op in case["ops"]
                ],
                "expected": ref,
            }
        )

    # Third opinion: the reference JS solution must produce the same traces.
    run_case_src = HIDDEN_TEST[
        HIDDEN_TEST.index("export function runCase") : HIDDEN_TEST.index("\nfor (const")
    ]
    runner = JS_RUNNER.replace(
        "MODULE_URL", (ROOT / "solution" / "src" / "lru.js").resolve().as_uri()
    ).replace("RUN_CASE", run_case_src.replace("export ", ""))
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", runner],
        input=json.dumps([{k: c[k] for k in ("maxSize", "ttl", "ops")} for c in cases]),
        capture_output=True,
        text=True,
        check=True,
    )
    js = json.loads(proc.stdout)
    for c, got in zip(cases, js, strict=True):
        assert got == c["expected"], (c, got)

    hidden = ROOT / "hidden_tests"
    shutil.rmtree(hidden, ignore_errors=True)
    hidden.mkdir()
    for name in VISIBLE_TESTS:
        shutil.copy(ROOT / "repo" / "test" / name, hidden / name)
    (hidden / "sequences.test.js").write_text(HIDDEN_TEST)
    (hidden / "sequences.json").write_text(json.dumps(cases, separators=(",", ":")) + "\n")

    n_ops = sum(len(c["expected"]) for c in cases)
    reasons = {}
    for c in cases:
        for step in c["expected"]:
            for _, _, r in step["evicted"]:
                reasons[r] = reasons.get(r, 0) + 1
    print(
        f"{len(cases)} sequences, {n_ops} checked operations, evictions {reasons}; "
        "reference, naive model and JS solution agree"
    )


if __name__ == "__main__":
    sys.exit(main())
