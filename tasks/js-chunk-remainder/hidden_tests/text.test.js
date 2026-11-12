import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { chunk, truncate, wrap, paginate } from '../src/text.js';

const debug = (...a) => console.log('[debug]', ...a);

describe('chunk', () => {
  test('even split', () => {
    debug('chunk even input', JSON.stringify([1, 2, 3, 4]));
    assert.deepEqual(chunk([1, 2, 3, 4], 2), [[1, 2], [3, 4]]);
  });
  test('keeps the shorter last group', () => {
    debug('chunk uneven input', JSON.stringify([1, 2, 3, 4, 5]));
    assert.deepEqual(chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]]);
  });
  test('size larger than input', () => {
    assert.deepEqual(chunk([1, 2], 5), [[1, 2]]);
  });
  test('empty input', () => {
    assert.deepEqual(chunk([], 3), []);
  });
  test('rejects bad size', () => {
    assert.throws(() => chunk([1], 0), RangeError);
    assert.throws(() => chunk([1], 1.5), RangeError);
  });
});

describe('truncate', () => {
  for (const [s, max, want] of [
    ['hello', 10, 'hello'],
    ['hello world', 5, 'hell…'],
    ['abc', 3, 'abc'],
    ['abcd', 1, '…'],
  ]) {
    test(`truncate(${JSON.stringify(s)}, ${max})`, () => {
      debug('truncate case', s, max);
      assert.equal(truncate(s, max), want);
    });
  }
});

describe('wrap', () => {
  test('wraps greedily', () => {
    assert.deepEqual(wrap('the quick brown fox jumps', 10), ['the quick', 'brown fox', 'jumps']);
  });
  test('keeps long words whole', () => {
    assert.deepEqual(wrap('a supercalifragilistic b', 5), ['a', 'supercalifragilistic', 'b']);
  });
  test('collapses whitespace', () => {
    assert.deepEqual(wrap('  a   b  ', 10), ['a b']);
  });
});

describe('paginate', () => {
  const text = 'one two three four five six seven eight nine ten eleven';
  test('pages of two lines', () => {
    const pages = paginate(text, 9, 2);
    debug('pages', JSON.stringify(pages));
    assert.equal(pages.flat().join(' '), text);
  });
  test('page count', () => {
    assert.equal(paginate(text, 9, 2).length, 4);
  });
});
