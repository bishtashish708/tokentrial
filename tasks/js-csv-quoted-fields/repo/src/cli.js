#!/usr/bin/env node
// Usage: node src/cli.js FILE GROUP_COLUMN VALUE_COLUMN [--delimiter=;]
import { readFileSync } from 'node:fs';
import { loadTable, summarize, renderSummary } from './report.js';
import { CsvError } from './csv.js';

function main(argv) {
  const opts = {};
  const args = [];
  for (const a of argv) {
    if (a.startsWith('--delimiter=')) opts.delimiter = a.slice('--delimiter='.length);
    else args.push(a);
  }
  if (args.length !== 3) {
    process.stderr.write('usage: cli.js FILE GROUP_COLUMN VALUE_COLUMN [--delimiter=X]\n');
    return 2;
  }
  const [file, group, value] = args;
  try {
    const { rows } = loadTable(readFileSync(file, 'utf8'), opts);
    process.stdout.write(renderSummary(summarize(rows, group, value), group, value, opts));
    return 0;
  } catch (err) {
    if (err instanceof CsvError) {
      process.stderr.write(`${file}:${err.line}: ${err.message}\n`);
      return 1;
    }
    throw err;
  }
}

process.exitCode = main(process.argv.slice(2));
