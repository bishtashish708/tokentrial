# csvkit

A tiny, dependency-free CSV reader/writer (`src/csv.js`) plus a few reporting helpers
(`src/report.js`) and a command-line summariser (`src/cli.js`).

```js
import { parse, stringify, CsvError } from './src/csv.js';

parse('name,notes\r\nAda,"likes ""tea"", cake"\r\n');
// [['name', 'notes'], ['Ada', 'likes "tea", cake']]
```

The exact behaviour, including error messages, is defined in [SPEC.md](SPEC.md).

```sh
npm test                                   # or: node --test test/csv.test.js test/report.test.js
node src/cli.js data/sales.csv region units
```
