"""Command-line entry point."""

import argparse
import logging
import os
import sys

from ingestd.config import ConfigError, load_settings

log = logging.getLogger(__name__)


def build_parser():
    ap = argparse.ArgumentParser(prog="ingestd")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, help_text in (("serve", "run the service"), ("check-config", "validate config and exit")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--config", help="main config file (default: config/ingestd.conf)")
        p.add_argument("--profile", help="profile name (profiles/<name>.conf)")
        p.add_argument("--workers", type=int, help="shortcut for --set worker.count=N")
        p.add_argument("--port", type=int, help="shortcut for --set http.port=N")
        p.add_argument("--log-level", help="shortcut for --set logging.level=LEVEL")
        p.add_argument(
            "--set",
            dest="overrides",
            action="append",
            default=[],
            metavar="KEY=VALUE",
            help="override a setting, e.g. --set worker.count=4 (repeatable)",
        )
    return ap


def cli_overrides(args):
    """Turn parsed CLI options into a flat {"section.name": value} layer."""
    layer = {}
    for item in args.overrides:
        key, sep, value = item.partition("=")
        if not sep or "." not in key:
            raise ConfigError(f"--set expects SECTION.NAME=VALUE, got {item!r}")
        layer[key.strip().lower()] = value.strip()
    if args.workers is not None:
        layer["worker.count"] = args.workers
    if args.port is not None:
        layer["http.port"] = args.port
    if args.log_level is not None:
        layer["logging.level"] = args.log_level
    return layer


def main(argv=None, environ=None):
    args = build_parser().parse_args(argv)
    environ = os.environ if environ is None else environ
    try:
        settings = load_settings(args, environ)
    except ConfigError as exc:
        print(f"ingestd: configuration error: {exc}", file=sys.stderr)
        return 2
    if args.command == "check-config":
        print("configuration OK")
        return 0
    from ingestd.app import run

    return run(settings)
