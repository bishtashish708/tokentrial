/** Split `items` into consecutive groups of `size`. The last group may be shorter. */
export function chunk(items, size) {
  if (!Number.isInteger(size) || size < 1) throw new RangeError('size must be a positive integer');
  const out = [];
  for (let i = 0; i + size <= items.length; i += size) {
    out.push(items.slice(i, i + size));
  }
  return out;
}

/** Shorten `s` to at most `max` characters, ending with an ellipsis if cut. */
export function truncate(s, max) {
  if (s.length <= max) return s;
  return s.slice(0, Math.max(0, max - 1)) + '…';
}

/** Greedy word wrap to lines of at most `width` characters (long words kept whole). */
export function wrap(text, width) {
  const words = text.split(/\s+/).filter(Boolean);
  const lines = [];
  let line = '';
  for (const w of words) {
    if (!line) line = w;
    else if (line.length + 1 + w.length <= width) line += ' ' + w;
    else { lines.push(line); line = w; }
  }
  if (line) lines.push(line);
  return lines;
}

/** Wrap text and group the lines into pages of `perPage` lines. */
export function paginate(text, width, perPage) {
  return chunk(wrap(text, width), perPage);
}
