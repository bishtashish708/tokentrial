"""Subcommands. Each module defines register(subparsers) and run(args, lock) -> exit code."""

from lockscan.commands import check, licenses, summary, tree, why

ALL = [summary, tree, why, licenses, check]
