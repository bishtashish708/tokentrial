"""Run the experiment matrix with checkpointing, budget caps, and resume."""

from __future__ import annotations

import json
import random
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from tokentrial.arms import setup_arm
from tokentrial.budget import Budget, BudgetExceeded
from tokentrial.claude_code import (
    AgentFatalError,
    StreamParser,
    UsageLimitReached,
    build_command,
    child_env,
    looks_like_usage_limit,
    parse_reset_epoch,
)
from tokentrial.pricing import Price, cost_breakdown
from tokentrial.tasks import Task, materialize, run_check

# Statuses that count as finished; anything else is retried on --resume.
FINAL_STATUSES = {"solved", "unsolved", "aborted_budget", "timeout"}


@dataclass
class Config:
    mode: str
    provider: str
    model: str
    arms: list[str]
    task_ids: list[str]
    repeats: int
    seed: int
    max_usd: float | None
    max_usd_per_run: float | None

    def plan(self) -> list[tuple[str, str, int]]:
        """All (task, arm, repeat) cells, interleaved in a seeded random order."""
        cells = [(t, a, r) for r in range(self.repeats) for t in self.task_ids for a in self.arms]
        random.Random(self.seed).shuffle(cells)
        return cells


def run_id(task: str, arm: str, rep: int) -> str:
    return f"{task}__{arm}__r{rep}"


@dataclass
class Checkpoint:
    """`<out>/manifest.json` (config) plus `<out>/records.jsonl` (append-only)."""

    out: Path
    records: dict[str, dict] = field(default_factory=dict)

    @property
    def manifest_path(self) -> Path:
        return self.out / "manifest.json"

    @property
    def records_path(self) -> Path:
        return self.out / "records.jsonl"

    def exists(self) -> bool:
        return self.manifest_path.exists()

    def create(self, config: Config) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "logs").mkdir(exist_ok=True)
        self.manifest_path.write_text(json.dumps(asdict(config), indent=2) + "\n")

    def load_config(self) -> Config:
        return Config(**json.loads(self.manifest_path.read_text()))

    def load_records(self) -> None:
        self.records = {}
        if self.records_path.exists():
            for line in self.records_path.read_text().splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.records[rec["run_id"]] = rec  # last record per run wins

    def completed(self) -> set[str]:
        return {rid for rid, r in self.records.items() if r["status"] in FINAL_STATUSES}

    def spent(self) -> float:
        return sum(r.get("cost_usd", {}).get("total", 0.0) for r in self.records.values())

    def append(self, record: dict) -> None:
        with self.records_path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        self.records[record["run_id"]] = record


@dataclass
class Outcome:
    finished: int = 0
    skipped: int = 0
    stopped_reason: str | None = None  # "usage_limit" | "budget" | "fatal" | None
    reset_epoch: int | None = None
    message: str | None = None


def run_experiment(
    config: Config,
    tasks: dict[str, Task],
    price: Price,
    ckpt: Checkpoint,
    claude_bin: list[str],
    log=print,
) -> Outcome:
    ckpt.load_records()
    done = ckpt.completed()
    budget = Budget(config.max_usd, config.max_usd_per_run, spent_total=ckpt.spent())
    outcome = Outcome()
    cells = config.plan()

    for i, (task_id, arm, rep) in enumerate(cells, 1):
        rid = run_id(task_id, arm, rep)
        if rid in done:
            outcome.skipped += 1
            continue
        log(f"[{i}/{len(cells)}] {rid} (spent so far ${budget.spent_total:.4f})")
        try:
            record = _run_one(config, tasks[task_id], arm, rep, price, ckpt, claude_bin, budget)
        except UsageLimitReached as e:
            outcome.stopped_reason, outcome.reset_epoch = "usage_limit", e.reset_epoch
            log(f"usage limit reached: {e}")
            return outcome
        except AgentFatalError as e:
            outcome.stopped_reason, outcome.message = "fatal", str(e)
            log(f"fatal agent error: {e}")
            return outcome
        ckpt.append(record)
        outcome.finished += 1
        log(f"    -> {record['status']}  ${record['cost_usd']['total']:.4f}")
        if record.get("stop_experiment"):
            outcome.stopped_reason = "budget"
            return outcome
    return outcome


def _run_one(
    config: Config,
    task: Task,
    arm: str,
    rep: int,
    price: Price,
    ckpt: Checkpoint,
    claude_bin: list[str],
    budget: Budget,
) -> dict:
    rid = run_id(task.id, arm, rep)
    started = datetime.now(UTC).isoformat()
    t0 = time.monotonic()
    budget.start_run()
    parser = StreamParser(price)
    status, error, stop_experiment = None, None, False

    tmp = Path(tempfile.mkdtemp(prefix=f"tokentrial-{rid}-"))
    workspace = tmp / "ws"
    try:
        materialize(task, workspace)
        setup_arm(arm, workspace)
        proc = subprocess.Popen(
            build_command(claude_bin, config.model),
            cwd=workspace,
            env=child_env(config.mode),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        timed_out = threading.Event()

        def _on_timeout() -> None:
            timed_out.set()
            proc.kill()

        timer = threading.Timer(task.timeout_s, _on_timeout)
        timer.start()
        try:
            proc.stdin.write(task.prompt)
            proc.stdin.close()
            with (ckpt.out / "logs" / f"{rid}.jsonl").open("w") as raw_log:
                for line in proc.stdout:
                    raw_log.write(line)
                    try:
                        budget.charge(parser.feed(line))
                    except BudgetExceeded as e:
                        proc.kill()
                        status, error = "aborted_budget", str(e)
                        stop_experiment = "--max-usd " in str(e)
                        break
            proc.wait()
            stderr = proc.stderr.read()
        finally:
            timer.cancel()
            if proc.poll() is None:
                proc.kill()

        if status is None:
            result = parser.state.result
            if result is None and looks_like_usage_limit(stderr):
                raise UsageLimitReached(stderr.strip()[:300], parse_reset_epoch(stderr))
            if result is None and timed_out.is_set():
                status, error = "timeout", f"killed after {task.timeout_s}s"
            elif result is None:
                status, error = "error", (stderr.strip() or "no result event")[:500]
            elif result.get("is_error") and result.get("terminal_reason") == "api_error":
                # The API call failed (not the agent): retry this run on --resume.
                status = "error"
                error = str(result.get("result") or "api_error")[:500]
            else:
                status = "solved" if run_check(task, workspace) else "unsolved"
                if result.get("is_error"):
                    error = str(result.get("result") or result.get("subtype"))[:500]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    usage = parser.state.usage
    result = parser.state.result or {}
    return {
        "run_id": rid,
        "task": task.id,
        "arm": arm,
        "repeat": rep,
        "status": status,
        "solved": status == "solved",
        "error": error,
        "mode": config.mode,
        "model": config.model,
        "usage": asdict(usage),
        "cost_usd": cost_breakdown(usage, price),
        "cost_basis": "api_equivalent" if config.mode == "subscription" else "api_billed",
        "num_api_calls": len(parser.state.calls),
        "num_turns": result.get("num_turns"),
        "reported_cost_usd": result.get("total_cost_usd"),
        "duration_s": round(time.monotonic() - t0, 2),
        "started_at": started,
        "claude_init": parser.state.init,
        "stop_experiment": stop_experiment,
    }
