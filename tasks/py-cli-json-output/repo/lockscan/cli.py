"""Command-line entry point: python3 -m lockscan [-f LOCKFILE] COMMAND [options]."""

import argparse
import sys

from lockscan import __version__
from lockscan.commands import ALL
from lockscan.errors import LockscanError
from lockscan.loader import load

EXIT_ERROR = 2


def build_parser():
    parser = argparse.ArgumentParser(
        prog="lockscan", description="Report on a project's dependency lockfile."
    )
    parser.add_argument("-f", "--lockfile", default="lockscan.lock",
                        help="path to the lockfile (default: ./lockscan.lock)")
    parser.add_argument("--version", action="version", version=f"lockscan {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for module in ALL:
        module.register(sub)
    return parser


def report_error(err):
    print(f"lockscan: error: {err.message}", file=sys.stderr)
    return EXIT_ERROR


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        lock = load(args.lockfile)
        return args.run(args, lock)
    except LockscanError as err:
        return report_error(err)
