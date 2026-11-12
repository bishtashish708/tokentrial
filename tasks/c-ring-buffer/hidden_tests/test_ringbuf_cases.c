/* Hidden test: replays generated operation sequences (see ringbuf_cases.txt). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ringbuf.h"

static int failures = 0;
static long lineno = 0;
static char seqname[64] = "?";

static void fail(const char *what, const char *line)
{
    failures++;
    if (failures <= 40)
        fprintf(stderr, "%s (line %ld): %s: %s", seqname, lineno, what, line);
}

/* Parse hex ("-" = empty) into a freshly allocated buffer; returns length. */
static size_t unhex(const char *s, uint8_t **out)
{
    size_t n = 0, i;
    uint8_t *buf;

    if (strcmp(s, "-") == 0) {
        *out = malloc(1);
        return 0;
    }
    n = strlen(s) / 2;
    buf = malloc(n + 1);
    for (i = 0; i < n; i++) {
        unsigned v;
        sscanf(s + 2 * i, "%2x", &v);
        buf[i] = (uint8_t)v;
    }
    *out = buf;
    return n;
}

int main(int argc, char **argv)
{
    static char line[16384];
    char tok[8192];
    FILE *f;
    ringbuf_t *rb = NULL;
    long ops = 0;

    if (argc != 2) {
        fprintf(stderr, "usage: %s CASES_FILE\n", argv[0]);
        return 2;
    }
    f = fopen(argv[1], "r");
    if (f == NULL) {
        perror(argv[1]);
        return 2;
    }
    while (fgets(line, sizeof line, f) != NULL) {
        unsigned long a1, a2, eu, ef;
        long sfound;
        uint8_t *data, *got;
        size_t n, k;

        lineno++;
        if (line[0] == '#') {
            sscanf(line, "# %63[^\n]", seqname);
            continue;
        }
        ops++;
        switch (line[0]) {
        case 'C':
            rb_destroy(rb);
            sscanf(line, "C %lu", &a1);
            rb = rb_create((size_t)a1);
            if (rb == NULL) {
                fail("rb_create returned NULL", line);
                return 1;
            }
            continue;
        case 'W':
        case 'O':
            sscanf(line + 2, "%8191s %lu %lu %lu", tok, &a1, &eu, &ef);
            n = unhex(tok, &data);
            k = line[0] == 'W' ? rb_write(rb, n ? data : NULL, n)
                               : rb_write_overwrite(rb, n ? data : NULL, n);
            if (k != a1)
                fail(line[0] == 'W' ? "rb_write return value" : "rb_write_overwrite return value",
                     line);
            free(data);
            break;
        case 'R':
            sscanf(line, "R %lu %8191s %lu %lu", &a1, tok, &eu, &ef);
            n = unhex(tok, &data);
            got = malloc(a1 + 1);
            k = rb_read(rb, a1 ? got : NULL, a1);
            if (k != n || memcmp(got, data, n) != 0)
                fail("rb_read result", line);
            free(got);
            free(data);
            break;
        case 'P':
            sscanf(line, "P %lu %lu %8191s %lu %lu", &a1, &a2, tok, &eu, &ef);
            n = unhex(tok, &data);
            got = malloc(a2 + 1);
            k = rb_peek(rb, a1, a2 ? got : NULL, a2);
            if (k != n || memcmp(got, data, n) != 0)
                fail("rb_peek result", line);
            free(got);
            free(data);
            break;
        case 'S':
            sscanf(line, "S %lu %lu %lu %lu", &a1, &a2, &eu, &ef);
            if (rb_skip(rb, a1) != a2)
                fail("rb_skip return value", line);
            break;
        case 'F': {
            size_t pos = 123456789;
            int r;
            sscanf(line, "F %lu %lu %ld %lu %lu", &a1, &a2, &sfound, &eu, &ef);
            r = rb_find(rb, (uint8_t)a1, a2, &pos);
            if (sfound < 0) {
                if (r != 0 || pos != 123456789)
                    fail("rb_find should not find / must leave *pos unchanged", line);
            } else if (r != 1 || pos != (size_t)sfound) {
                fail("rb_find result", line);
            }
            break;
        }
        case 'X':
            sscanf(line, "X %lu %lu", &eu, &ef);
            rb_clear(rb);
            break;
        case 'D':
            sscanf(line, "D %8191s", tok);
            n = unhex(tok, &data);
            got = malloc(rb_capacity(rb) + 1);
            k = rb_peek(rb, 0, got, rb_capacity(rb));
            if (k != n || memcmp(got, data, n) != 0)
                fail("final contents", line);
            free(got);
            free(data);
            continue;
        default:
            fprintf(stderr, "bad case line %ld\n", lineno);
            return 2;
        }
        if (rb_used(rb) != eu || rb_free(rb) != ef)
            fail("rb_used/rb_free after operation", line);
    }
    fclose(f);
    rb_destroy(rb);
    if (failures) {
        fprintf(stderr, "%d failures\n", failures);
        return 1;
    }
    printf("%ld operations ok\n", ops);
    return 0;
}
