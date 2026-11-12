import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { LRUCache } from '../src/lru.js';

function setup(options) {
  const clock = { t: 1000 };
  const evicted = [];
  const cache = new LRUCache({
    now: () => clock.t,
    onEvict: (k, v, why) => evicted.push([k, v, why]),
    ...options,
  });
  return { cache, clock, evicted };
}

describe('TTL', () => {
  test('entry expires exactly at set time + ttl', () => {
    const { cache, clock } = setup({ maxSize: 3, ttl: 100 });
    cache.set('a', 1);
    clock.t = 1099;
    assert.equal(cache.get('a'), 1);
    clock.t = 1100;
    assert.equal(cache.get('a'), undefined);
  });

  test('per-entry ttl overrides the default', () => {
    const { cache, clock } = setup({ maxSize: 3, ttl: 100 });
    cache.set('short', 1, { ttl: 10 });
    cache.set('forever', 2, { ttl: Infinity });
    cache.set('default', 3);
    clock.t = 1050;
    assert.deepEqual(cache.keys(), ['default', 'forever']);
    clock.t = 5000;
    assert.deepEqual(cache.keys(), ['forever']);
  });

  test('get does not refresh an entry\'s expiry', () => {
    const { cache, clock } = setup({ maxSize: 3, ttl: 10 });
    cache.set('a', 1);
    clock.t = 1009;
    assert.equal(cache.get('a'), 1);
    clock.t = 1010;
    assert.equal(cache.has('a'), false);
  });

  test('size excludes expired entries', () => {
    const { cache, clock } = setup({ maxSize: 5 });
    cache.set('a', 1, { ttl: 5 }).set('b', 2);
    assert.equal(cache.size, 2);
    clock.t = 1005;
    assert.equal(cache.size, 1);
  });

  test('prune removes expired entries', () => {
    const { cache, clock, evicted } = setup({ maxSize: 5, ttl: 10 });
    cache.set('a', 1).set('b', 2, { ttl: 50 }).set('c', 3);
    clock.t = 1020;
    assert.equal(cache.prune(), 2);
    assert.equal(cache.prune(), 0);
    assert.deepEqual(evicted, [['a', 1, 'expired'], ['c', 3, 'expired']]);
  });

  test('expired entries are evicted before a live LRU entry', () => {
    const { cache, clock, evicted } = setup({ maxSize: 2 });
    cache.set('old', 1);
    cache.set('temp', 2, { ttl: 5 });
    clock.t = 1010;
    cache.set('new', 3);
    assert.deepEqual(evicted, [['temp', 2, 'expired']]);
    assert.deepEqual(cache.keys(), ['new', 'old']);
  });

  test('invalid ttl', () => {
    assert.throws(() => new LRUCache({ maxSize: 1, ttl: 0 }), RangeError);
    const { cache } = setup({ maxSize: 1 });
    assert.throws(() => cache.set('a', 1, { ttl: -1 }), RangeError);
    assert.equal(cache.size, 0);
  });
});
