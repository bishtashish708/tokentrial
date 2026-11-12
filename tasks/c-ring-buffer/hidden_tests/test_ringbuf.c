/* Unit tests for ringbuf and linereader. Run with `make test`. */
#include <stdio.h>
#include <string.h>

#include "linereader.h"
#include "ringbuf.h"

static int failures = 0;
static int checks = 0;

#define CHECK(cond)                                                              \
    do {                                                                         \
        checks++;                                                                \
        if (!(cond)) {                                                           \
            failures++;                                                          \
            fprintf(stderr, "%s:%d: %s: CHECK(%s) failed\n", __FILE__, __LINE__, \
                    __func__, #cond);                                            \
        }                                                                        \
    } while (0)

#define CHECK_EQ(a, b)                                                                 \
    do {                                                                               \
        unsigned long va_ = (unsigned long)(a), vb_ = (unsigned long)(b);              \
        checks++;                                                                      \
        if (va_ != vb_) {                                                              \
            failures++;                                                                \
            fprintf(stderr, "%s:%d: %s: %s == %lu, expected %s == %lu\n", __FILE__,    \
                    __LINE__, __func__, #a, va_, #b, vb_);                             \
        }                                                                              \
    } while (0)

static const uint8_t *B(const char *s)
{
    return (const uint8_t *)s;
}

static void test_create(void)
{
    ringbuf_t *rb = rb_create(0);
    CHECK(rb == NULL);
    rb = rb_create(8);
    CHECK(rb != NULL);
    CHECK_EQ(rb_capacity(rb), 8);
    CHECK_EQ(rb_used(rb), 0);
    CHECK_EQ(rb_free(rb), 8);
    rb_destroy(rb);
    rb_destroy(NULL);
}

static void test_write_read_basic(void)
{
    uint8_t out[16];
    ringbuf_t *rb = rb_create(10);

    CHECK_EQ(rb_write(rb, B("hello"), 5), 5);
    CHECK_EQ(rb_used(rb), 5);
    CHECK_EQ(rb_free(rb), 5);
    CHECK_EQ(rb_read(rb, out, 3), 3);
    CHECK(memcmp(out, "hel", 3) == 0);
    CHECK_EQ(rb_read(rb, out, 16), 2);
    CHECK(memcmp(out, "lo", 2) == 0);
    CHECK_EQ(rb_read(rb, out, 4), 0);
    CHECK_EQ(rb_used(rb), 0);
    rb_destroy(rb);
}

static void test_fill_to_capacity(void)
{
    uint8_t out[8];
    ringbuf_t *rb = rb_create(8);

    CHECK_EQ(rb_write(rb, B("abcdefgh"), 8), 8);
    CHECK_EQ(rb_used(rb), 8);
    CHECK_EQ(rb_free(rb), 0);
    CHECK_EQ(rb_write(rb, B("x"), 1), 0);
    CHECK_EQ(rb_read(rb, out, 8), 8);
    CHECK(memcmp(out, "abcdefgh", 8) == 0);
    CHECK_EQ(rb_used(rb), 0);
    rb_destroy(rb);
}

static void test_partial_write(void)
{
    uint8_t out[8];
    ringbuf_t *rb = rb_create(6);

    CHECK_EQ(rb_write(rb, B("abcd"), 4), 4);
    CHECK_EQ(rb_write(rb, B("WXYZ"), 4), 2);
    CHECK_EQ(rb_read(rb, out, 8), 6);
    CHECK(memcmp(out, "abcdWX", 6) == 0);
    rb_destroy(rb);
}

static void test_wrap_and_peek(void)
{
    uint8_t out[8];
    ringbuf_t *rb = rb_create(7);

    rb_write(rb, B("01234"), 5);
    CHECK_EQ(rb_skip(rb, 4), 4);
    CHECK_EQ(rb_write(rb, B("56789"), 5), 5); /* wraps around the end of storage */
    CHECK_EQ(rb_used(rb), 6);
    CHECK_EQ(rb_peek(rb, 0, out, 8), 6);
    CHECK(memcmp(out, "456789", 6) == 0);
    CHECK_EQ(rb_peek(rb, 2, out, 3), 3);
    CHECK(memcmp(out, "678", 3) == 0);
    CHECK_EQ(rb_peek(rb, 6, out, 3), 0);
    CHECK_EQ(rb_used(rb), 6);
    rb_destroy(rb);
}

static void test_find(void)
{
    size_t pos = 99;
    ringbuf_t *rb = rb_create(16);

    rb_write(rb, B("abc\ndef\n"), 8);
    CHECK(rb_find(rb, '\n', 0, &pos) == 1);
    CHECK_EQ(pos, 3);
    CHECK(rb_find(rb, '\n', 4, &pos) == 1);
    CHECK_EQ(pos, 7);
    pos = 99;
    CHECK(rb_find(rb, 'z', 0, &pos) == 0);
    CHECK_EQ(pos, 99);
    CHECK(rb_find(rb, 'a', 8, &pos) == 0);
    rb_destroy(rb);
}

static void test_overwrite_small(void)
{
    uint8_t out[8];
    ringbuf_t *rb = rb_create(5);

    rb_write(rb, B("abc"), 3);
    CHECK_EQ(rb_write_overwrite(rb, B("XY"), 2), 0);
    CHECK_EQ(rb_write_overwrite(rb, B("Z!"), 2), 2);
    CHECK_EQ(rb_used(rb), 5);
    CHECK_EQ(rb_read(rb, out, 8), 5);
    CHECK(memcmp(out, "cXYZ!", 5) == 0);
    rb_destroy(rb);
}

static void test_linereader(void)
{
    char line[16];
    linereader_t *lr = lr_create(10);

    CHECK_EQ(lr_feed(lr, "one\ntwo\r\nth", 11), 11);
    CHECK_EQ(lr_next(lr, line, sizeof line), 3);
    CHECK(strcmp(line, "one") == 0);
    CHECK_EQ(lr_next(lr, line, sizeof line), 3);
    CHECK(strcmp(line, "two") == 0);
    /* the rest of "three" and "four" wrap around the end of the reader's buffer */
    CHECK_EQ(lr_feed(lr, "ree\nfour\n", 9), 9);
    CHECK_EQ(lr_next(lr, line, sizeof line), 5);
    CHECK(strcmp(line, "three") == 0);
    CHECK_EQ(lr_next(lr, line, sizeof line), 4);
    CHECK(strcmp(line, "four") == 0);
    CHECK(lr_next(lr, line, sizeof line) == LR_AGAIN);
    CHECK_EQ(lr_pending(lr), 0);
    lr_destroy(lr);
}

static void test_linereader_too_long(void)
{
    char line[8];
    linereader_t *lr = lr_create(4);

    CHECK_EQ(lr_feed(lr, "abcdefg\nhi\n", 11), 5);
    CHECK(lr_next(lr, line, sizeof line) == LR_TOO_LONG);
    CHECK_EQ(lr_pending(lr), 0);
    CHECK_EQ(lr_feed(lr, "fg\nhi\n", 6), 5);
    CHECK_EQ(lr_next(lr, line, sizeof line), 2);
    CHECK(strcmp(line, "fg") == 0);
    CHECK(lr_next(lr, line, sizeof line) == LR_AGAIN);
    CHECK_EQ(lr_feed(lr, "\n", 1), 1);
    CHECK_EQ(lr_next(lr, line, sizeof line), 2);
    CHECK(strcmp(line, "hi") == 0);
    lr_destroy(lr);
}

int main(void)
{
    test_create();
    test_write_read_basic();
    test_fill_to_capacity();
    test_partial_write();
    test_wrap_and_peek();
    test_find();
    test_overwrite_small();
    test_linereader();
    test_linereader_too_long();

    if (failures) {
        fprintf(stderr, "%d of %d checks failed\n", failures, checks);
        return 1;
    }
    printf("all %d checks passed\n", checks);
    return 0;
}
