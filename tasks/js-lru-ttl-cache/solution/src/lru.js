// A small least-recently-used cache with optional per-entry TTL. See SPEC.md.
//
// Entries live in a Map, whose iteration order is insertion order: the first
// entry is the least recently used, the last one the most recently used.
// Touching an entry deletes and re-inserts it so it moves to the end.
// Expired entries stay in the map until a removal point (see SPEC.md) drops them.

function checkTtl(ttl, what) {
  if (ttl === undefined) return;
  if (typeof ttl !== 'number' || Number.isNaN(ttl) || !(ttl > 0)) {
    throw new RangeError(`${what} must be a number > 0, got ${String(ttl)}`);
  }
}

export class LRUCache {
  #map = new Map(); // key -> { value, expiresAt }
  #maxSize;
  #ttl;
  #now;
  #onEvict;

  /**
   * @param {object} options
   * @param {number} options.maxSize  maximum number of stored entries (integer >= 1)
   * @param {number} [options.ttl]    default time-to-live in ms
   * @param {() => number} [options.now]  clock, defaults to Date.now
   * @param {(key: any, value: any, reason: string) => void} [options.onEvict]
   */
  constructor({ maxSize, ttl, now = Date.now, onEvict } = {}) {
    if (!Number.isInteger(maxSize) || maxSize < 1) {
      throw new RangeError(`maxSize must be an integer >= 1, got ${maxSize}`);
    }
    checkTtl(ttl, 'ttl');
    this.#maxSize = maxSize;
    this.#ttl = ttl;
    this.#now = now;
    this.#onEvict = onEvict;
  }

  get maxSize() {
    return this.#maxSize;
  }

  /** Number of live entries. */
  get size() {
    const t = this.#now();
    let n = 0;
    for (const entry of this.#map.values()) if (t < entry.expiresAt) n++;
    return n;
  }

  #remove(key, entry, reason) {
    this.#map.delete(key);
    this.#onEvict?.(key, entry.value, reason);
  }

  // The live entry for key, or undefined (removing it if it is expired).
  #lookup(key) {
    const entry = this.#map.get(key);
    if (entry === undefined) return undefined;
    if (this.#now() >= entry.expiresAt) {
      this.#remove(key, entry, 'expired');
      return undefined;
    }
    return entry;
  }

  #removeExpired(t) {
    let removed = 0;
    for (const [key, entry] of [...this.#map]) {
      if (t >= entry.expiresAt) {
        this.#remove(key, entry, 'expired');
        removed++;
      }
    }
    return removed;
  }

  /** Value for `key` (and mark it most recently used), or undefined. */
  get(key) {
    const entry = this.#lookup(key);
    if (entry === undefined) return undefined;
    this.#map.delete(key);
    this.#map.set(key, entry);
    return entry.value;
  }

  /** Value for `key` without changing its recency, or undefined. */
  peek(key) {
    return this.#lookup(key)?.value;
  }

  has(key) {
    return this.#lookup(key) !== undefined;
  }

  /** Insert or replace `key`; it becomes the most recently used entry. */
  set(key, value, { ttl } = {}) {
    checkTtl(ttl, 'ttl');
    const t = this.#now();
    const life = ttl !== undefined ? ttl : this.#ttl;
    const expiresAt = life === undefined ? Infinity : t + life;

    const existing = this.#map.get(key);
    if (existing !== undefined) {
      if (t < existing.expiresAt) {
        this.#map.delete(key);
        this.#map.set(key, { value, expiresAt });
        return this;
      }
      this.#remove(key, existing, 'expired');
    }
    if (this.#map.size >= this.#maxSize) {
      this.#removeExpired(t);
      if (this.#map.size >= this.#maxSize) {
        const [oldKey, oldEntry] = this.#map.entries().next().value;
        this.#remove(oldKey, oldEntry, 'lru');
      }
    }
    this.#map.set(key, { value, expiresAt });
    return this;
  }

  /** Remove `key`. Returns true if a live entry was removed. */
  delete(key) {
    const entry = this.#map.get(key);
    if (entry === undefined) return false;
    this.#map.delete(key);
    return this.#now() < entry.expiresAt;
  }

  clear() {
    this.#map.clear();
  }

  /** Remove all expired entries; returns how many were removed. */
  prune() {
    return this.#removeExpired(this.#now());
  }

  #live() {
    const t = this.#now();
    return [...this.#map].filter(([, e]) => t < e.expiresAt).reverse();
  }

  /** Live keys, most recently used first. */
  keys() {
    return this.#live().map(([k]) => k);
  }

  /** Live [key, value] pairs, most recently used first. */
  entries() {
    return this.#live().map(([k, e]) => [k, e.value]);
  }
}
