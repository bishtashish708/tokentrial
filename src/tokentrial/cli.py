"""Command-line entry point: `tokentrial run`, `tokentrial report`, `tokentrial doctor`."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from tokentrial import __version__, tools
from tokentrial.arms import ARMS, PILOT_ARMS, unavailable_arms
from tokentrial.claude_code import API_CREDENTIAL_VARS, auth_status
from tokentrial.pricing import load_prices
from tokentrial.runner import Checkpoint, Config, run_experiment
from tokentrial.tasks import load_tasks

app = typer.Typer(
    help="Measure whether token-saving tools reduce cost per correctly solved task.",
    no_args_is_help=True,
)

EXIT_NOT_READY = 2
EXIT_USAGE_LIMIT = 3
EXIT_BUDGET = 4
EXIT_FATAL = 5


class Mode(StrEnum):
    subscription = "subscription"
    api = "api"


def _version(value: bool) -> None:
    if value:
        typer.echo(f"tokentrial {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version.")
    ] = False,
) -> None:
    pass


def _claude_bin(value: str) -> list[str]:
    return shlex.split(value)


def _preflight(mode: Mode, claude_bin: list[str]) -> list[str]:
    """Problems that would stop a real run, as human-readable strings."""
    if not shutil.which(claude_bin[0]):
        return [f"`{claude_bin[0]}` not found on PATH. Install Claude Code first."]
    problems = []
    status = auth_status(claude_bin, mode.value)
    if mode is Mode.subscription:
        if not status.get("loggedIn"):
            problems.append("Claude Code is not logged in. Run: claude auth login")
        elif status.get("authMethod") != "claude.ai":
            problems.append(
                f"Claude Code auth method is {status.get('authMethod')!r}, not a claude.ai "
                "subscription. Run: claude auth login"
            )
    elif not os.environ.get("ANTHROPIC_API_KEY"):
        problems.append("--mode api needs ANTHROPIC_API_KEY in the environment.")
    return problems


@app.command()
def doctor(
    mode: Annotated[Mode, typer.Option(help="Mode to check.")] = Mode.subscription,
    claude_bin: Annotated[str, typer.Option(help="Claude Code command.", hidden=True)] = "claude",
) -> None:
    """Check that Claude Code is installed and logged in. Makes no model calls."""
    cmd = _claude_bin(claude_bin)
    if shutil.which(cmd[0]):
        ver = subprocess.run([*cmd, "--version"], capture_output=True, text=True).stdout.strip()
        typer.echo(f"claude: {ver}")
        status = auth_status(cmd, mode.value)
        typer.echo(
            f"auth: loggedIn={status.get('loggedIn')} method={status.get('authMethod')} "
            f"plan={status.get('subscriptionType')}"
        )
    if mode is Mode.subscription and any(os.environ.get(v) for v in API_CREDENTIAL_VARS):
        typer.echo(
            "note: ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN is set; it will be removed from "
            "the agent's environment so runs use the subscription."
        )
    problems = _preflight(mode, cmd)
    for p in problems:
        typer.echo(f"problem: {p}", err=True)
    if problems:
        raise typer.Exit(code=EXIT_NOT_READY)
    typer.echo(f"ready for --mode {mode.value}")


MODELS_FILE = "models.json"


def _experiments(out: Path) -> list[Path]:
    """Experiment directories under --out: itself, or one per model (see models.json)."""
    if Checkpoint(out).exists():
        return [out]
    listing = out / MODELS_FILE
    if listing.exists():
        return [out / m for m in json.loads(listing.read_text())]
    return []


@app.command()
def run(
    arms: Annotated[
        list[str] | None, typer.Option("--arm", "-a", help="Arm to run (repeatable).")
    ] = None,
    tasks_dir: Annotated[Path, typer.Option("--tasks", help="Task directory.")] = Path("tasks"),
    task_ids: Annotated[
        list[str] | None, typer.Option("--task", "-t", help="Only these task IDs (repeatable).")
    ] = None,
    mode: Annotated[
        Mode,
        typer.Option(
            help="subscription: logged-in Claude Code, API-equivalent cost (default). "
            "api: bill ANTHROPIC_API_KEY."
        ),
    ] = Mode.subscription,
    provider: Annotated[str, typer.Option(help="Price table: anthropic | bedrock")] = "anthropic",
    models: Annotated[
        list[str] | None,
        typer.Option(
            "--model",
            help="Model ID priced in pricing.toml (repeatable; default claude-haiku-5-5). "
            "With several models each gets its own experiment in --out/<model>/, run in "
            "the order given; caps apply per model.",
        ),
    ] = None,
    repeats: Annotated[int, typer.Option(min=1, help="Runs per (task, arm) pair.")] = 3,
    seed: Annotated[int, typer.Option(help="Seed for the interleaved run order.")] = 0,
    max_usd: Annotated[
        float | None,
        typer.Option(min=0, help="Stop the experiment once total cost exceeds this."),
    ] = 30.0,
    max_usd_per_run: Annotated[
        float | None,
        typer.Option(min=0, help="Abort a single agent run once its cost exceeds this."),
    ] = 1.0,
    pause_at_utilization: Annotated[
        float | None,
        typer.Option(
            min=0,
            max=1,
            help="Pause (exit 3, resumable) once Claude Code reports the subscription's "
            "five-hour window at or above this fraction, e.g. 0.7. Leaves room for other "
            "work on the same account.",
        ),
    ] = None,
    out: Annotated[Path, typer.Option(help="Experiment directory.")] = Path("runs/pilot"),
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Continue the experiment in --out, skipping finished runs."),
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print the plan and exit.")] = False,
    claude_bin: Annotated[str, typer.Option(help="Claude Code command.", hidden=True)] = "claude",
) -> None:
    """Run every task under every arm and record token usage and correctness."""
    if resume:
        dirs = _experiments(out)
        if not dirs:
            raise typer.BadParameter(f"nothing to resume in {out}/", param_hint="--out")
        typer.echo(f"resuming {out}/ with its saved configuration (other options ignored)")
        plans = [(d, Checkpoint(d).load_config()) for d in dirs]
        if pause_at_utilization is not None:
            for _, c in plans:
                c.pause_at_utilization = pause_at_utilization
            typer.echo(f"pause threshold for this session: {pause_at_utilization:.0%}")
    else:
        all_tasks = [t.id for t in load_tasks(tasks_dir)] if tasks_dir.is_dir() else []
        selected_tasks = list(task_ids) if task_ids else all_tasks
        unknown_tasks = sorted(set(selected_tasks) - set(all_tasks))
        if unknown_tasks:
            raise typer.BadParameter(f"unknown task(s): {', '.join(unknown_tasks)}")
        model_list = list(dict.fromkeys(models or ["claude-haiku-5-5"]))
        plans = [
            (
                out if len(model_list) == 1 else out / m,
                Config(
                    mode=mode.value,
                    provider=provider,
                    model=m,
                    arms=list(arms or PILOT_ARMS),
                    task_ids=selected_tasks,
                    repeats=repeats,
                    seed=seed,
                    max_usd=max_usd,
                    max_usd_per_run=max_usd_per_run,
                    pause_at_utilization=pause_at_utilization,
                ),
            )
            for m in model_list
        ]
        if not dry_run:
            existing = [d for d, _ in plans if Checkpoint(d).exists()]
            if existing or (out / MODELS_FILE).exists():
                typer.echo(
                    f"{out}/ already has an experiment. Use --resume to continue it, "
                    "or choose a new --out.",
                    err=True,
                )
                raise typer.Exit(code=EXIT_NOT_READY)

    prices = load_prices()
    for _, config in plans:
        _validate(config, prices)
    for d, config in plans:
        _describe(d, config, prices)
    not_ready = unavailable_arms(sorted({a for _, c in plans for a in c.arms}))
    for arm_name, reason in not_ready.items():
        typer.echo(f"warning: arm {arm_name}: {reason}")
    if dry_run:
        return

    n_total = sum(len(c.task_ids) * len(c.arms) * c.repeats for _, c in plans)
    if n_total == 0:
        typer.echo("No runs planned (no tasks found).", err=True)
        raise typer.Exit(code=EXIT_NOT_READY)
    if not_ready:
        typer.echo(
            "Some arms cannot run yet (see warnings). Install them with "
            "`tokentrial install-arms`, or pick others with --arm.",
            err=True,
        )
        raise typer.Exit(code=EXIT_NOT_READY)
    tasks = {t.id: t for t in load_tasks(tasks_dir)}
    unready = sorted({t for _, c in plans for t in c.task_ids if not tasks[t].ready})
    if unready:
        typer.echo(
            f"Task(s) {', '.join(unready)} need tools that are not installed "
            "(run `tokentrial install-arms`).",
            err=True,
        )
        raise typer.Exit(code=EXIT_NOT_READY)
    cmd = _claude_bin(claude_bin)
    problems = _preflight(Mode(plans[0][1].mode), cmd)
    if problems:
        for p in problems:
            typer.echo(f"problem: {p}", err=True)
        raise typer.Exit(code=EXIT_NOT_READY)

    if not resume:
        if len(plans) > 1:
            out.mkdir(parents=True, exist_ok=True)
            (out / MODELS_FILE).write_text(json.dumps([c.model for _, c in plans]) + "\n")
        for d, config in plans:
            Checkpoint(d).create(config)

    for d, config in plans:
        if len(plans) > 1:
            typer.echo(f"== {config.model} ({d}/)")
        _run_and_report(d, config, prices, tasks, cmd, resume_hint=out)


def _price_key(config: Config) -> tuple[str, str]:
    return (
        config.provider,
        config.model if config.provider == "anthropic" else f"anthropic.{config.model}",
    )


def _validate(config: Config, prices: dict) -> None:
    unknown = [a for a in config.arms if a not in ARMS]
    if unknown:
        raise typer.BadParameter(f"unknown arm(s): {', '.join(unknown)}", param_hint="--arm")
    if config.mode == Mode.subscription and config.provider != "anthropic":
        raise typer.BadParameter("subscription mode is priced against the anthropic table")
    key = _price_key(config)
    if key not in prices:
        raise typer.BadParameter(f"no price for {key[0]}/{key[1]}")


def _describe(d: Path, config: Config, prices: dict) -> None:
    key = _price_key(config)
    cost_label = "API-equivalent cost" if config.mode == Mode.subscription else "billed cost"
    n_runs = len(config.task_ids) * len(config.arms) * config.repeats
    typer.echo(
        f"[{d}] mode={config.mode} provider={config.provider} model={config.model} "
        f"repeats={config.repeats}"
    )
    typer.echo(f"arms: {', '.join(config.arms)}")
    typer.echo(f"tasks: {', '.join(config.task_ids) or '(none)'}")
    typer.echo(f"planned agent runs: {n_runs}")
    typer.echo(f"caps ({cost_label}): total ${config.max_usd}, per run ${config.max_usd_per_run}")
    if config.pause_at_utilization is not None:
        typer.echo(f"pause when the five-hour window reaches {config.pause_at_utilization:.0%}")
    if not prices[key].verified:
        typer.echo("warning: price entry is unverified; results cannot be published.")


def _run_and_report(
    d: Path, config: Config, prices: dict, tasks: dict, cmd: list[str], resume_hint: Path
) -> None:
    key = _price_key(config)
    aux_prices = {
        m: p for (prov, m), p in prices.items() if prov == config.provider and m != key[1]
    }
    outcome = run_experiment(
        config, tasks, prices[key], Checkpoint(d), cmd, log=typer.echo, aux_prices=aux_prices
    )
    typer.echo(f"finished {outcome.finished} run(s), skipped {outcome.skipped} already done")
    if outcome.stopped_reason == "usage_limit":
        when = (
            datetime.fromtimestamp(outcome.reset_epoch).strftime("%Y-%m-%d %H:%M")
            if outcome.reset_epoch
            else "later"
        )
        typer.echo(
            f"Paused: {outcome.message or 'usage limit reached'}. Progress is saved. "
            f"Continue after {when} with:\n  tokentrial run --resume --out {resume_hint}"
        )
        raise typer.Exit(code=EXIT_USAGE_LIMIT)
    if outcome.stopped_reason == "fatal":
        typer.echo(
            f"Stopped: {outcome.message}\nIf this is an auth error, run `claude auth login` in a "
            f"terminal, then: tokentrial run --resume --out {resume_hint}",
            err=True,
        )
        raise typer.Exit(code=EXIT_FATAL)
    if outcome.stopped_reason == "budget":
        typer.echo(f"Stopped: total budget ${config.max_usd} reached. Results so far are saved.")
        raise typer.Exit(code=EXIT_BUDGET)


@app.command("install-arms")
def install_arms(
    arms: Annotated[
        list[str] | None, typer.Option("--arm", "-a", help="Tool to install (repeatable).")
    ] = None,
) -> None:
    """Download the pinned versions of the tools under test into a local cache.

    rtk: release binary from GitHub, verified against the release checksums.
    caveman: git clone of the pinned tag, verified against the pinned commit.
    Nothing is written to your global Claude Code configuration.
    """
    names = list(arms or tools.INSTALLERS)
    unknown = [n for n in names if n not in tools.INSTALLERS]
    if unknown:
        raise typer.BadParameter(f"nothing to install for: {', '.join(unknown)}")
    for name in names:
        pin = tools.PINS[name]
        typer.echo(f"{name} {pin.version} ({pin.source}) -> {tools.tool_dir(pin)}")
        tools.INSTALLERS[name](log=lambda m: typer.echo(f"  {m}"))
        typer.echo("  ok")


@app.command()
def report(
    runs: Annotated[Path, typer.Option(help="Experiment directory.")] = Path("runs/pilot"),
    out: Annotated[
        Path | None, typer.Option(help="Output directory (default: results/<experiment name>).")
    ] = None,
    resamples: Annotated[int, typer.Option(min=100, help="Bootstrap resamples.")] = 10_000,
    seed: Annotated[int, typer.Option(help="Bootstrap seed.")] = 0,
    export_raw: Annotated[
        bool,
        typer.Option(
            "--export-raw", help="Also copy manifest, records and logs (home path scrubbed)."
        ),
    ] = False,
) -> None:
    """Cost per solved task per arm, with bootstrap CIs against baseline and the noop floor."""
    from tokentrial.report import export_raw as _export_raw
    from tokentrial.report import load_records, summarize, to_markdown

    if not (runs / "records.jsonl").exists():
        typer.echo(f"no records in {runs}/", err=True)
        raise typer.Exit(code=EXIT_NOT_READY)
    manifest = json.loads((runs / "manifest.json").read_text())
    # A per-model experiment (runs/<exp>/<model>/) is named <exp>/<model>.
    multi = (runs.parent / MODELS_FILE).exists()
    rel = Path(runs.parent.name) / runs.name if multi else Path(runs.name)
    manifest.setdefault("name", rel.as_posix())
    records = load_records(runs)
    summary = summarize(records, n_boot=resamples, seed=seed)
    expected = len(manifest["task_ids"]) * len(manifest["arms"]) * manifest["repeats"]
    summary["complete"] = len(records) == expected
    summary["manifest"] = manifest
    dest = out or Path("results") / rel
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    md = to_markdown(summary, manifest)
    if not summary["complete"]:
        md = f"> Partial results: {len(records)} of {expected} runs.\n\n" + md
    (dest / "summary.md").write_text(md)
    typer.echo(md)
    typer.echo(f"wrote {dest}/summary.json and {dest}/summary.md")
    if export_raw:
        for path in _export_raw(runs, dest / "raw"):
            typer.echo(f"wrote {path}")


if __name__ == "__main__":
    app()
