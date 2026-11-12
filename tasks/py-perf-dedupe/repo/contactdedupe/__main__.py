"""python3 -m contactdedupe INPUT.jsonl OUTPUT.jsonl"""

import argparse
import sys
import time

from contactdedupe.dedupe import dedupe
from contactdedupe.jsonl import InputError, read_records, write_records


def main(argv=None):
    parser = argparse.ArgumentParser(prog="contactdedupe", description="Merge duplicate contacts.")
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    try:
        records = read_records(args.input)
    except (OSError, InputError) as e:
        print(f"contactdedupe: {e}", file=sys.stderr)
        return 2
    start = time.perf_counter()
    merged = dedupe(records)
    elapsed = time.perf_counter() - start
    write_records(args.output, merged)
    if args.verbose:
        print(
            f"{len(records)} contacts -> {len(merged)} merged in {elapsed:.2f}s",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
