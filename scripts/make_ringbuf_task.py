"""Generate the hidden test data for tasks/c-ring-buffer deterministically.

Usage: python3 scripts/make_ringbuf_task.py

The repo/ and solution/ sources are maintained by hand. This script (re)writes the
hidden side of the task: hidden_tests/ (a copy of the visible test, a C driver, and
seeded random operation sequences with expected results), check.sh, and task.toml.

Expected results come from two independent Python models of SPEC.md that must agree on
every operation: `IndexModel` (fixed storage + head/count index arithmetic, like a C
implementation) and `SliceModel` (a plain bytearray, appending at the end and deleting
from the front). Any disagreement aborts generation.
"""

from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tasks" / "c-ring-buffer"
SEED = 20261112
N_SEQUENCES = 160


class IndexModel:
    """Fixed-size storage with a head index and a count, wrapping by modulo."""

    def __init__(self, cap: int):
        self.cap = cap
        self.store = [0] * cap
        self.head = 0
        self.count = 0

    def used(self) -> int:
        return self.count

    def free(self) -> int:
        return self.cap - self.count

    def _at(self, logical: int) -> int:
        return self.store[(self.head + logical) % self.cap]

    def _push(self, b: int) -> None:
        self.store[(self.head + self.count) % self.cap] = b
        self.count += 1

    def _pop(self) -> int:
        b = self.store[self.head]
        self.head = (self.head + 1) % self.cap
        self.count -= 1
        return b

    def write(self, data: bytes) -> int:
        k = min(len(data), self.free())
        for b in data[:k]:
            self._push(b)
        return k

    def write_overwrite(self, data: bytes) -> int:
        dropped = 0
        for b in data:  # one byte at a time, as SPEC.md defines it
            if self.count == self.cap:
                self._pop()
                dropped += 1
            self._push(b)
        return dropped

    def read(self, n: int) -> bytes:
        return bytes(self._pop() for _ in range(min(n, self.count)))

    def peek(self, offset: int, n: int) -> bytes:
        if offset >= self.count:
            return b""
        k = min(n, self.count - offset)
        return bytes(self._at(offset + i) for i in range(k))

    def skip(self, n: int) -> int:
        k = min(n, self.count)
        self.head = (self.head + k) % self.cap
        self.count -= k
        return k

    def find(self, byte: int, start: int) -> int | None:
        for i in range(start, self.count):
            if self._at(i) == byte:
                return i
        return None

    def clear(self) -> None:
        self.head = 0
        self.count = 0


class SliceModel:
    """A bytearray holding exactly the stored bytes, oldest first."""

    def __init__(self, cap: int):
        self.cap = cap
        self.data = bytearray()

    def used(self) -> int:
        return len(self.data)

    def free(self) -> int:
        return self.cap - len(self.data)

    def write(self, data: bytes) -> int:
        chunk = data[: self.free()]
        self.data += chunk
        return len(chunk)

    def write_overwrite(self, data: bytes) -> int:
        before = len(self.data) + len(data)
        self.data = (self.data + data)[-self.cap :]
        return before - len(self.data)

    def read(self, n: int) -> bytes:
        out = bytes(self.data[:n])
        del self.data[:n]
        return out

    def peek(self, offset: int, n: int) -> bytes:
        return bytes(self.data[offset : offset + n])

    def skip(self, n: int) -> int:
        k = len(self.data[:n])
        del self.data[:n]
        return k

    def find(self, byte: int, start: int) -> int | None:
        i = self.data.find(bytes([byte]), start) if start < len(self.data) else -1
        return None if i < 0 else i

    def clear(self) -> None:
        self.data = bytearray()


def hexs(b: bytes) -> str:
    return b.hex() if b else "-"


def rand_bytes(rng: random.Random, n: int) -> bytes:
    small = [0x00, 0x0A, 0x0D, 0x41, 0x42, 0x7F, 0xFF]
    return bytes(rng.choice(small) if rng.random() < 0.4 else rng.randrange(256) for _ in range(n))


def gen_sequence(rng: random.Random, seq_id: int) -> list[str]:
    cap = rng.choice([1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 16, 17, 31, 64, 100])
    a, b = IndexModel(cap), SliceModel(cap)
    lines = [f"# sequence {seq_id}", f"C {cap}"]
    n_ops = rng.randint(25, 60)
    for _ in range(n_ops):
        op = rng.choices("WORPSFX", weights=[28, 14, 18, 12, 8, 18, 2])[0]
        used = a.used()
        if op == "W":
            data = rand_bytes(rng, rng.randint(0, cap + 2))
            ra, rb = a.write(data), b.write(data)
            assert ra == rb, (seq_id, op)
            line = f"W {hexs(data)} {ra}"
        elif op == "O":
            hi = 2 * cap + 3 if rng.random() < 0.4 else cap
            data = rand_bytes(rng, rng.randint(0, hi))
            ra, rb = a.write_overwrite(data), b.write_overwrite(data)
            assert ra == rb, (seq_id, op)
            line = f"O {hexs(data)} {ra}"
        elif op == "R":
            n = rng.randint(0, cap + 2)
            ra, rb = a.read(n), b.read(n)
            assert ra == rb, (seq_id, op)
            line = f"R {n} {hexs(ra)}"
        elif op == "P":
            off = rng.randint(0, used + 1)
            n = rng.randint(0, cap + 1)
            ra, rb = a.peek(off, n), b.peek(off, n)
            assert ra == rb, (seq_id, op)
            line = f"P {off} {n} {hexs(ra)}"
        elif op == "S":
            n = rng.randint(0, cap + 1)
            ra, rb = a.skip(n), b.skip(n)
            assert ra == rb, (seq_id, op)
            line = f"S {n} {ra}"
        elif op == "F":
            stored = a.peek(0, used)
            if stored and rng.random() < 0.75:
                byte = rng.choice(stored)
            else:
                byte = rng.randrange(256)
            start = (
                rng.randint(0, used + 1)
                if rng.random() < 0.3
                else rng.randint(0, max(0, used // 2))
            )
            ra, rb = a.find(byte, start), b.find(byte, start)
            assert ra == rb, (seq_id, op)
            line = f"F {byte} {start} {-1 if ra is None else ra}"
        else:
            a.clear()
            b.clear()
            line = "X"
        assert a.used() == b.used() and a.free() == b.free()
        assert a.peek(0, a.used()) == bytes(b.data), (seq_id, "contents")
        lines.append(f"{line} {a.used()} {a.free()}")
    lines.append(f"D {hexs(a.peek(0, a.used()))}")  # full contents via rb_peek
    return lines


DRIVER = r"""/* Hidden test: replays generated operation sequences (see ringbuf_cases.txt). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ringbuf.h"

static int failures = 0;
static long lineno = 0;
static char seqname[64] = "?";

static void fail(const char *what, const char *line)
{
    failures++;
    if (failures <= 40)
        fprintf(stderr, "%s (line %ld): %s: %s", seqname, lineno, what, line);
}

/* Parse hex ("-" = empty) into a freshly allocated buffer; returns length. */
static size_t unhex(const char *s, uint8_t **out)
{
    size_t n = 0, i;
    uint8_t *buf;

    if (strcmp(s, "-") == 0) {
        *out = malloc(1);
        return 0;
    }
    n = strlen(s) / 2;
    buf = malloc(n + 1);
    for (i = 0; i < n; i++) {
        unsigned v;
        sscanf(s + 2 * i, "%2x", &v);
        buf[i] = (uint8_t)v;
    }
    *out = buf;
    return n;
}

int main(int argc, char **argv)
{
    static char line[16384];
    char tok[8192];
    FILE *f;
    ringbuf_t *rb = NULL;
    long ops = 0;

    if (argc != 2) {
        fprintf(stderr, "usage: %s CASES_FILE\n", argv[0]);
        return 2;
    }
    f = fopen(argv[1], "r");
    if (f == NULL) {
        perror(argv[1]);
        return 2;
    }
    while (fgets(line, sizeof line, f) != NULL) {
        unsigned long a1, a2, eu, ef;
        long sfound;
        uint8_t *data, *got;
        size_t n, k;

        lineno++;
        if (line[0] == '#') {
            sscanf(line, "# %63[^\n]", seqname);
            continue;
        }
        ops++;
        switch (line[0]) {
        case 'C':
            rb_destroy(rb);
            sscanf(line, "C %lu", &a1);
            rb = rb_create((size_t)a1);
            if (rb == NULL) {
                fail("rb_create returned NULL", line);
                return 1;
            }
            continue;
        case 'W':
        case 'O':
            sscanf(line + 2, "%8191s %lu %lu %lu", tok, &a1, &eu, &ef);
            n = unhex(tok, &data);
            k = line[0] == 'W' ? rb_write(rb, n ? data : NULL, n)
                               : rb_write_overwrite(rb, n ? data : NULL, n);
            if (k != a1)
                fail(line[0] == 'W' ? "rb_write return value" : "rb_write_overwrite return value",
                     line);
            free(data);
            break;
        case 'R':
            sscanf(line, "R %lu %8191s %lu %lu", &a1, tok, &eu, &ef);
            n = unhex(tok, &data);
            got = malloc(a1 + 1);
            k = rb_read(rb, a1 ? got : NULL, a1);
            if (k != n || memcmp(got, data, n) != 0)
                fail("rb_read result", line);
            free(got);
            free(data);
            break;
        case 'P':
            sscanf(line, "P %lu %lu %8191s %lu %lu", &a1, &a2, tok, &eu, &ef);
            n = unhex(tok, &data);
            got = malloc(a2 + 1);
            k = rb_peek(rb, a1, a2 ? got : NULL, a2);
            if (k != n || memcmp(got, data, n) != 0)
                fail("rb_peek result", line);
            free(got);
            free(data);
            break;
        case 'S':
            sscanf(line, "S %lu %lu %lu %lu", &a1, &a2, &eu, &ef);
            if (rb_skip(rb, a1) != a2)
                fail("rb_skip return value", line);
            break;
        case 'F': {
            size_t pos = 123456789;
            int r;
            sscanf(line, "F %lu %lu %ld %lu %lu", &a1, &a2, &sfound, &eu, &ef);
            r = rb_find(rb, (uint8_t)a1, a2, &pos);
            if (sfound < 0) {
                if (r != 0 || pos != 123456789)
                    fail("rb_find should not find / must leave *pos unchanged", line);
            } else if (r != 1 || pos != (size_t)sfound) {
                fail("rb_find result", line);
            }
            break;
        }
        case 'X':
            sscanf(line, "X %lu %lu", &eu, &ef);
            rb_clear(rb);
            break;
        case 'D':
            sscanf(line, "D %8191s", tok);
            n = unhex(tok, &data);
            got = malloc(rb_capacity(rb) + 1);
            k = rb_peek(rb, 0, got, rb_capacity(rb));
            if (k != n || memcmp(got, data, n) != 0)
                fail("final contents", line);
            free(got);
            free(data);
            continue;
        default:
            fprintf(stderr, "bad case line %ld\n", lineno);
            return 2;
        }
        if (rb_used(rb) != eu || rb_free(rb) != ef)
            fail("rb_used/rb_free after operation", line);
    }
    fclose(f);
    rb_destroy(rb);
    if (failures) {
        fprintf(stderr, "%d failures\n", failures);
        return 1;
    }
    printf("%ld operations ok\n", ops);
    return 0;
}
"""

CHECK = """#!/usr/bin/env bash
# Hidden check for c-ring-buffer: restore the tests, build them, run the visible test and
# the generated operation sequences.
set -euo pipefail
: "${TASK_DIR:?TASK_DIR must point at the task directory}"
mkdir -p tests
cp "$TASK_DIR/hidden_tests/test_ringbuf.c" tests/test_ringbuf.c
cp "$TASK_DIR/hidden_tests/test_ringbuf_cases.c" tests/test_ringbuf_cases.c
cp "$TASK_DIR/hidden_tests/ringbuf_cases.txt" tests/ringbuf_cases.txt
out=.tt-check
rm -rf "$out" && mkdir -p "$out"
CFLAGS="-std=c11 -Wall -Wextra -O1 -I."
cc $CFLAGS -o "$out/test_ringbuf" tests/test_ringbuf.c ringbuf.c linereader.c >/dev/null 2>&1
cc $CFLAGS -o "$out/test_cases" tests/test_ringbuf_cases.c ringbuf.c >/dev/null 2>&1
"$out/test_ringbuf" >/dev/null 2>&1
"$out/test_cases" tests/ringbuf_cases.txt >/dev/null 2>&1
rm -rf "$out"
"""

TASK_TOML = '''prompt = """
This is a small C library: a fixed-capacity byte ring buffer (ringbuf.c / ringbuf.h) and a
newline-framed reader built on it (linereader.c). The ring buffer has bugs and its tests
fail. SPEC.md defines the required behaviour of the ringbuf API precisely. Fix ringbuf.c so
that it implements SPEC.md exactly; keep the public API in ringbuf.h unchanged. Do not
modify the tests. Build and run them with `make test` (compiled with
`cc -std=c11 -Wall -Wextra`). Your fix will also be checked against additional cases
derived from SPEC.md.
"""
timeout_s = 1200
tags = ["c", "make", "spec", "multi-bug", "data-structure", "medium"]
'''


def main() -> int:
    rng = random.Random(SEED)
    out = ["# ringbuf operation sequences generated by scripts/make_ringbuf_task.py"]
    out.append("# Each op line ends with the expected rb_used and rb_free afterwards.")
    n_ops = 0
    for i in range(N_SEQUENCES):
        seq = gen_sequence(rng, i)
        n_ops += len(seq) - 1
        out.extend(seq)

    hidden = ROOT / "hidden_tests"
    shutil.rmtree(hidden, ignore_errors=True)
    hidden.mkdir()
    shutil.copy(ROOT / "repo" / "tests" / "test_ringbuf.c", hidden / "test_ringbuf.c")
    (hidden / "test_ringbuf_cases.c").write_text(DRIVER)
    (hidden / "ringbuf_cases.txt").write_text("\n".join(out) + "\n")
    (ROOT / "check.sh").write_text(CHECK)
    (ROOT / "check.sh").chmod(0o755)
    (ROOT / "task.toml").write_text(TASK_TOML)
    print(f"{N_SEQUENCES} sequences, {n_ops} operations; both models agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
