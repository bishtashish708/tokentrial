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
  const n = text.length;
  const records = [];
  let i = 0;
  let line = 1;

  const isBreak = (c) => c === '\n' || c === '\r';
  // Consume the line break at i (CRLF counts as one).
  const skipBreak = () => {
    if (text[i] === '\r' && text[i + 1] === '\n') i += 2;
    else i += 1;
    line += 1;
  };

  while (i < n) {
    if (isBreak(text[i])) {
      records.push([]);
      skipBreak();
      continue;
    }
    const record = [];
    for (;;) {
      let field = '';
      if (text[i] === '"') {
        const openLine = line;
        i += 1;
        for (;;) {
          if (i >= n) {
            throw new CsvError(`Unterminated quoted field at line ${openLine}`, openLine);
          }
          const c = text[i];
          if (c === '"') {
            if (text[i + 1] === '"') {
              field += '"';
              i += 2;
              continue;
            }
            i += 1;
            break;
          }
          if (c === '\r' && text[i + 1] === '\n') {
            field += '\r\n';
            i += 2;
            line += 1;
            continue;
          }
          if (isBreak(c)) line += 1;
          field += c;
          i += 1;
        }
        if (i < n && text[i] !== delimiter && !isBreak(text[i])) {
          throw new CsvError(`Unexpected character after closing quote at line ${line}`, line);
        }
      } else {
        while (i < n && text[i] !== delimiter && !isBreak(text[i])) {
          field += text[i];
          i += 1;
        }
      }
      record.push(field);
      if (i < n && text[i] === delimiter) {
        i += 1;
        continue; // another field follows (possibly empty, even at end of input)
      }
      break;
    }
    records.push(record);
    if (i < n) skipBreak();
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
