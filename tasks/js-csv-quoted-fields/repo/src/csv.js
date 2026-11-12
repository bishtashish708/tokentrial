// csvkit: a small RFC 4180-style CSV reader and writer. See SPEC.md.

export class CsvError extends Error {
  constructor(message, line) {
    super(message);
    this.name = 'CsvError';
    this.line = line;
  }
}

function checkDelimiter(delimiter) {
  if (delimiter === undefined) return ',';
  if (typeof delimiter !== 'string' || delimiter.length !== 1 || '"\r\n'.includes(delimiter)) {
    throw new TypeError(`invalid delimiter: ${JSON.stringify(delimiter)}`);
  }
  return delimiter;
}

/**
 * Parse CSV text into an array of records (arrays of strings).
 * @param {string} text
 * @param {{delimiter?: string}} [options]
 * @returns {string[][]}
 */
export function parse(text, options = {}) {
  const delimiter = checkDelimiter(options.delimiter);
  // Windows files: treat CRLF the same as LF.
  const src = text.replace(/\r\n/g, '\n');

  const records = [];
  let record = [];
  let field = '';
  let inQuotes = false;
  let quoted = false; // the current field started with a quote
  let quoteLine = 0;

  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (inQuotes) {
      if (c === '"') {
        if (src[i + 1] === '"') {
          field += '"'; // escaped quote
        } else {
          inQuotes = false;
          const next = src[i + 1];
          if (next !== undefined && next !== delimiter && next !== '\n' && next !== '\r') {
            const line = records.length + 1;
            throw new CsvError(`Unexpected character after closing quote at line ${line}`, line);
          }
        }
      } else {
        field += c;
      }
    } else if (c === '"' && field === '' && !quoted) {
      inQuotes = true;
      quoted = true;
      quoteLine = records.length + 1;
    } else if (c === delimiter) {
      record.push(field);
      field = '';
      quoted = false;
    } else if (c === '\n' || c === '\r') {
      if (record.length === 0 && field === '' && !quoted) {
        records.push([]); // blank line
      } else {
        record.push(field);
        records.push(record);
      }
      record = [];
      field = '';
      quoted = false;
    } else {
      field += c;
    }
  }

  if (inQuotes) {
    throw new CsvError(`Unterminated quoted field at line ${quoteLine}`, quoteLine);
  }
  if (field !== '' || record.length > 0) {
    record.push(field);
    records.push(record);
  }
  return records;
}

function quoteField(field, delimiter, alone) {
  const needs =
    field.includes(delimiter) ||
    field.includes('"') ||
    field.includes('\r') ||
    field.includes('\n') ||
    (alone && field === '');
  return needs ? `"${field.replaceAll('"', '""')}"` : field;
}

/**
 * Serialise records to CSV text. Every record ends with CRLF.
 * @param {string[][]} records
 * @param {{delimiter?: string}} [options]
 * @returns {string}
 */
export function stringify(records, options = {}) {
  const delimiter = checkDelimiter(options.delimiter);
  let out = '';
  for (const record of records) {
    const alone = record.length === 1;
    out += record.map((f) => quoteField(String(f), delimiter, alone)).join(delimiter);
    out += '\r\n';
  }
  return out;
}
