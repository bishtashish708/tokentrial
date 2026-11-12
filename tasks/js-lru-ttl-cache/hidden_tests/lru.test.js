import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { LRUCache } from '../src/lru.js';

function tracked(maxSize) {
  const evicted = [];
  const cache = new LRUCache({ maxSize, onEvict: (k, v, why) => evicted.push([k, v, why]) });
  return { cache, evicted };
}

describe('LRUCache (no TTL)', () => {
  test('get and set', () => {
    const c = new LRUCache({ maxSize: 3 });
    assert.equal(c.set('a', 1), c);
    assert.equal(c.get('a'), 1);
    assert.equal(c.get('missing'), undefined);
    assert.equal(c.size, 1);
  });

  test('evicts the least recently used entry', () => {
    const { cache, evicted } = tracked(2);
    cache.set('a', 1).set('b', 2);
    cache.get('a');
    cache.set('c', 3);
    assert.deepEqual(evicted, [['b', 2, 'lru']]);
    assert.deepEqual(cache.keys(), ['c', 'a']);
  });

  test('replacing a key moves it to MRU and evicts nothing', () => {
    const { cache, evicted } = tracked(2);
    cache.set('a', 1).set('b', 2).set('a', 10);
    assert.deepEqual(cache.entries(), [['a', 10], ['b', 2]]);
    assert.deepEqual(evicted, []);
  });

  test('peek and has do not change recency', () => {
    const { cache, evicted } = tracked(2);
    cache.set('a', 1).set('b', 2);
    assert.equal(cache.peek('a'), 1);
    assert.equal(cache.has('a'), true);
    cache.set('c', 3);
    assert.deepEqual(evicted, [['a', 1, 'lru']]);
  });

  test('delete and clear do not call onEvict', () => {
    const { cache, evicted } = tracked(3);
    cache.set('a', 1).set('b', 2);
    assert.equal(cache.delete('a'), true);
    assert.equal(cache.delete('a'), false);
    cache.clear();
    assert.equal(cache.size, 0);
    assert.deepEqual(evicted, []);
  });

  test('maxSize validation', () => {
    assert.throws(() => new LRUCache({ maxSize: 0 }), RangeError);
    assert.throws(() => new LRUCache({ maxSize: 1.5 }), RangeError);
    assert.throws(() => new LRUCache({}), RangeError);
    assert.equal(new LRUCache({ maxSize: 4 }).maxSize, 4);
  });
});
