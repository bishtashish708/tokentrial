"""Generate the git-history tasks deterministically (fixed authors and dates).

Usage: python3 scripts/make_git_tasks.py

Builds each task's repository history with plain git, ships it as history.bundle,
and writes the expected answer into check.sh and solution/.
"""

import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

TASKS = Path(__file__).resolve().parent.parent / "tasks"
AUTHORS = [
    ("Dana Reyes", "dana@example.com"),
    ("Kofi Mensah", "kofi@example.com"),
    ("Lin Wei", "lin@example.com"),
    ("Priya Nair", "priya@example.com"),
]


class Repo:
    def __init__(self, path: Path, seed: int):
        self.path, self.rng, self.n = path, random.Random(seed), 0
        self.git("init", "-q", "-b", "main")

    def git(self, *args, env=None):
        return subprocess.run(
            ["git", *args], cwd=self.path, check=True, capture_output=True, text=True, env=env
        ).stdout.strip()

    def write(self, rel, text):
        p = self.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, message, author=None):
        self.n += 1
        name, email = author or self.rng.choice(AUTHORS)
        date = f"2026-0{1 + self.n // 40}-{1 + self.n % 28:02d}T{9 + self.n % 8:02d}:{self.n % 60:02d}:00Z"
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_DATE": date,
        }
        self.git("add", "-A")
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", message, env=env)
        return self.git("rev-parse", "HEAD")

    def tag(self, name):
        self.git("tag", name)

    def bundle(self, dest: Path):
        self.git("bundle", "create", str(dest), "--all")


FILLER_TOPICS = ["logging", "metrics", "docs", "ci", "typing", "examples", "errors", "config"]


def filler(repo: Repo, i: int, pkg: str):
    topic = repo.rng.choice(FILLER_TOPICS)
    if topic == "docs":
        repo.write("CHANGES.md", (repo.path / "CHANGES.md").read_text() + f"- note {i}\n")
        return repo.commit(f"docs: changelog entry {i}")
    lines = "\n".join(f"    {topic}_{i}_{k} = {repo.rng.randint(1, 999)}" for k in range(6))
    repo.write(
        f"{pkg}/{topic}.py",
        f'"""{topic} helpers (rev {i})."""\n\n\nclass {topic.title()}:\n{lines}\n',
    )
    verbs = ["tidy", "rework", "simplify", "extend", "document", "harden"]
    body = "\n".join(
        f"- {repo.rng.choice(verbs)} {topic} item {k}" for k in range(repo.rng.randint(1, 5))
    )
    return repo.commit(f"{topic}: {repo.rng.choice(verbs)} helpers\n\n{body}")


# --- Task: git-regression-hunt ----------------------------------------------------

BUCKET_GOOD = '''"""Token bucket rate limiter."""

import time


class TokenBucket:
    """Allows `rate` tokens per second, bursting up to `capacity`."""

    def __init__(self, rate: float, capacity: float, clock=time.monotonic):
        if rate <= 0 or capacity <= 0:
            raise ValueError("rate and capacity must be positive")
        self.rate = rate
        self.capacity = capacity
        self.clock = clock
        self.tokens = capacity
        self.updated = clock()

    def _refill(self) -> None:
        now = self.clock()
        elapsed = max(0.0, now - self.updated)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.updated = now

    def try_acquire(self, n: float = 1) -> bool:
        self._refill()
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False

    def wait_time(self, n: float = 1) -> float:
        """Seconds until `n` tokens are available (0 if available now)."""
        self._refill()
        missing = n - self.tokens
        return 0.0 if missing <= 0 else missing / self.rate
'''

# The regression: refill credits whole seconds only (int truncation), hidden in a
# "tidy" refactor that also renames things.
BUCKET_BAD = BUCKET_GOOD.replace(
    "        elapsed = max(0.0, now - self.updated)\n        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)",
    "        elapsed = max(0, int(now - self.updated))\n        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)",
).replace('"""Token bucket rate limiter."""', '"""Token bucket rate limiter (internals tidied)."""')
assert BUCKET_BAD != BUCKET_GOOD

BUCKET_TESTS = """import pytest

from ratekit.bucket import TokenBucket


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return FakeClock()


def test_starts_full(clock):
    b = TokenBucket(rate=2, capacity=5, clock=clock)
    assert all(b.try_acquire() for _ in range(5))
    assert not b.try_acquire()


def test_refill_whole_seconds(clock):
    b = TokenBucket(rate=2, capacity=5, clock=clock)
    for _ in range(5):
        b.try_acquire()
    clock.t += 1
    assert b.try_acquire() and b.try_acquire() and not b.try_acquire()


def test_refill_partial_seconds(clock):
    b = TokenBucket(rate=4, capacity=4, clock=clock)
    for _ in range(4):
        b.try_acquire()
    clock.t += 0.5
    assert b.try_acquire() and b.try_acquire() and not b.try_acquire()


def test_wait_time(clock):
    b = TokenBucket(rate=10, capacity=1, clock=clock)
    b.try_acquire()
    assert b.wait_time() == pytest.approx(0.1)
    clock.t += 0.05
    assert b.wait_time() == pytest.approx(0.05)


def test_capacity_cap(clock):
    b = TokenBucket(rate=100, capacity=3, clock=clock)
    clock.t += 60
    assert sum(b.try_acquire() for _ in range(10)) == 3


@pytest.mark.parametrize("rate,capacity", [(0, 1), (1, 0), (-1, 5)])
def test_rejects_bad_args(rate, capacity):
    with pytest.raises(ValueError):
        TokenBucket(rate, capacity)
"""


def make_regression_task():
    root = TASKS / "git-regression-hunt"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        r = Repo(Path(tmp), seed=7)
        r.write("README.md", "# ratekit\n\nRate limiting primitives.\n")
        r.write("CHANGES.md", "# Changes\n\n")
        r.write("ratekit/__init__.py", '"""ratekit."""\n')
        r.write(
            "ratekit/bucket.py",
            BUCKET_GOOD.replace(
                "        missing = n - self.tokens\n        return 0.0 if missing <= 0 else missing / self.rate\n",
                "        return max(0.0, (n - self.tokens) / self.rate)\n",
            ),
        )
        r.write("tests/test_bucket.py", BUCKET_TESTS.split("def test_refill_partial_seconds")[0])
        r.commit("Initial token bucket")
        for i in range(1, 28):
            filler(r, i, "ratekit")
        r.write("ratekit/bucket.py", BUCKET_GOOD)
        r.commit("bucket: clearer wait_time\n\nAvoid negative intermediate values.")
        r.write("tests/test_bucket.py", BUCKET_TESTS)
        r.commit("tests: cover partial-second refill and wait_time")
        for i in range(28, 44):
            filler(r, i, "ratekit")
        r.write("ratekit/bucket.py", BUCKET_BAD)
        r.write(
            "ratekit/clocks.py",
            '"""Clock helpers."""\n\nimport time\n\n\ndef monotonic():\n    return time.monotonic()\n',
        )
        bad = r.commit(
            "refactor: tidy bucket internals\n\n- move clock helpers to ratekit/clocks.py\n- simplify refill bookkeeping\n- docstring touch-ups"
        )
        for i in range(44, 62):
            filler(r, i, "ratekit")
            if i == 50:
                r.write(
                    "ratekit/bucket.py",
                    (r.path / "ratekit/bucket.py")
                    .read_text()
                    .replace(
                        '"""Allows `rate` tokens per second, bursting up to `capacity`."""',
                        '"""Allows `rate` tokens per second, bursting up to `capacity` tokens."""',
                    ),
                )
                r.commit("bucket: docstring wording")
        r.bundle(root / "history.bundle")
    (root / "solution").mkdir()
    (root / "solution" / "ANSWER.txt").write_text(bad + "\n")
    (root / "solution" / "ratekit").mkdir()
    (root / "solution" / "ratekit" / "bucket.py").write_text(
        BUCKET_GOOD.replace(
            '"""Allows `rate` tokens per second, bursting up to `capacity`."""',
            '"""Allows `rate` tokens per second, bursting up to `capacity` tokens."""',
        )
    )
    (root / "hidden_tests").mkdir()
    (root / "hidden_tests" / "test_bucket.py").write_text(BUCKET_TESTS)
    (root / "check.sh").write_text(f"""#!/usr/bin/env bash
# Hidden check for git-regression-hunt: the culprit commit's SHA, and a working fix.
set -euo pipefail
: "${{TASK_DIR:?TASK_DIR must point at the task directory}}"
[ -f ANSWER.txt ] || exit 1
got=$(tr -d '[:space:]`' < ANSWER.txt)
expected={bad}
[ ${{#got}} -ge 7 ] && [ "${{expected#"$got"}}" != "$expected" ] || exit 1
mkdir -p tests && cp "$TASK_DIR/hidden_tests/test_bucket.py" tests/test_bucket.py
python3 -m pytest -q -p no:cacheprovider tests >/dev/null 2>&1
""")
    (root / "check.sh").chmod(0o755)
    (root / "task.toml").write_text('''prompt = """
This repository's history is in git. `tests/test_bucket.py` passed at some point in the past,
but now fails. Run the tests with `python3 -m pytest tests`.

1. Find the commit that introduced the regression, and write its full commit SHA to a file
   named ANSWER.txt in the repository root (the SHA only).
2. Fix the bug in the current code so the tests pass. Do not modify the tests.
"""
timeout_s = 1200
history = "history.bundle"
requires = ["pytest"]
tags = ["git", "pytest", "regression-hunt", "large-git-output"]
''')
    return bad


# --- Task: git-config-forensics ---------------------------------------------------

DEFAULTS = '''"""Default client settings."""

TIMEOUT_S = 30
MAX_RETRIES = {retries}
BACKOFF_BASE_S = 0.5
USER_AGENT = "fetchkit/{ver}"
'''


def make_forensics_task():
    root = TASKS / "git-config-forensics"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        r = Repo(Path(tmp), seed=11)
        r.write("README.md", "# fetchkit\n\nHTTP fetching with retries. Default retries: 5.\n")
        r.write("CHANGES.md", "# Changes\n\n")
        r.write("fetchkit/__init__.py", '"""fetchkit."""\n')
        r.write("fetchkit/defaults.py", DEFAULTS.format(retries=5, ver="1.0"))
        r.commit("Initial import")
        r.tag("v1.0")
        culprit = None
        for i in range(1, 80):
            if i == 18:
                # Decoy: message claims the change, but only the README changes.
                r.write(
                    "README.md", "# fetchkit\n\nHTTP fetching with retries. Default retries: 3.\n"
                )
                r.commit(
                    "Reduce default retries to 3\n\nUpdate the docs to match the planned default."
                )
            elif i == 41:
                # The real change, buried in a consolidation commit.
                r.write("fetchkit/defaults.py", DEFAULTS.format(retries=3, ver="1.3"))
                r.write(
                    "fetchkit/session.py",
                    '"""Session wiring."""\n\nfrom fetchkit import defaults\n\nRETRIES = defaults.MAX_RETRIES\n',
                )
                culprit = r.commit(
                    "Consolidate defaults\n\n- move session constants next to defaults\n- bump user agent"
                )
            elif i == 52:
                # A later revert-looking commit that touches the same line's neighbours only.
                r.write(
                    "fetchkit/defaults.py",
                    DEFAULTS.format(retries=3, ver="1.4").replace(
                        "TIMEOUT_S = 30", "TIMEOUT_S = 20"
                    ),
                )
                r.commit("Retry tuning\n\nShorter timeout so retries finish sooner.")
            else:
                filler(r, i, "fetchkit")
            if i in (12, 30, 40, 55, 70):
                r.tag({12: "v1.1", 30: "v1.2", 40: "v1.3", 55: "v1.4", 70: "v1.5"}[i])
        r.bundle(root / "history.bundle")
    answer = f"{culprit} v1.4"
    (root / "solution").mkdir()
    (root / "solution" / "ANSWER.txt").write_text(answer + "\n")
    (root / "check.sh").write_text(f"""#!/usr/bin/env bash
# Hidden check for git-config-forensics: "<sha> <tag>", sha may be abbreviated (>= 7).
set -euo pipefail
[ -f ANSWER.txt ] || exit 1
read -r sha tag rest < <(tr -d '`' < ANSWER.txt; echo) || true
expected={culprit}
[ -n "${{sha:-}}" ] && [ ${{#sha}} -ge 7 ] && [ "${{expected#"$sha"}}" != "$expected" ] || exit 1
[ "${{tag:-}}" = "v1.4" ]
""")
    (root / "check.sh").chmod(0o755)
    (root / "task.toml").write_text('''prompt = """
This is the git repository of `fetchkit`. At some point the default value of `MAX_RETRIES` in
the code was changed from 5 to 3. Find the commit that changed it in the code, and the first
release tag that shipped the change.

Write the answer to a file named ANSWER.txt in the repository root, as
`<commit sha> <tag>` on one line (for example `0123abc v9.9`), and nothing else.
Do not modify any other files.
"""
timeout_s = 900
history = "history.bundle"
tags = ["git", "exact-answer", "large-git-output"]
''')
    return answer


if __name__ == "__main__":
    print("git-regression-hunt culprit:", make_regression_task())
    print("git-config-forensics answer:", make_forensics_task())
