"""Generate the hidden cases of tasks/py-cli-json-output deterministically.

Usage: python3 scripts/make_lockscan_task.py

repo/ and solution/ are hand-written. This script generates seeded random lockfiles and
writes hidden_tests/cases.json with, per lockfile, a list of invocations and their expected
results:

* text invocations (every subcommand): expected output is captured from the ORIGINAL
  repo/ (before the feature) and asserted identical for repo/+solution/, so the hidden
  tests pin the text output byte for byte;
* JSON invocations: expected documents are computed by an independent implementation
  below, straight from the generator's own data (structured requirements, a hand-written
  license table), never through lockscan's code; the script asserts the reference
  solution produces exactly the same documents and exit statuses.

It also copies the visible tests and fixtures into hidden_tests/ (flat).
"""

import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tasks" / "py-cli-json-output"
HIDDEN = ROOT / "hidden_tests"

NAMES = [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "eps-ilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
    "Nu",
    "nu",
    "xi",
    "omicron",
    "pi_two",
    "rho.three",
]
GHOSTS = ["ghost", "phantom", "Zeta"]  # never locked -> "missing"

# (raw license or None for "no key", normalized, category); independent of lockscan code
LICENSES = [
    (None, None, "unknown"),
    ("", None, "unknown"),
    ("   ", None, "unknown"),
    ("MIT", "MIT", "permissive"),
    (" mit ", "MIT", "permissive"),
    ("MIT License", "MIT", "permissive"),
    ("Apache 2.0", "Apache-2.0", "permissive"),
    ("apache-2.0", "Apache-2.0", "permissive"),
    ("Apache Software License", "Apache-2.0", "permissive"),
    ("BSD", "BSD-3-Clause", "permissive"),
    ("Simplified BSD", "BSD-2-Clause", "permissive"),
    ("bsd-2-clause", "BSD-2-Clause", "permissive"),
    ("ISC", "ISC", "permissive"),
    ("Python Software Foundation License", "PSF-2.0", "permissive"),
    ("unlicense", "Unlicense", "permissive"),
    ("GPLv2", "GPL-2.0", "copyleft"),
    ("GPL-3.0", "GPL-3.0", "copyleft"),
    ("lgpl-2.1", "LGPL-2.1", "copyleft"),
    ("LGPLv3", "LGPL-3.0", "copyleft"),
    ("AGPL-3.0", "AGPL-3.0", "copyleft"),
    ("Mozilla Public License 2.0", "MPL-2.0", "copyleft"),
    ("Proprietary", "Proprietary", "unknown"),
    ("  Custom EULA ", "Custom EULA", "unknown"),
    ("GPL", "GPL", "unknown"),
    ("WTFPL", "WTFPL", "unknown"),
]
OPS = ["==", "!=", ">=", "<=", ">", "<"]


def vkey(text):
    parts = [int(p) for p in text.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def allows(version, constraints):
    v = vkey(version)
    for op, bound in constraints:
        b = vkey(bound)
        ok = {"==": v == b, "!=": v != b, ">=": v >= b, "<=": v <= b, ">": v > b, "<": v < b}[op]
        if not ok:
            return False
    return True


# ---------------------------------------------------------------- random lockfiles


def rand_version(rng):
    form = rng.randrange(6)
    if form == 0:
        return f"{rng.randrange(3)}.{rng.choice([0, 1, 2, 9, 10, 11])}"
    if form == 1:
        return str(rng.randrange(1, 12))
    return f"{rng.randrange(3)}.{rng.choice([0, 1, 2, 9, 10, 11, 12])}.{rng.randrange(12)}"


def rand_requirement(rng, name, locked_versions):
    constraints = []
    for _ in range(rng.choice([0, 0, 1, 1, 2])):
        pool = locked_versions + [rand_version(rng)]
        constraints.append((rng.choice(OPS), rng.choice(pool)))
    text = name
    if constraints:
        sep = rng.choice(["", " "])
        items = [f"{op}{sep}{v}" if rng.random() < 0.7 else f"{op} {v}" for op, v in constraints]
        text += rng.choice(["", " "]) + rng.choice([",", ", ", " ,"]).join(items)
    raw = rng.choice(["", " ", "  "]) + text + rng.choice(["", " "])
    return {"raw": raw, "text": raw.strip(), "name": name, "constraints": constraints}


def rand_lockfile(rng):
    names = rng.sample(NAMES, rng.randrange(2, 10))
    packages = []
    for name in names:
        n_versions = 1 if rng.random() < 0.75 else rng.randrange(2, 4)
        keys, versions = set(), []
        while len(versions) < n_versions:
            v = rand_version(rng)
            if vkey(v) not in keys:
                keys.add(vkey(v))
                versions.append(v)
        for v in versions:
            lic = rng.choice(LICENSES)
            packages.append(
                {
                    "name": name,
                    "version": v,
                    "license": lic,
                    "source": rng.choice([None, None, "registry", "git", "path"]),
                    "deps": [],
                }
            )
    rng.shuffle(packages)
    locked = {}
    for p in packages:
        locked.setdefault(p["name"], []).append(p["version"])

    def pick_dep_names(k, exclude=None):
        pool = [n for n in names if n != exclude] + (GHOSTS if rng.random() < 0.4 else [])
        return rng.sample(pool, min(k, len(pool)))

    for p in packages:
        for dep in pick_dep_names(rng.choice([0, 0, 1, 1, 2, 3]), exclude=p["name"]):
            p["deps"].append(rand_requirement(rng, dep, locked.get(dep, [])))
    project = None
    if rng.random() < 0.8:
        project = {"name": rng.choice(["app", "shop-api", "zz-service", "Alpha"]), "deps": []}
        for dep in pick_dep_names(rng.randrange(0, 4)):
            project["deps"].append(rand_requirement(rng, dep, locked.get(dep, [])))
    return {"project": project, "packages": packages}


def to_toml(lock):
    q = json.dumps
    out = ["version = 1", ""]
    if lock["project"] is not None:
        pr = lock["project"]
        out += [
            "[project]",
            f"name = {q(pr['name'])}",
            "dependencies = [" + ", ".join(q(d["raw"]) for d in pr["deps"]) + "]",
            "",
        ]
    for p in lock["packages"]:
        out += ["[[package]]", f"name = {q(p['name'])}", f"version = {q(p['version'])}"]
        if p["source"] is not None:
            out.append(f"source = {q(p['source'])}")
        if p["license"][0] is not None:
            out.append(f"license = {q(p['license'][0])}")
        if p["deps"] or rand_flag(p):
            out.append("dependencies = [" + ", ".join(q(d["raw"]) for d in p["deps"]) + "]")
        out.append("")
    return "\n".join(out)


def rand_flag(p):
    return len(p["name"]) % 2 == 0  # sometimes write an explicit empty list


# ---------------------------------------------------------------- independent reference


def null_first(v):
    return (0, "") if v is None else (1, v)


def expected_licenses(lock, only_direct, fail_on):
    direct = {d["name"] for d in lock["project"]["deps"]} if lock["project"] else set()
    pkgs = [p for p in lock["packages"] if not only_direct or p["name"] in direct]
    pkgs.sort(key=lambda p: (p["name"], vkey(p["version"])))
    counts = {"permissive": 0, "copyleft": 0, "unknown": 0}
    entries = []
    for p in pkgs:
        _, norm, cat = p["license"]
        counts[cat] += 1
        entries.append(
            {
                "name": p["name"],
                "version": p["version"],
                "license": norm,
                "category": cat,
                "direct": p["name"] in direct,
            }
        )
    failed = fail_on is not None and counts[fail_on] > 0
    return (1 if failed else 0), {"packages": entries, "counts": counts, "failed": failed}


def expected_check(lock, strict):
    by_name = {}
    for p in lock["packages"]:
        by_name.setdefault(p["name"], []).append(p["version"])

    def ordered(versions):
        return sorted(versions, key=vkey)

    issues = []
    requirers = []
    if lock["project"] is not None:
        requirers.append((lock["project"]["name"], None, lock["project"]["deps"]))
    requirers += [(p["name"], p["version"], p["deps"]) for p in lock["packages"]]
    for who, ver, deps in requirers:
        for d in deps:
            base = {
                "package": who,
                "version": ver,
                "dependency": d["name"],
                "requirement": d["text"],
            }
            vs = by_name.get(d["name"], [])
            if not vs:
                issues.append({"kind": "missing", "severity": "error", **base, "found": []})
            elif not any(allows(v, d["constraints"]) for v in vs):
                issues.append(
                    {"kind": "unsatisfied", "severity": "error", **base, "found": ordered(vs)}
                )
    for name, vs in by_name.items():
        if len(vs) > 1:
            issues.append(
                {
                    "kind": "duplicate",
                    "severity": "warning",
                    "package": name,
                    "version": None,
                    "dependency": None,
                    "requirement": None,
                    "found": ordered(vs),
                }
            )
    if lock["project"] is not None:
        reach, frontier = set(), [d["name"] for d in lock["project"]["deps"]]
        while frontier:
            name = frontier.pop()
            if name in reach:
                continue
            reach.add(name)
            for p in lock["packages"]:
                if p["name"] == name:
                    frontier += [d["name"] for d in p["deps"]]
        for p in lock["packages"]:
            if p["name"] not in reach:
                issues.append(
                    {
                        "kind": "orphan",
                        "severity": "warning",
                        "package": p["name"],
                        "version": p["version"],
                        "dependency": None,
                        "requirement": None,
                        "found": None,
                    }
                )
    issues.sort(
        key=lambda i: (
            i["kind"],
            i["package"],
            null_first(i["version"]),
            null_first(i["dependency"]),
            null_first(i["requirement"]),
        )
    )
    errors = sum(i["severity"] == "error" for i in issues)
    warnings = len(issues) - errors
    code = 1 if errors or (strict and warnings) else 0
    return code, {
        "ok": code == 0,
        "counts": {"errors": errors, "warnings": warnings},
        "issues": issues,
    }


# ---------------------------------------------------------------- running the tool


def workspace(with_solution):
    tmp = Path(tempfile.mkdtemp(prefix="lockscan-"))
    shutil.copytree(ROOT / "repo", tmp / "ws")
    if with_solution:
        shutil.copytree(ROOT / "solution", tmp / "ws", dirs_exist_ok=True)
    return tmp / "ws"


def run(ws, lockpath, args):
    proc = subprocess.run(
        [sys.executable, "-m", "lockscan", "-f", str(lockpath), *args],
        cwd=ws,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode, proc.stdout, proc.stderr


TEXT_ARGS = [
    ["summary"],
    ["tree"],
    ["tree", "--depth", "2"],
    ["licenses"],
    ["licenses", "--only-direct"],
    ["licenses", "--fail-on", "copyleft"],
    ["licenses", "--only-direct", "--fail-on", "unknown"],
    ["check"],
    ["check", "--strict"],
]


def main():
    original, solved = workspace(False), workspace(True)
    rng = random.Random(1337)
    tmpdir = Path(tempfile.mkdtemp(prefix="lockscan-cases-"))
    cases = []
    stats = {
        "issues": 0,
        "unsatisfied": 0,
        "missing": 0,
        "duplicate": 0,
        "orphan": 0,
        "null_license": 0,
        "failed": 0,
    }
    for k in range(70):
        lock = rand_lockfile(rng)
        toml_text = to_toml(lock)
        path = tmpdir / f"case{k}.lock"
        path.write_text(toml_text)
        runs = []
        text_args = list(TEXT_ARGS)
        text_args.append(["why", rng.choice([p["name"] for p in lock["packages"]])])
        for args in text_args:
            if lock["project"] is None and args[0] == "tree":
                continue
            expected = run(original, path, args)
            assert run(solved, path, args) == expected, (k, args)
            assert (
                run(solved, path, args + ["--format", "text"]) == expected
                if args[0] in ("licenses", "check")
                else True
            )
            runs.append(
                {"args": args, "code": expected[0], "stdout": expected[1], "stderr": expected[2]}
            )
        json_variants = [
            (["licenses"], expected_licenses(lock, False, None)),
            (["licenses", "--only-direct"], expected_licenses(lock, True, None)),
            (["licenses", "--fail-on", "copyleft"], expected_licenses(lock, False, "copyleft")),
            (
                ["licenses", "--fail-on", "unknown", "--only-direct"],
                expected_licenses(lock, True, "unknown"),
            ),
            (["check"], expected_check(lock, False)),
            (["check", "--strict"], expected_check(lock, True)),
        ]
        for args, (code, doc) in json_variants:
            args = args + ["--format", "json"]
            got_code, out, err = run(solved, path, args)
            assert err == "" and got_code == code and json.loads(out) == doc, (k, args, out)
            runs.append({"args": args, "code": code, "json": doc})
        cases.append({"lockfile": toml_text, "runs": runs})
        doc = expected_check(lock, False)[1]
        stats["issues"] += len(doc["issues"])
        for i in doc["issues"]:
            stats[i["kind"]] += 1
        stats["null_license"] += sum(p["license"][1] is None for p in lock["packages"])
        stats["failed"] += expected_licenses(lock, False, "copyleft")[1]["failed"]
    print(f"{len(cases)} lockfiles, {sum(len(c['runs']) for c in cases)} invocations; {stats}")

    HIDDEN.mkdir(exist_ok=True)
    (HIDDEN / "cases.json").write_text(json.dumps(cases, indent=1) + "\n")
    for f in (ROOT / "repo" / "tests").glob("*.py"):
        shutil.copy(f, HIDDEN / f.name)
    for f in (ROOT / "repo" / "tests" / "data").glob("*.lock"):
        shutil.copy(f, HIDDEN / f.name)


if __name__ == "__main__":
    main()
