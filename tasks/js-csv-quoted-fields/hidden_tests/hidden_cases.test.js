import { test } from 'node:test';
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
