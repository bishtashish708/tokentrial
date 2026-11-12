# lrucache

A small, dependency-free least-recently-used cache for Node.

```js
import { LRUCache, memoize } from './src/index.js';

const cache = new LRUCache({ maxSize: 2, onEvict: (k, v, why) => console.log(k, v, why) });
cache.set('a', 1).set('b', 2);
cache.get('a');
cache.set('c', 3); // logs: b 2 lru
cache.keys();      // ['c', 'a']
```

Behaviour is specified in [SPEC.md](SPEC.md). Run the tests with `npm test`
(`node --test test/lru.test.js test/ttl.test.js test/memoize.test.js`).

## Roadmap

- Per-entry TTL with an injectable clock (see the **(new)** parts of SPEC.md).
