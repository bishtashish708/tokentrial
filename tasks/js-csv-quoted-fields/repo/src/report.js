// Small reporting helpers built on top of csv.js.
import { parse, stringify } from './csv.js';

/**
 * Parse CSV text with a header row into objects keyed by column name.
 * Records with zero fields (blank lines) are skipped. A data record whose
 * field count differs from the header's is an error.
 */
export function loadTable(text, options = {}) {
  const records = parse(text, options).filter((r) => r.length > 0);
  if (records.length === 0) return { columns: [], rows: [] };
  const [columns, ...data] = records;
  const rows = data.map((record, idx) => {
    if (record.length !== columns.length) {
      throw new Error(
        `row ${idx + 1}: expected ${columns.length} fields, got ${record.length}`,
      );
    }
    return Object.fromEntries(columns.map((c, j) => [c, record[j]]));
  });
  return { columns, rows };
}

/** Sum `valueColumn` (parsed as a number) per distinct value of `groupColumn`. */
export function summarize(rows, groupColumn, valueColumn) {
  const totals = new Map();
  for (const row of rows) {
    const key = row[groupColumn];
    const value = Number(row[valueColumn]);
    if (!Number.isFinite(value)) {
      throw new Error(`non-numeric ${valueColumn}: ${JSON.stringify(row[valueColumn])}`);
    }
    totals.set(key, (totals.get(key) ?? 0) + value);
  }
  return [...totals.entries()]
    .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
    .map(([group, total]) => ({ group, total }));
}

/** Render a summary as CSV with a header row. */
export function renderSummary(summary, groupColumn, valueColumn, options = {}) {
  const records = [[groupColumn, `total_${valueColumn}`]];
  for (const { group, total } of summary) records.push([group, String(total)]);
  return stringify(records, options);
}

/** Rows whose `column` contains `needle` (case-insensitive). */
export function filterRows(rows, column, needle) {
  const n = needle.toLowerCase();
  return rows.filter((row) => String(row[column] ?? '').toLowerCase().includes(n));
}
