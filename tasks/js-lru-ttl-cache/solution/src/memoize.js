import { LRUCache } from './lru.js';

/**
 * Cache `fn`'s results in an LRUCache. See SPEC.md.
 * @param {Function} fn
 * @param {object} [options]
 * @param {number} [options.maxSize=100]
 * @param {number} [options.ttl]  time-to-live of cached results in ms
 * @param {() => number} [options.now]  clock for the TTL
 * @param {(...args: any[]) => any} [options.key]  cache key for a call (default: first argument)
 */
export function memoize(fn, { maxSize = 100, key = (first) => first, ttl, now, onEvict } = {}) {
  const cache = new LRUCache({ maxSize, ttl, now, onEvict });
  const memo = function (...args) {
    const k = key(...args);
    if (cache.has(k)) return cache.get(k);
    const result = fn.apply(this, args);
    cache.set(k, result);
    return result;
  };
  memo.cache = cache;
  return memo;
}
