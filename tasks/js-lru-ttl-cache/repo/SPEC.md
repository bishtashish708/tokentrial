# lrucache specification

This document is normative. Sections marked **(new)** describe the per-entry TTL feature,
which `src/lru.js` does not implement yet; everything else is existing behaviour that must
keep working unchanged.

## Construction

```js
new LRUCache({ maxSize, ttl, now, onEvict })
```

| Option    | Meaning |
|-----------|---------|
| `maxSize` | Required. Maximum number of **stored** entries; an integer >= 1, otherwise `RangeError`. |
| `ttl`     | **(new)** Optional default time-to-live in milliseconds. `undefined` (the default) means entries never expire. Otherwise it must be a number > 0; `Infinity` is allowed and means "never expires". Anything else (`0`, negatives, `NaN`, non-numbers) throws `RangeError`. |
| `now`     | **(new)** Optional clock: a function returning the current time in milliseconds. Defaults to `Date.now`. The cache calls it whenever it needs the current time and never remembers a value between method calls. |
| `onEvict` | Optional callback `onEvict(key, value, reason)`, called once for every entry the cache removes on its own (see *Removal*). `reason` is `'lru'` or **(new)** `'expired'`. |

## Entries, recency, expiry

- Each stored entry has a key (compared with `SameValueZero`, like `Map`), a value and
  **(new)** an expiry time `expiresAt` (a number, possibly `Infinity`).
- Stored entries are kept in **recency order**, from least recently used (LRU) to most
  recently used (MRU). Only `set` and a `get` that returns a live entry move an entry to the
  MRU end. No other method changes the order.
- **(new)** At time `t`, an entry is **expired** if `t >= expiresAt`, and **live** otherwise.
  An entry written by `set` at time `t` with an effective TTL of `d` gets
  `expiresAt = t + d` (`Infinity` if there is no TTL). The effective TTL is the `ttl` passed
  to that `set` call if it is not `undefined`, else the constructor's `ttl`, else none.
- **(new)** Expired entries are **not** removed the moment they expire. An expired entry stays
  stored until one of the removal points below removes it. While stored, it still counts
  toward `maxSize`, but it is otherwise invisible: it is never returned, counted by `size`, or
  listed by `keys()` / `entries()`.

In each method below, `t` is the value of `now()` at the time of the call.

## Methods

### `set(key, value, options?)` -> `this`

`options.ttl` overrides the default TTL and is validated like the constructor's `ttl`
(`undefined` means "use the default"). Validation happens first: on an invalid TTL, `set`
throws `RangeError` and changes nothing (no removals, no `onEvict` calls). Then:

1. If `key` is stored and live, its value and `expiresAt` are replaced and it becomes MRU.
   Nothing is removed. Done.
2. **(new)** If `key` is stored but expired, that entry is removed (reason `'expired'`) and
   `key` is then inserted as a new key (step 3).
3. Inserting a new key: if the number of stored entries equals `maxSize`, room is made
   first:
   1. **(new)** every stored entry that is expired at `t` is removed (reason `'expired'`), in
      recency order from LRU to MRU;
   2. if the number of stored entries still equals `maxSize`, the LRU entry is removed
      (reason `'lru'`).

   If the cache is not full, nothing is removed at all, even if it holds expired entries.
   The new entry is then stored as MRU.

### `get(key)`

If `key` is not stored, returns `undefined`. **(new)** If its entry is expired, removes it
(reason `'expired'`) and returns `undefined`; recency is not touched. Otherwise the entry
becomes MRU and its value is returned.

### `peek(key)` and `has(key)`

Like `get`, but never change recency: `peek` returns the value (or `undefined`) and `has`
returns `true` for a live entry and `false` otherwise. **(new)** An expired entry looked up
by either is removed (reason `'expired'`).

### `delete(key)`

Removes `key`'s entry if stored, **without** calling `onEvict`. Returns `true` if a **live**
entry was removed, and `false` otherwise (not stored, or **(new)** stored but expired).

### `clear()`

Removes every entry without calling `onEvict`.

### `prune()` **(new)**

Removes every stored entry that is expired at `t`, in recency order from LRU to MRU (reason
`'expired'`), and returns the number of entries removed.

### `size` (getter), `keys()`, `entries()`

`size` is the number of **live** entries. `keys()` returns an array of the live keys and
`entries()` an array of `[key, value]` pairs for the live entries, both ordered from MRU to
LRU. **(new)** None of these remove anything.

### `maxSize` (getter)

The configured `maxSize`.

## Removal

The cache removes an entry on its own (and calls `onEvict(key, value, reason)`, synchronously,
after the entry is gone) only:

- with reason `'lru'`: in `set` step 3.2;
- with reason `'expired'`: in `set` steps 2 and 3.1, in `get`/`peek`/`has` of an expired key,
  and in `prune()`.

`delete`, `clear` and replacing a live key's value in `set` never call `onEvict`.

## `memoize(fn, options)` (src/memoize.js)

Returns a function that caches `fn`'s results in an `LRUCache`, keyed by `options.key(...args)`
(default: the first argument). **(new)** `options.maxSize`, `options.ttl`, `options.now` and
`options.onEvict` are passed to the `LRUCache` constructor, so memoized results expire too.
