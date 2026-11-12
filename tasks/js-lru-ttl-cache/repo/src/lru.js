// A small least-recently-used cache. See SPEC.md.
//
// Entries live in a Map, whose iteration order is insertion order: the first
// entry is the least recently used, the last one the most recently used.
// Touching an entry deletes and re-inserts it so it moves to the end.

export class LRUCache {
  #map = new Map();
  #maxSize;
  #onEvict;

  /**
   * @param {object} options
   * @param {number} options.maxSize  maximum number of entries (integer >= 1)
   * @param {(key: any, value: any, reason: string) => void} [options.onEvict]
   */
  constructor({ maxSize, onEvict } = {}) {
    if (!Number.isInteger(maxSize) || maxSize < 1) {
      throw new RangeError(`maxSize must be an integer >= 1, got ${maxSize}`);
    }
    this.#maxSize = maxSize;
    this.#onEvict = onEvict;
  }

  get maxSize() {
    return this.#maxSize;
  }

  /** Number of entries in the cache. */
  get size() {
    return this.#map.size;
  }

  /** Value for `key` (and mark it most recently used), or undefined. */
  get(key) {
    if (!this.#map.has(key)) return undefined;
    const value = this.#map.get(key);
    this.#map.delete(key);
    this.#map.set(key, value);
    return value;
  }

  /** Value for `key` without changing its recency, or undefined. */
  peek(key) {
    return this.#map.get(key);
  }

  has(key) {
    return this.#map.has(key);
  }

  /** Insert or replace `key`; it becomes the most recently used entry. */
  set(key, value) {
    if (this.#map.has(key)) {
      this.#map.delete(key);
    } else if (this.#map.size >= this.#maxSize) {
      const [oldKey, oldValue] = this.#map.entries().next().value;
      this.#map.delete(oldKey);
      this.#onEvict?.(oldKey, oldValue, 'lru');
    }
    this.#map.set(key, value);
    return this;
  }

  /** Remove `key`. Returns true if it was present. */
  delete(key) {
    return this.#map.delete(key);
  }

  clear() {
    this.#map.clear();
  }

  /** Keys, most recently used first. */
  keys() {
    return [...this.#map.keys()].reverse();
  }

  /** [key, value] pairs, most recently used first. */
  entries() {
    return [...this.#map.entries()].reverse();
  }
}
