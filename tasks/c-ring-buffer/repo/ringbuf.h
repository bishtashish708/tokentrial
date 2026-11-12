/* ringbuf.h - fixed-capacity byte FIFO. See SPEC.md for the exact contract. */
#ifndef RINGBUF_H
#define RINGBUF_H

#include <stddef.h>
#include <stdint.h>

typedef struct ringbuf ringbuf_t;

ringbuf_t *rb_create(size_t capacity);
void rb_destroy(ringbuf_t *rb);
void rb_clear(ringbuf_t *rb);

size_t rb_capacity(const ringbuf_t *rb);
size_t rb_used(const ringbuf_t *rb);
size_t rb_free(const ringbuf_t *rb);

size_t rb_write(ringbuf_t *rb, const uint8_t *src, size_t n);
size_t rb_write_overwrite(ringbuf_t *rb, const uint8_t *src, size_t n);

size_t rb_read(ringbuf_t *rb, uint8_t *dst, size_t n);
size_t rb_peek(const ringbuf_t *rb, size_t offset, uint8_t *dst, size_t n);
size_t rb_skip(ringbuf_t *rb, size_t n);

int rb_find(const ringbuf_t *rb, uint8_t byte, size_t from, size_t *pos);

#endif /* RINGBUF_H */
