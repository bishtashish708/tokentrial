"""Generate the hidden cases for tasks/js-csv-quoted-fields deterministically.

Usage: python3 scripts/make_csv_task.py   (needs node >= 20 on PATH)

repo/ (buggy csv.js, SPEC.md, visible tests), solution/ (reference csv.js), check.sh and
task.toml are hand-written files in the task directory. This script (re)writes
hidden_tests/: a copy of each visible test file, hidden_cases.test.js and cases.json.

Expected outputs come from the reference solution (solution/src/csv.js, run with node) and
are cross-checked, case by case, against Python's stdlib `csv` module configured to match
SPEC.md (`csv.reader(io.StringIO(text, newline=""), delimiter=d, strict=True)` and
`csv.writer(..., lineterminator="\\r\\n", quoting=csv.QUOTE_MINIMAL)`). The script asserts
they agree on every case.

Where SPEC.md goes beyond Python's csv (error messages), the cross-check is explicit:
- Python must also raise `csv.Error`, with the matching kind
  ("unexpected end of data" for an unterminated quote, "',' expected after '\\"'" for a
  character after a closing quote; the delimiter appears in place of ',').
- "Unexpected character after closing quote at line N": N must equal the reader's
  `line_num` when Python raises (Python reads one physical line at a time, splitting on
  \\r\\n, \\n and \\r exactly like SPEC.md's physical lines).
- "Unterminated quoted field at line N": Python only fails at end of input, so N is derived
  independently: append a closing quote, parse with Python, take the last field's value,
  re-escape it to locate the opening quote, and count line breaks before it.
"""

import csv
import io
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tasks" / "js-csv-quoted-fields"
SEED = 4180
N_PARSE = 320
N_STRINGIFY = 80

RUNNER = r"""
import { parse, stringify } from 'MODULE_URL';
let data = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (d) => (data += d));
process.stdin.on('end', () => {
  const { parseCases, stringifyCases } = JSON.parse(data);
  const out = { parse: [], stringify: [] };
  for (const c of parseCases) {
    try {
      out.parse.push({ records: parse(c.input, { delimiter: c.delimiter }) });
    } catch (e) {
      out.parse.push({ error: { name: e.name, message: e.message, line: e.line } });
    }
  }
  for (const c of stringifyCases) {
    out.stringify.push(stringify(c.records, { delimiter: c.delimiter }));
  }
  process.stdout.write(JSON.stringify(out));
});
"""

HIDDEN_TEST = r"""import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { parse, stringify, CsvError } from '../src/csv.js';

const CASES = JSON.parse(
  readFileSync(fileURLToPath(new URL('./cases.json', import.meta.url)), 'utf8'),
);

for (const [i, c] of CASES.parse.entries()) {
  test(`parse #${i} ${JSON.stringify(c.input)}`, () => {
    const opts = { delimiter: c.delimiter };
    if (c.error) {
      assert.throws(() => parse(c.input, opts), (err) => {
        assert.ok(err instanceof CsvError, 'expected a CsvError');
        assert.equal(err.message, c.error.message);
        assert.equal(err.line, c.error.line);
        return true;
      });
    } else {
      assert.deepEqual(parse(c.input, opts), c.records);
    }
  });
}

for (const [i, c] of CASES.stringify.entries()) {
  test(`stringify #${i}`, () => {
    const opts = { delimiter: c.delimiter };
    assert.equal(stringify(c.records, opts), c.output);
    assert.deepEqual(parse(c.output, opts), c.records);
  });
}
"""

VISIBLE_TESTS = ["csv.test.js", "report.test.js"]


def rand_delim(rng):
    r = rng.random()
    return "," if r < 0.7 else (";" if r < 0.85 else "\t")


def rand_value(rng, delim):
    pieces = ["a", "b", "x", "7", " ", delim, '"', '""', "\n", "\r\n", "\r", "é"]
    weights = [6, 5, 3, 2, 2, 2, 2, 1, 1, 1, 1, 1]
    if rng.random() < 0.25:
        return ""
    return "".join(rng.choices(pieces, weights, k=rng.randint(1, 5)))


def encode_field(rng, value, delim):
    special = any(ch in value for ch in (delim, '"', "\r", "\n"))
    if special or rng.random() < 0.3:
        return '"' + value.replace('"', '""') + '"'
    return value


def structured_input(rng, delim):
    lines = []
    for _ in range(rng.randint(1, 5)):
        if rng.random() < 0.12:
            lines.append("")  # blank record
            continue
        n = rng.randint(1, 4)
        lines.append(delim.join(encode_field(rng, rand_value(rng, delim), delim) for _ in range(n)))
    out = ""
    for k, line in enumerate(lines):
        out += line
        last = k == len(lines) - 1
        if not last or rng.random() < 0.5:
            out += rng.choice(["\n", "\r\n", "\r"])
    if rng.random() < 0.15:
        out = corrupt(rng, out, delim)
    return out


def corrupt(rng, text, delim):
    """Introduce one error: drop a quote, or put a stray character after a closing quote."""
    quotes = [i for i, ch in enumerate(text) if ch == '"']
    if not quotes:
        return text + '"' + rand_value(rng, delim).replace('"', "")
    i = rng.choice(quotes)
    if rng.random() < 0.5:
        return text[:i] + text[i + 1 :]
    return text[: i + 1] + rng.choice(["x", " ", '"z']) + text[i + 1 :]


def raw_input(rng, delim):
    alphabet = ["a", "b", delim, '"', '"', "\n", "\r", "\r\n", " "]
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 14)))


def tail_input(rng, delim):
    """Inputs that end in a final record with no line break (incl. a lone `""`)."""
    head = structured_input(rng, delim)
    if head and head[-1] not in "\r\n":
        head += rng.choice(["\n", "\r\n", "\r"])
    tail = rng.choice(['""', '""' + delim + '""', delim, '"a' + delim + 'b"', '""""', '"\r\n"'])
    return head + tail


def python_parse(text, delim):
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim, strict=True)
    rows = []
    try:
        for row in reader:
            rows.append(row)
    except csv.Error as e:
        return None, (str(e), reader.line_num)
    return rows, None


def count_breaks(text):
    return sum(1 for ln in io.StringIO(text, newline="").readlines() if ln[-1] in "\r\n")


def cross_check_parse(case, result):
    text, delim = case["input"], case["delimiter"]
    rows, perr = python_parse(text, delim)
    if "records" in result:
        assert perr is None, (text, perr)
        assert rows == result["records"], (text, rows, result["records"])
        return
    err = result["error"]
    assert err["name"] == "CsvError", err
    assert perr is not None, (text, "python accepted", rows)
    pmsg, pline = perr
    if err["message"].startswith("Unexpected character after closing quote"):
        assert pmsg == f"'{delim}' expected after '\"'", (text, pmsg)
        line = pline
        assert err["message"] == f"Unexpected character after closing quote at line {line}"
    else:
        assert pmsg == "unexpected end of data", (text, pmsg)
        closed, cerr = python_parse(text + '"', delim)
        assert cerr is None, (text, cerr)
        value = closed[-1][-1]
        escaped = value.replace('"', '""')
        p = len(text) - len(escaped) - 1
        assert text[p] == '"' and text[p + 1 :] == escaped, (text, p)
        line = 1 + count_breaks(text[:p])
        assert err["message"] == f"Unterminated quoted field at line {line}", (text, err)
    assert err["line"] == line, (text, err)


def python_stringify(records, delim):
    s = io.StringIO()
    csv.writer(s, delimiter=delim, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL).writerows(
        records
    )
    return s.getvalue()


def main():
    rng = random.Random(SEED)
    parse_cases = []
    seen = set()
    while len(parse_cases) < N_PARSE:
        delim = rand_delim(rng)
        r = rng.random()
        if r < 0.6:
            text = structured_input(rng, delim)
        elif r < 0.85:
            text = raw_input(rng, delim)
        else:
            text = tail_input(rng, delim)
        if (text, delim) in seen:
            continue
        seen.add((text, delim))
        parse_cases.append({"input": text, "delimiter": delim})

    stringify_cases = []
    for _ in range(N_STRINGIFY):
        delim = rand_delim(rng)
        records = []
        for _ in range(rng.randint(0, 4)):
            records.append([rand_value(rng, delim) for _ in range(rng.choice([0, 1, 1, 2, 3]))])
        stringify_cases.append({"records": records, "delimiter": delim})

    module_url = (ROOT / "solution" / "src" / "csv.js").resolve().as_uri()
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", RUNNER.replace("MODULE_URL", module_url)],
        input=json.dumps({"parseCases": parse_cases, "stringifyCases": stringify_cases}),
        capture_output=True,
        text=True,
        check=True,
    )
    out = json.loads(proc.stdout)

    hidden_parse = []
    for case, result in zip(parse_cases, out["parse"], strict=True):
        cross_check_parse(case, result)
        entry = {"input": case["input"], "delimiter": case["delimiter"]}
        if "records" in result:
            entry["records"] = result["records"]
        else:
            entry["error"] = {
                "message": result["error"]["message"],
                "line": result["error"]["line"],
            }
        hidden_parse.append(entry)

    hidden_stringify = []
    for case, output in zip(stringify_cases, out["stringify"], strict=True):
        expected = python_stringify(case["records"], case["delimiter"])
        assert output == expected, (case, output, expected)
        rows, perr = python_parse(output, case["delimiter"])
        assert perr is None and rows == case["records"], (case, rows)
        hidden_stringify.append({**case, "output": output})

    hidden = ROOT / "hidden_tests"
    shutil.rmtree(hidden, ignore_errors=True)
    hidden.mkdir()
    for name in VISIBLE_TESTS:
        shutil.copy(ROOT / "repo" / "test" / name, hidden / name)
    (hidden / "hidden_cases.test.js").write_text(HIDDEN_TEST)
    (hidden / "cases.json").write_text(
        json.dumps({"parse": hidden_parse, "stringify": hidden_stringify}, indent=1) + "\n"
    )
    n_err = sum("error" in c for c in hidden_parse)
    n_unterm = sum(
        "error" in c and c["error"]["message"].startswith("Unterm") for c in hidden_parse
    )
    print(
        f"{len(hidden_parse)} parse cases ({n_err} errors, {n_unterm} unterminated), "
        f"{len(hidden_stringify)} stringify cases; all agree with Python csv"
    )


if __name__ == "__main__":
    sys.exit(main())
