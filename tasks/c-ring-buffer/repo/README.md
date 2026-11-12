# ringbuf

A tiny fixed-capacity byte FIFO for buffering stream input, plus a newline-framed reader
that sits on top of it.

- `ringbuf.c`, `ringbuf.h` – the ring buffer (contract in `SPEC.md`)
- `linereader.c`, `linereader.h` – splits a byte stream into lines using `rb_find`/`rb_peek`
- `examples/linestat.c` – reads stdin in 7-byte chunks and prints line statistics
- `tests/test_ringbuf.c` – unit tests

```
make test                       # build and run the unit tests
make && ./build/linestat 120 < SPEC.md
```

Plain C11, no dependencies; builds with clang and gcc.
