"""Generate the hidden test data for tasks/sh-backup-rotate deterministically.

Usage: python3 scripts/make_rotate_task.py

The repo/ and solution/ files are maintained by hand. This script (re)writes the hidden
side of the task: hidden_tests/ (a copy of the visible test script, a scenario runner and
seeded random scenarios with expected results), check.sh and task.toml.

Each scenario is a directory listing (names, kinds, modification times), a config file
and an argument list. The expected exit status, stdout and remaining directory contents
are computed by two independent Python models of SPEC.md -- `model_regex` (regular
expressions, sorted() with a key) and `model_scan` (hand-written character scanning and
an insertion sort with a comparator) -- and generation aborts unless they agree.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tasks" / "sh-backup-rotate"
SEED = 31337
N_SCENARIOS = 170

# Placeholders the runner substitutes in argument lists.
DIR, CONF, NODIR, NOCONF = "{DIR}", "{CONF}", "{NODIR}", "{NOCONF}"


# ---------------------------------------------------------------- model 1: regex based


def model_regex(sc: dict) -> dict:
    args = sc["args"]
    dry = False
    config = None
    nonopts: list[str] = []
    i, done = 0, False
    usage = False
    while i < len(args):
        a = args[i]
        i += 1
        if not done:
            if a == "--dry-run":
                dry = True
                continue
            if a == "--config":
                if i >= len(args):
                    usage = True
                    break
                config = args[i]
                i += 1
                continue
            if a == "--":
                done = True
                continue
            if a.startswith("-"):
                usage = True
                break
        nonopts.append(a)
    names = sorted(e["name"] for e in sc["entries"])
    if usage or config is None or len(nonopts) != 1:
        return {"exit": 2, "stdout": "", "remaining": names}

    if config != CONF or sc["conf"] is None:
        return {"exit": 3, "stdout": "", "remaining": names}
    rules: list[tuple[str, int]] = []
    rule_re = re.compile(r"([0-9]{1,9})[ \t]+(.+)")
    for raw in sc["conf"].split("\n"):
        line = raw.strip(" \t")
        if not line or line.startswith("#"):
            continue
        m = rule_re.fullmatch(line)
        if not m:
            return {"exit": 3, "stdout": "", "remaining": names}
        prefix = m.group(2)
        if "." in prefix or "/" in prefix or prefix in [p for p, _ in rules]:
            return {"exit": 3, "stdout": "", "remaining": names}
        rules.append((prefix, int(m.group(1), 10)))

    if nonopts[0] != DIR:
        return {"exit": 4, "stdout": "", "remaining": names}

    files = [e["name"] for e in sc["entries"] if e["kind"] == "file"]
    backup_re = re.compile(r"(.*)-([0-9]{8}T[0-9]{6})")
    owned: dict[str, list[tuple[str, str]]] = {p: [] for p, _ in rules}
    for name in files:
        m = backup_re.fullmatch(name.split(".", 1)[0])
        if m and m.group(1) in owned:
            owned[m.group(1)].append((m.group(2), name))
    out = []
    kept = deleted = 0
    gone = set()
    for prefix, keep in rules:
        order = sorted(owned[prefix], key=lambda t: (t[0], t[1].encode()), reverse=True)
        kept += len(order[:keep])
        for _, name in reversed(order[keep:]):
            out.append(("would delete: " if dry else "deleted: ") + name)
            deleted += 1
            gone.add(name)
    verb = "would delete" if dry else "deleted"
    out.append(f"summary: kept {kept}, {verb} {deleted}")
    remaining = names if dry else [n for n in names if n not in gone]
    return {"exit": 0, "stdout": "\n".join(out) + "\n", "remaining": remaining}


# ---------------------------------------------------------------- model 2: scanning

DIGITS = "0123456789"


def _strip_blank(s: str) -> str:
    a, b = 0, len(s)
    while a < b and s[a] in " \t":
        a += 1
    while b > a and s[b - 1] in " \t":
        b -= 1
    return s[a:b]


def _is_ts(s: str) -> bool:
    if len(s) != 15:
        return False
    for k, c in enumerate(s):
        if k == 8:
            if c != "T":
                return False
        elif c not in DIGITS:
            return False
    return True


def _newer(a: tuple[str, str], b: tuple[str, str]) -> bool:
    """True if backup a sorts before (is newer than) backup b."""
    if a[0] != b[0]:
        return a[0] > b[0]
    return list(a[1].encode()) > list(b[1].encode())


def model_scan(sc: dict) -> dict:
    names = sorted(e["name"] for e in sc["entries"])

    def err(code: int) -> dict:
        return {"exit": code, "stdout": "", "remaining": list(names)}

    args = list(sc["args"])
    dry, config, dirs = False, None, []
    while args:
        a = args.pop(0)
        if a == "--":
            dirs.extend(args)
            break
        if a == "--dry-run":
            dry = True
        elif a == "--config":
            if not args:
                return err(2)
            config = args.pop(0)
        elif a[:1] == "-":
            return err(2)
        else:
            dirs.append(a)
    if config is None or len(dirs) != 1:
        return err(2)

    if not (config == CONF and sc["conf"] is not None):
        return err(3)
    prefixes: list[str] = []
    keeps: list[int] = []
    text = sc["conf"]
    for raw in (text[:-1] if text.endswith("\n") else text).split("\n") if text else []:
        line = _strip_blank(raw)
        if line == "" or line[0] == "#":
            continue
        cut = 0
        while cut < len(line) and line[cut] not in " \t":
            cut += 1
        keep_s, prefix = line[:cut], _strip_blank(line[cut:])
        if not (1 <= len(keep_s) <= 9) or any(c not in DIGITS for c in keep_s):
            return err(3)
        if prefix == "" or "." in prefix or "/" in prefix or prefix in prefixes:
            return err(3)
        keep = 0
        for c in keep_s:
            keep = keep * 10 + DIGITS.index(c)
        prefixes.append(prefix)
        keeps.append(keep)

    if dirs[0] != DIR:
        return err(4)

    lines = []
    kept_total = deleted_total = 0
    deleted_names = []
    for prefix, keep in zip(prefixes, keeps):
        mine: list[tuple[str, str]] = []
        for e in sc["entries"]:
            if e["kind"] != "file":
                continue
            name = e["name"]
            head = prefix + "-"
            if not name.startswith(head):
                continue
            rest = name[len(head) :]
            if _is_ts(rest[:15]) and (len(rest) == 15 or rest[15] == "."):
                mine.append((rest[:15], name))
        ordered: list[tuple[str, str]] = []
        for item in mine:  # insertion sort, newest first
            k = 0
            while k < len(ordered) and not _newer(item, ordered[k]):
                k += 1
            ordered.insert(k, item)
        doomed = ordered[keep:] if keep < len(ordered) else []
        kept_total += len(ordered) - len(doomed)
        for k in range(len(doomed) - 1, -1, -1):
            lines.append(("would delete: " if dry else "deleted: ") + doomed[k][1])
            deleted_names.append(doomed[k][1])
            deleted_total += 1
    lines.append(
        "summary: kept %d, %s %d"
        % (kept_total, "would delete" if dry else "deleted", deleted_total)
    )
    remaining = [n for n in names if dry or n not in deleted_names]
    return {"exit": 0, "stdout": "".join(l + "\n" for l in lines), "remaining": remaining}


# ---------------------------------------------------------------- scenario generation

PREFIX_POOL = [
    "db",
    "db-archive",
    "db-arch",
    "web",
    "my site",
    "app db",
    "logs",
    "x",
    "media-2",
    "media",
    "a  b",
    "nightly-db",
    "pg_main",
    "Mail",
]
RESTS = ["", ".sql", ".sql.gz", ".tar.gz", ".tgz", ".SQL", ". old", ".", ".bak copy", ".tar"]


def rand_ts(rng: random.Random, pool: list[str]) -> str:
    if pool and rng.random() < 0.15:
        return rng.choice(pool)  # same timestamp as another backup: tie-break by name
    ts = "%04d%02d%02dT%02d%02d%02d" % (
        rng.choice([2023, 2024, 2025]),
        rng.randint(1, 12),
        rng.randint(1, 31),
        rng.randint(0, 23),
        rng.randint(0, 59),
        rng.randint(0, 59),
    )
    pool.append(ts)
    return ts


def noise_names(rng: random.Random, p: str, ts: str) -> list[str]:
    return [
        f"{p}-latest.sql",
        f"{p}-{ts}x.sql",
        f"{p}_{ts}.sql",
        f"{p}-{ts[:-1]}.sql",
        f"{p}-{ts}0.sql",
        f"{p}-{ts}-partial.sql",
        f"{p}-{ts.replace('T', 't')}.sql",
        f"{p}-{ts.replace('T', '-')}.sql",
        f"{p}{ts}.sql",
        f"old {p}-{ts}.sql",
        f"{p}-{ts} .sql",
        f"{p} -{ts}.sql",
    ]


def keep_text(rng: random.Random, keep: int) -> str:
    if rng.random() < 0.12:
        return "0" * rng.randint(1, 2) + str(keep)  # leading zeros: 08, 010, 0009 ...
    return str(keep)


def gen_conf(rng: random.Random, rules: list[tuple[str, int]]) -> str:
    out = []
    if rng.random() < 0.5:
        out.append("# keep  prefix")
    for prefix, keep in rules:
        if rng.random() < 0.15:
            out.append(rng.choice(["", "   ", "\t", "  # a comment", "#3 commented-out"]))
        lead = rng.choice(["", "", "", " ", "\t", "  "])
        sep = rng.choice([" ", " ", "\t", "   ", " \t "])
        trail = rng.choice(["", "", "", " ", "\t", "  "])
        out.append(f"{lead}{keep_text(rng, keep)}{sep}{prefix}{trail}")
    text = "\n".join(out)
    if rng.random() < 0.85:
        text += "\n"
    return text


def gen_entries(rng: random.Random, rules: list[tuple[str, int]]) -> list[dict]:
    names: set[str] = set()
    entries = []

    def add(name: str, kind: str = "file") -> None:
        if name.lower() in names:  # macOS file systems are usually case-insensitive
            return
        names.add(name.lower())
        entries.append(
            {"name": name, "kind": kind, "mtime": rng.randint(1_600_000_000, 1_760_000_000)}
        )

    pool: list[str] = []
    prefixes = [p for p, _ in rules] + rng.sample(PREFIX_POOL, 2)  # some unconfigured ones too
    for p in prefixes:
        for _ in range(rng.choice([0, 1, 2, 3, 4, 5, 6, 8])):
            add(f"{p}-{rand_ts(rng, pool)}{rng.choice(RESTS)}")
        if rng.random() < 0.5:
            add(rng.choice(noise_names(rng, p, rand_ts(rng, pool))))
    for extra in ["notes.txt", "README", "rotate.log"]:
        if rng.random() < 0.3:
            add(extra)
    if rules and rng.random() < 0.3:
        p = rng.choice(rules)[0]
        add(f"{p}-{rand_ts(rng, pool)}.d", "dir")  # a directory that looks like a backup
    if rules and rng.random() < 0.3:
        p = rng.choice(rules)[0]
        add(f"{p}-{rand_ts(rng, pool)}.lnk", "symlink")  # a symlink that looks like a backup
    rng.shuffle(entries)
    return entries


def gen_args(rng: random.Random, dry: bool) -> list[str]:
    opts = [["--config", CONF]]
    if dry:
        opts.append(["--dry-run"])
        if rng.random() < 0.1:
            opts.append(["--dry-run"])
    if rng.random() < 0.1:
        opts.insert(0, ["--config", NOCONF])  # overridden by the later --config
    rng.shuffle(opts)
    if ["--config", NOCONF] in opts and opts.index(["--config", NOCONF]) > opts.index(
        ["--config", CONF]
    ):
        opts.remove(["--config", NOCONF])  # keep it only where the real --config overrides it
    flat = [a for o in opts for a in o]
    style = rng.random()
    if style < 0.6:
        return flat + [DIR]
    if style < 0.8:
        return [DIR] + flat
    return flat + ["--", DIR]


def gen_valid(rng: random.Random) -> dict:
    n_rules = rng.choice([1, 1, 2, 2, 3, 3, 4])
    picked = rng.sample(PREFIX_POOL, n_rules)
    if rng.random() < 0.35 and "db" not in picked:
        picked[0] = "db"
        if "db-archive" not in picked:
            picked.append("db-archive")
    rules = [(p, rng.choice([0, 0, 1, 1, 2, 2, 3, 3, 4, 5, 9, 12])) for p in picked]
    return {
        "args": gen_args(rng, rng.random() < 0.5),
        "conf": gen_conf(rng, rules),
        "entries": gen_entries(rng, rules),
    }


BAD_CONF_LINES = [
    "x db",
    "5",
    "  7  ",
    "-1 db",
    "3db",
    "1.5 db",
    "2 db.old",
    "2 a/b",
    "1 .hidden",
    "1234567890 db",
    "+3 db",
    "3 db.",
    "0x3 db",
]


def gen_error(rng: random.Random) -> dict:
    sc = gen_valid(rng)
    kind = rng.randrange(9)
    if kind == 0:
        sc["args"] = rng.choice([[], [DIR], ["--dry-run", DIR], ["--config", CONF]])
    elif kind == 1:
        sc["args"] = rng.choice(
            [
                [DIR, "--config"],
                ["--dry-run", DIR, "--config"],
                ["--config", CONF, DIR, DIR],
                ["--config", CONF, DIR, "--", DIR],
            ]
        )
    elif kind == 2:
        bad = rng.choice(["-n", "--keep", "--dry_run", "--config=x", "-", "--verbose", "-h"])
        args = gen_args(rng, False)
        args.insert(rng.randint(0, len(args)), bad)
        if args[args.index(bad) - 1] == "--config" or "--" in args[: args.index(bad)]:
            args = [bad] + [a for a in args if a != bad]
        sc["args"] = args
    elif kind == 3:
        sc["args"] = ["--config", NOCONF, DIR]
    elif kind == 4:
        sc["args"] = rng.choice([["--config", DIR, DIR], ["--dry-run", "--config", DIR, DIR]])
    elif kind == 5:
        lines = sc["conf"].rstrip("\n").split("\n")
        lines.insert(rng.randint(0, len(lines)), rng.choice(BAD_CONF_LINES))
        sc["conf"] = "\n".join(lines) + "\n"
    elif kind == 6:
        lines = sc["conf"].rstrip("\n").split("\n")
        rule_lines = [l for l in lines if l.strip(" \t") and not l.strip(" \t").startswith("#")]
        dup = rng.choice(rule_lines).strip(" \t").split(None, 1)[1]
        lines.append(f"{rng.randint(0, 5)}\t{dup}  ")
        sc["conf"] = "\n".join(lines) + "\n"
    elif kind == 7:
        sc["args"] = [a if a != DIR else NODIR for a in sc["args"]]
    else:
        # Both a config error and a missing directory: the config error wins.
        lines = sc["conf"].rstrip("\n").split("\n") + [rng.choice(BAD_CONF_LINES)]
        sc["conf"] = "\n".join(lines) + "\n"
        sc["args"] = [a if a != DIR else NODIR for a in sc["args"]]
    return sc


def main() -> int:
    rng = random.Random(SEED)
    scenarios = []
    exits: dict[int, int] = {}
    while len(scenarios) < N_SCENARIOS:
        sc = gen_error(rng) if rng.random() < 0.25 else gen_valid(rng)
        a, b = model_regex(sc), model_scan(sc)
        assert a == b, (len(scenarios), sc, a, b)
        sc["id"] = f"scenario-{len(scenarios):03d}"
        sc["expect"] = a
        exits[a["exit"]] = exits.get(a["exit"], 0) + 1
        scenarios.append(sc)

    hidden = ROOT / "hidden_tests"
    shutil.rmtree(hidden, ignore_errors=True)
    hidden.mkdir()
    shutil.copy(ROOT / "repo" / "tests" / "run-tests.sh", hidden / "run-tests.sh")
    (hidden / "scenarios.json").write_text(
        "[\n" + ",\n".join(json.dumps(s, separators=(",", ":")) for s in scenarios) + "\n]\n"
    )
    (hidden / "run_scenarios.py").write_text(RUNNER)
    (ROOT / "check.sh").write_text(CHECK)
    (ROOT / "check.sh").chmod(0o755)
    (ROOT / "task.toml").write_text(TASK_TOML)
    deletes = sum(
        s["expect"]["stdout"].count("delete") - 1 for s in scenarios if s["expect"]["exit"] == 0
    )
    print(
        f"{len(scenarios)} scenarios, exit codes {dict(sorted(exits.items()))}, "
        f"{deletes} deletions; both models agree"
    )
    return 0


RUNNER = r'''"""Hidden check: replay generated rotate-backups scenarios.

usage: python3 run_scenarios.py SCENARIOS_JSON SCRIPT
Runs SCRIPT with `bash` (or $ROTATE_BASH) in a fresh temporary directory per scenario.
"""

import json
import os
import subprocess
import sys
import tempfile


def main():
    scenarios = json.load(open(sys.argv[1]))
    script = os.path.abspath(sys.argv[2])
    bash = os.environ.get("ROTATE_BASH", "bash")
    failures = 0
    for sc in scenarios:
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "back ups")
            conf = os.path.join(tmp, "rotate.conf")
            os.mkdir(d)
            for e in sc["entries"]:
                path = os.path.join(d, e["name"])
                if e["kind"] == "dir":
                    os.mkdir(path)
                elif e["kind"] == "symlink":
                    target = os.path.join(tmp, "target-file")
                    open(target, "w").close()
                    os.symlink(target, path)
                else:
                    with open(path, "w") as f:
                        f.write(e["name"] + "\n")
                    os.utime(path, (e["mtime"], e["mtime"]))
            if sc["conf"] is not None:
                with open(conf, "w", newline="") as f:
                    f.write(sc["conf"])
            subst = {
                "{DIR}": d,
                "{CONF}": conf,
                "{NODIR}": os.path.join(tmp, "missing dir"),
                "{NOCONF}": os.path.join(tmp, "missing.conf"),
            }
            args = [subst.get(a, a) for a in sc["args"]]
            try:
                proc = subprocess.run(
                    [bash, script] + args, cwd=tmp, capture_output=True, timeout=30
                )
            except subprocess.TimeoutExpired:
                print(f"{sc['id']}: timeout")
                failures += 1
                continue
            got = {
                "exit": proc.returncode,
                "stdout": proc.stdout.decode("utf-8", "replace"),
                "remaining": sorted(os.listdir(d)),
            }
            if got != sc["expect"]:
                failures += 1
                print(f"{sc['id']}: args={sc['args']!r}")
                print(f"  conf={sc['conf']!r}")
                for k in ("exit", "stdout", "remaining"):
                    if got[k] != sc["expect"][k]:
                        print(f"  {k}: expected {sc['expect'][k]!r}")
                        print(f"  {k}: got      {got[k]!r}")
    print(f"{len(scenarios) - failures} of {len(scenarios)} scenarios passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
'''

CHECK = """#!/usr/bin/env bash
# Hidden check for sh-backup-rotate: restore and run the visible test script, then replay
# the generated scenarios.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
mkdir -p tests
cp "$TASK_DIR/hidden_tests/run-tests.sh" tests/run-tests.sh
bash tests/run-tests.sh >/dev/null 2>&1
python3 "$TASK_DIR/hidden_tests/run_scenarios.py" "$TASK_DIR/hidden_tests/scenarios.json" \\
    bin/rotate-backups.sh >/dev/null 2>&1
"""

TASK_TOML = '''prompt = """
bin/rotate-backups.sh keeps the newest N backups per prefix in a directory and deletes the
rest, but it has bugs and its tests fail. SPEC.md defines the required behaviour exactly,
including the output format and exit codes. Fix bin/rotate-backups.sh so that it
implements SPEC.md. It must keep working under macOS's /bin/bash 3.2 as well as bash 5.
Do not modify the tests. Run them with `bash tests/run-tests.sh`. Your fix will also be
checked against additional cases derived from SPEC.md.
"""
timeout_s = 1200
tags = ["bash", "shell", "spec", "multi-bug", "filesystem", "medium"]
'''


if __name__ == "__main__":
    sys.exit(main())
