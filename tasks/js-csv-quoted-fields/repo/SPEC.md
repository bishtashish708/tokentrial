# csvkit specification

This document is normative. `src/csv.js` must implement it exactly.

## Terms

- **Delimiter**: the field separator, `,` by default (see *Options*).
- **Line break**: any of the three sequences `\r\n` (CRLF), `\n` (LF) or `\r` (a CR that is
  not immediately followed by LF). A CRLF is always one line break, never two.
- **Physical line**: the input split at every line break, *including line breaks that appear
  inside quoted fields*. Physical lines are numbered from 1. The physical line of a character
  is 1 plus the number of line breaks that end before it.

## `parse(text, options?)`

Returns an array of records; each record is an array of strings.

### Records

1. The empty string parses to `[]` (no records).
2. A line break outside a quoted field ends the current record.
3. A line break at the very end of the input ends the last record; it does **not** start a
   new, empty record. So `"a,b\n"` and `"a,b"` both parse to `[["a", "b"]]`.
4. A record with no characters at all (two line breaks in a row, or a line break at the very
   start of the input) is a record with **zero** fields: `"a\n\nb"` parses to
   `[["a"], [], ["b"]]` and `"\n"` parses to `[[]]`.
5. The final record does not need a line break after it, and it is kept whatever its content,
   including a single empty field: `"a\n\"\""` parses to `[["a"], [""]]`.

### Fields

6. Within a record, fields are separated by the delimiter. A record of `n` delimiters
   has `n + 1` fields; empty fields are empty strings: `",a,"` is `["", "a", ""]`.
7. A field is **quoted** if and only if its very first character is `"`. Otherwise it is
   **unquoted**, and runs up to the next delimiter, line break or end of input. Inside an
   unquoted field `"` is an ordinary character: `a"b` is the field `a"b`, and ` "x"` (leading
   space) is the field ` "x"`.
8. A quoted field runs from its opening `"` to the matching closing `"`. Between them:
   - `""` stands for one literal `"` character;
   - every other character, including the delimiter, `\r` and `\n`, is literal and kept
     exactly as written. In particular a CRLF inside a quoted field stays `\r\n` and a lone
     CR stays `\r`; no line-ending normalisation is ever applied to field contents.
   The field's value is the text between the quotes with each `""` replaced by `"`.
9. After the closing quote, the next character must be the delimiter, a line break, or the
   end of input.

### Errors

Errors are reported by throwing a `CsvError` (exported from `src/csv.js`, a subclass of
`Error`) whose `message` is exactly one of the following and whose `line` property is the
number `N` used in the message:

- `Unterminated quoted field at line N`: the input ends inside a quoted field. `N` is the
  physical line of the field's **opening** quote.
- `Unexpected character after closing quote at line N`: rule 9 is violated. `N` is the
  physical line of the offending character.

Parsing reads the input from start to end and throws at the first violation; nothing is
returned in that case.

## `stringify(records, options?)`

Returns the CSV text for an array of records (arrays of strings).

- Fields are joined with the delimiter, and **every** record, including the last, is followed
  by `\r\n`. A record with zero fields is written as just `\r\n`.
- A field is written quoted if and only if it contains the delimiter, `"`, `\r` or `\n`, or
  it is the only field of its record and is empty (so `[""]` is written as `""\r\n`, which
  keeps it distinct from `[]`). A quoted field is written as `"`, the value with every `"`
  doubled, `"`. All other fields are written as is.

For any records, `parse(stringify(records, o), o)` deep-equals `records`.

## Options

Both functions accept an optional object `{ delimiter }`. `delimiter` defaults to `,` and
must be a string of exactly one character that is not `"`, `\r` or `\n`; anything else throws
a `TypeError` before any input is read.
