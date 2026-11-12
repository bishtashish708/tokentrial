import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / "data"


def run(*args, cwd=ROOT):
    """Run `python3 -m lockscan ARGS`; returns (exit status, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, "-m", "lockscan", *map(str, args)],
        cwd=cwd, capture_output=True, text=True, timeout=60,
    )
    return proc.returncode, proc.stdout, proc.stderr
