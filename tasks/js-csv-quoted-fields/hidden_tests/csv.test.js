import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { parse, stringify, CsvError } from '../src/csv.js';

describe('parse: basics', () => {
  test('simple records', () => {
    assert.deepEqual(parse('a,b,c\n1,2,3\n'), [['a', 'b', 'c'], ['1', '2', '3']]);
  });
  test('empty input', () => {
    assert.deepEqual(parse(''), []);
  });
  test('final record without a line break', () => {
    assert.deepEqual(parse('a,b\nc,d'), [['a', 'b'], ['c', 'd']]);
  });
  test('empty fields', () => {
    assert.deepEqual(parse(',a,\n,,'), [['', 'a', ''], ['', '', '']]);
  });
  test('CRLF record endings', () => {
    assert.deepEqual(parse('x,y\r\n1,2\r\n'), [['x', 'y'], ['1', '2']]);
  });
  test('blank line is a record with zero fields', () => {
    assert.deepEqual(parse('a\n\nb\n'), [['a'], [], ['b']]);
  });
  test('quote inside an unquoted field is literal', () => {
    assert.deepEqual(parse('5" pipe,x'), [['5" pipe', 'x']]);
  });
});

describe('parse: quoted fields', () => {
  test('embedded delimiter', () => {
    assert.deepEqual(parse('"a,b",c\n'), [['a,b', 'c']]);
  });
  test('doubled quote is an escaped quote', () => {
    assert.deepEqual(parse('"say ""hi""",x\n'), [['say "hi"', 'x']]);
  });
  test('field that is only an escaped quote', () => {
    assert.deepEqual(parse('"""",z'), [['"', 'z']]);
  });
  test('newline inside a quoted field', () => {
    assert.deepEqual(parse('"line1\nline2",b\n'), [['line1\nline2', 'b']]);
  });
  test('CRLF inside a quoted field is kept verbatim', () => {
    assert.deepEqual(parse('id,note\r\n1,"two\r\nlines"\r\n'), [
      ['id', 'note'],
      ['1', 'two\r\nlines'],
    ]);
  });
  test('empty quoted field', () => {
    assert.deepEqual(parse('"",x\n'), [['', 'x']]);
  });
});

describe('parse: errors', () => {
  test('unterminated quoted field', () => {
    assert.throws(() => parse('a,b\n"open,c\n'), (err) => {
      assert.ok(err instanceof CsvError);
      assert.equal(err.message, 'Unterminated quoted field at line 2');
      assert.equal(err.line, 2);
      return true;
    });
  });
  test('garbage after closing quote', () => {
    assert.throws(() => parse('"ab"c,d\n'), {
      name: 'CsvError',
      message: 'Unexpected character after closing quote at line 1',
    });
  });
});

describe('options', () => {
  test('semicolon delimiter', () => {
    assert.deepEqual(parse('a;"b;c"\n1;2', { delimiter: ';' }), [['a', 'b;c'], ['1', '2']]);
  });
  test('invalid delimiter', () => {
    assert.throws(() => parse('a', { delimiter: '"' }), TypeError);
    assert.throws(() => parse('a', { delimiter: ';;' }), TypeError);
  });
});

describe('stringify', () => {
  test('quotes only when needed', () => {
    assert.equal(
      stringify([['a', 'b,c', 'say "hi"'], ['multi\nline', '', 'x']]),
      'a,"b,c","say ""hi"""\r\n"multi\nline",,x\r\n',
    );
  });
  test('lone empty field vs empty record', () => {
    assert.equal(stringify([[''], []]), '""\r\n\r\n');
  });
  test('round trip', () => {
    const records = [['id', 'text'], ['1', 'a "quoted", multi\r\nline value'], [''], []];
    assert.deepEqual(parse(stringify(records)), records);
  });
});
