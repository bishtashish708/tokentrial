"""Task definitions: a starting repo, a prompt, and a hidden check."""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Task:
    id: str
    dir: Path
    prompt: str
    timeout_s: int = 900
    tags: tuple[str, ...] = ()

    @property
    def repo(self) -> Path:
        return self.dir / "repo"

    @property
    def check(self) -> Path:
        return self.dir / "check.sh"

    @property
    def solution(self) -> Path:
        return self.dir / "solution"


def load_tasks(root: Path) -> list[Task]:
    tasks = []
    for toml_path in sorted(root.glob("*/task.toml")):
        meta = tomllib.loads(toml_path.read_text())
        tasks.append(
            Task(
                id=toml_path.parent.name,
                dir=toml_path.parent.resolve(),
                prompt=meta["prompt"].strip(),
                timeout_s=int(meta.get("timeout_s", 900)),
                tags=tuple(meta.get("tags", ())),
            )
        )
    return tasks


def materialize(task: Task, dest: Path, with_solution: bool = False) -> Path:
    """Copy the starting repo (optionally with the reference fix) into `dest`."""
    shutil.copytree(task.repo, dest)
    if with_solution:
        shutil.copytree(task.solution, dest, dirs_exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=tokentrial",
            "-c",
            "user.email=tokentrial@localhost",
            "commit",
            "-q",
            "-m",
            "task start",
        ],
        cwd=dest,
        check=True,
    )
    return dest


def run_check(task: Task, workspace: Path, timeout_s: int = 300) -> bool:
    """Run the hidden check against `workspace`. True means solved."""
    env = {**os.environ, "TASK_DIR": str(task.dir)}
    try:
        proc = subprocess.run(
            ["bash", str(task.check)],
            cwd=workspace,
            env=env,
            capture_output=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return False
    return proc.returncode == 0
