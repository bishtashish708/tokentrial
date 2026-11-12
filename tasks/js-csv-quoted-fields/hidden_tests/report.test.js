import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { loadTable, summarize, renderSummary, filterRows } from '../src/report.js';

const SALES = readFileSync(fileURLToPath(new URL('../data/sales.csv', import.meta.url)), 'utf8');

test('loadTable skips blank records and keys rows by header', () => {
  const { columns, rows } = loadTable(SALES);
  assert.deepEqual(columns, ['region', 'product', 'units', 'notes']);
  assert.equal(rows.length, 5);
  assert.equal(rows[0].notes, 'first order, paid');
  assert.equal(rows[1].notes, '');
});

test('summarize units per region', () => {
  const { rows } = loadTable(SALES);
  assert.deepEqual(summarize(rows, 'region', 'units'), [
    { group: 'east', total: 7 },
    { group: 'north', total: 15 },
    { group: 'south', total: 14 },
  ]);
});

test('renderSummary writes CSV', () => {
  const summary = [{ group: 'a,b', total: 3 }];
  assert.equal(renderSummary(summary, 'region', 'units'), 'region,total_units\r\n"a,b",3\r\n');
});

test('filterRows is case-insensitive', () => {
  const { rows } = loadTable(SALES);
  assert.deepEqual(filterRows(rows, 'notes', 'CALL').map((r) => r.region), ['north']);
});

test('loadTable rejects ragged rows', () => {
  assert.throws(() => loadTable('a,b\n1\n'), /row 1: expected 2 fields, got 1/);
});
