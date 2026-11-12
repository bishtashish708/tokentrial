"""Hidden check: replay generated rotate-backups scenarios.

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
