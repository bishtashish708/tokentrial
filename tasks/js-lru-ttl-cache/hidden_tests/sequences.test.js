import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { LRUCache } from '../src/lru.js';

const CASES = JSON.parse(
  readFileSync(fileURLToPath(new URL('./sequences.json', import.meta.url)), 'utf8'),
);

const num = (x) => (x === 'Infinity' ? Infinity : x === 'NaN' ? NaN : x);

export function runCase(Cache, c) {
  let clock = 1000;
  let evicted = [];
  const options = { maxSize: c.maxSize, now: () => clock, onEvict: (k, v, r) => evicted.push([k, v, r]) };
  if (c.ttl !== null) options.ttl = num(c.ttl);
  const cache = new Cache(options);
  const trace = [];
  for (const op of c.ops) {
    if (op.op === 'tick') {
      clock += op.ms;
      continue;
    }
    evicted = [];
    let result;
    switch (op.op) {
      case 'set':
        try {
          if (op.ttl === undefined) cache.set(op.key, op.value);
          else cache.set(op.key, op.value, { ttl: num(op.ttl) });
          result = null;
        } catch (e) {
          result = e instanceof RangeError ? 'RangeError' : `unexpected ${e}`;
        }
        break;
      case 'get':
      case 'peek':
      case 'has':
      case 'delete':
        result = cache[op.op](op.key);
        break;
      case 'size':
        result = cache.size;
        break;
      case 'keys':
      case 'entries':
      case 'prune':
      case 'clear':
        result = cache[op.op]();
        break;
      default:
        throw new Error(`bad op ${op.op}`);
    }
    trace.push({ result: result === undefined ? null : result, evicted });
  }
  return trace;
}

for (const [i, c] of CASES.entries()) {
  test(`sequence #${i} (maxSize ${c.maxSize}, ttl ${c.ttl})`, () => {
    const got = runCase(LRUCache, c);
    for (let j = 0; j < c.expected.length; j++) {
      assert.deepEqual(got[j], c.expected[j], `operation #${j} of sequence #${i}`);
    }
    assert.equal(got.length, c.expected.length);
  });
}
