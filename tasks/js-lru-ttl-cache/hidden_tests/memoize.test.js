import { test } from 'node:test';
import assert from 'node:assert/strict';
import { memoize } from '../src/memoize.js';

test('memoize caches by first argument', () => {
  let calls = 0;
  const sq = memoize((x) => (calls++, x * x), { maxSize: 2 });
  assert.equal(sq(3), 9);
  assert.equal(sq(3), 9);
  assert.equal(calls, 1);
});

test('memoize custom key and eviction', () => {
  let calls = 0;
  const add = memoize((a, b) => (calls++, a + b), { maxSize: 1, key: (a, b) => `${a}+${b}` });
  add(1, 2);
  add(2, 3);
  add(1, 2);
  assert.equal(calls, 3);
});

test('memoized results expire', () => {
  let t = 0;
  let calls = 0;
  const f = memoize((x) => (calls++, x), { maxSize: 4, ttl: 10, now: () => t });
  f('a');
  t = 9;
  f('a');
  assert.equal(calls, 1);
  t = 10;
  f('a');
  assert.equal(calls, 2);
});
