/* ringbuf.c - fixed-capacity byte FIFO. See SPEC.md. */
#include "ringbuf.h"

#include <stdlib.h>
#include <string.h>

struct ringbuf {
    uint8_t *buf;
    size_t cap;
    size_t head;  /* storage index of the oldest byte */
    size_t count; /* bytes stored; distinguishes full (count == cap) from empty */
};

ringbuf_t *rb_create(size_t capacity)
{
    ringbuf_t *rb;

    if (capacity == 0)
        return NULL;
    rb = malloc(sizeof *rb);
    if (rb == NULL)
        return NULL;
    rb->buf = calloc(capacity, 1);
    if (rb->buf == NULL) {
        free(rb);
        return NULL;
    }
    rb->cap = capacity;
    rb->head = 0;
    rb->count = 0;
    return rb;
}

void rb_destroy(ringbuf_t *rb)
{
    if (rb == NULL)
        return;
    free(rb->buf);
    free(rb);
}

void rb_clear(ringbuf_t *rb)
{
    rb->head = 0;
    rb->count = 0;
}

size_t rb_capacity(const ringbuf_t *rb)
{
    return rb->cap;
}

size_t rb_used(const ringbuf_t *rb)
{
    return rb->count;
}

size_t rb_free(const ringbuf_t *rb)
{
    return rb->cap - rb->count;
}

static size_t tail_index(const ringbuf_t *rb)
{
    return (rb->head + rb->count) % rb->cap;
}

/* Copy k bytes out of storage starting at storage index `start`, wrapping as needed. */
static void copy_out(const ringbuf_t *rb, size_t start, uint8_t *dst, size_t k)
{
    size_t first;

    if (k == 0)
        return;
    first = rb->cap - start;
    if (first > k)
        first = k;
    memcpy(dst, rb->buf + start, first);
    if (k > first)
        memcpy(dst + first, rb->buf, k - first);
}

/* Copy k bytes into storage starting at storage index `start`, wrapping as needed. */
static void copy_in(ringbuf_t *rb, size_t start, const uint8_t *src, size_t k)
{
    size_t first;

    if (k == 0)
        return;
    first = rb->cap - start;
    if (first > k)
        first = k;
    memcpy(rb->buf + start, src, first);
    if (k > first)
        memcpy(rb->buf, src + first, k - first);
}

size_t rb_write(ringbuf_t *rb, const uint8_t *src, size_t n)
{
    size_t k = rb_free(rb);

    if (n < k)
        k = n;
    copy_in(rb, tail_index(rb), src, k);
    rb->count += k;
    return k;
}

size_t rb_write_overwrite(ringbuf_t *rb, const uint8_t *src, size_t n)
{
    size_t total = rb->count + n;
    size_t dropped = total > rb->cap ? total - rb->cap : 0;

    if (n >= rb->cap) {
        /* Everything stored is dropped, plus all but the last cap bytes of src. */
        rb->head = 0;
        rb->count = 0;
        src += n - rb->cap;
        n = rb->cap;
    } else if (n > rb_free(rb)) {
        rb_skip(rb, n - rb_free(rb));
    }
    rb_write(rb, src, n);
    return dropped;
}

size_t rb_read(ringbuf_t *rb, uint8_t *dst, size_t n)
{
    size_t k = rb->count;

    if (n < k)
        k = n;
    copy_out(rb, rb->head, dst, k);
    rb->head = (rb->head + k) % rb->cap;
    rb->count -= k;
    return k;
}

size_t rb_peek(const ringbuf_t *rb, size_t offset, uint8_t *dst, size_t n)
{
    size_t k;

    if (offset >= rb->count)
        return 0;
    k = rb->count - offset;
    if (n < k)
        k = n;
    copy_out(rb, (rb->head + offset) % rb->cap, dst, k);
    return k;
}

size_t rb_skip(ringbuf_t *rb, size_t n)
{
    size_t k = rb->count;

    if (n < k)
        k = n;
    rb->head = (rb->head + k) % rb->cap;
    rb->count -= k;
    return k;
}

int rb_find(const ringbuf_t *rb, uint8_t byte, size_t from, size_t *pos)
{
    size_t start, remaining, run;
    const uint8_t *hit;

    if (from >= rb->count)
        return 0;

    /* Search the contiguous run up to the end of storage first, then the wrapped part. */
    start = (rb->head + from) % rb->cap;
    remaining = rb->count - from;
    run = rb->cap - start;
    if (run > remaining)
        run = remaining;

    hit = memchr(rb->buf + start, byte, run);
    if (hit != NULL) {
        *pos = from + (size_t)(hit - (rb->buf + start));
        return 1;
    }
    hit = memchr(rb->buf, byte, remaining - run);
    if (hit != NULL) {
        *pos = from + run + (size_t)(hit - rb->buf);
        return 1;
    }
    return 0;
}
