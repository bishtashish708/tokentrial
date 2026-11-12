# ringbuf specification

`ringbuf` is a fixed-capacity FIFO of bytes. All functions are declared in `ringbuf.h`.
Bytes are addressed by **logical position**: position 0 is the oldest byte currently stored
(the next byte `rb_read` would return), position `rb_used(rb) - 1` the newest. Logical
positions never depend on where the bytes happen to sit in the underlying storage; once
data wraps around the end of the storage everything below must behave exactly as if it
had not.

## Lifetime

- `ringbuf_t *rb_create(size_t capacity)` returns a new, empty buffer that can hold
  **exactly `capacity` bytes** at once (not `capacity - 1`). Returns `NULL` if
  `capacity == 0` or allocation fails.
- `void rb_destroy(ringbuf_t *rb)` frees it. `rb_destroy(NULL)` does nothing.
- `void rb_clear(ringbuf_t *rb)` discards all stored bytes. Capacity is unchanged.

## Queries

- `size_t rb_capacity(const ringbuf_t *rb)` — the `capacity` given to `rb_create`.
- `size_t rb_used(const ringbuf_t *rb)` — number of bytes stored, `0 <= used <= capacity`.
- `size_t rb_free(const ringbuf_t *rb)` — `capacity - used`.

`rb_used` is `capacity` immediately after writing `capacity` bytes into an empty buffer,
and `0` after reading them all back. A full buffer and an empty buffer are never confused.

## Writing

- `size_t rb_write(ringbuf_t *rb, const uint8_t *src, size_t n)`
  Appends `k = min(n, rb_free(rb))` bytes, namely `src[0..k-1]`, after the newest byte and
  returns `k`. It never overwrites stored data, so a write into a nearly full buffer is
  partial and a write into a full buffer returns 0.

- `size_t rb_write_overwrite(ringbuf_t *rb, const uint8_t *src, size_t n)`
  Appends all `n` bytes, discarding the **oldest** bytes as needed so that at most
  `capacity` bytes remain. The result is exactly as if the `n` bytes were appended one at a
  time, each append first dropping the oldest byte when the buffer is full. In particular,
  if `n >= capacity` the buffer afterwards holds exactly the last `capacity` bytes of `src`.
  Returns the number of bytes that were dropped, counting both previously stored bytes and
  bytes of `src` that did not survive: `max(0, used_before + n - capacity)`.

`n == 0` is allowed for both and changes nothing (returns 0). `src` may be `NULL` only
when `n == 0`.

## Reading

- `size_t rb_read(ringbuf_t *rb, uint8_t *dst, size_t n)`
  Removes the `k = min(n, rb_used(rb))` oldest bytes, copies them to `dst[0..k-1]` in
  order, and returns `k`.

- `size_t rb_peek(const ringbuf_t *rb, size_t offset, uint8_t *dst, size_t n)`
  Copies, without removing anything, the bytes at logical positions
  `offset .. offset + k - 1` to `dst[0..k-1]`, where `k = min(n, rb_used(rb) - offset)`,
  and returns `k`. If `offset >= rb_used(rb)` it copies nothing and returns 0.

- `size_t rb_skip(ringbuf_t *rb, size_t n)`
  Removes the `k = min(n, rb_used(rb))` oldest bytes without copying them; returns `k`.

`dst` may be `NULL` only when `n == 0`.

## Searching

- `int rb_find(const ringbuf_t *rb, uint8_t byte, size_t from, size_t *pos)`
  Looks for `byte` at logical positions `from, from + 1, ..., rb_used(rb) - 1`. If found,
  stores the **logical position** of the first match in `*pos` and returns 1. Otherwise
  returns 0 and leaves `*pos` unchanged (this includes every call with
  `from >= rb_used(rb)`).

## Line reader

`linereader.h` builds a newline-framed reader on top of `ringbuf`; see the comments there.
It only uses the public `ringbuf` API, so it is correct whenever `ringbuf` is.
