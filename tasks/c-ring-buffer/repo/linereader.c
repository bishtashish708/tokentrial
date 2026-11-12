/* linereader.c - newline-framed reader on top of ringbuf. See linereader.h. */
#include "linereader.h"

#include <stdlib.h>

#include "ringbuf.h"

struct linereader {
    ringbuf_t *rb;
    size_t max_line;
    size_t scanned; /* leading buffered bytes already known to contain no '\n' */
};

linereader_t *lr_create(size_t max_line)
{
    linereader_t *lr;

    if (max_line == 0)
        return NULL;
    lr = malloc(sizeof *lr);
    if (lr == NULL)
        return NULL;
    /* Room for the longest line plus its '\n'. */
    lr->rb = rb_create(max_line + 1);
    if (lr->rb == NULL) {
        free(lr);
        return NULL;
    }
    lr->max_line = max_line;
    lr->scanned = 0;
    return lr;
}

void lr_destroy(linereader_t *lr)
{
    if (lr == NULL)
        return;
    rb_destroy(lr->rb);
    free(lr);
}

size_t lr_feed(linereader_t *lr, const char *data, size_t n)
{
    return rb_write(lr->rb, (const uint8_t *)data, n);
}

long lr_next(linereader_t *lr, char *out, size_t outsz)
{
    size_t nl, len;

    if (!rb_find(lr->rb, (uint8_t)'\n', lr->scanned, &nl)) {
        lr->scanned = rb_used(lr->rb);
        if (rb_free(lr->rb) == 0) {
            rb_clear(lr->rb);
            lr->scanned = 0;
            return LR_TOO_LONG;
        }
        return LR_AGAIN;
    }

    len = nl;
    if (len >= outsz)
        len = outsz - 1;
    rb_peek(lr->rb, 0, (uint8_t *)out, len);
    rb_skip(lr->rb, nl + 1);
    lr->scanned = 0;
    if (len > 0 && out[len - 1] == '\r')
        len--;
    out[len] = '\0';
    return (long)len;
}

size_t lr_pending(const linereader_t *lr)
{
    return rb_used(lr->rb);
}
