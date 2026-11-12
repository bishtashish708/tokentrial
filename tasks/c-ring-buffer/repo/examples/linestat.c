/* linestat - read stdin in small chunks through a linereader and report line statistics.
 *
 *   usage: linestat [MAX_LINE]      (default 80)
 *
 * Prints "lines=N longest=L too_long=T". Useful for eyeballing the reader on real files:
 *   ./build/linestat 120 < SPEC.md
 */
#include <stdio.h>
#include <stdlib.h>

#include "../linereader.h"

int main(int argc, char **argv)
{
    size_t max_line = 80;
    char chunk[7]; /* deliberately tiny so lines straddle chunk boundaries */
    char *line;
    linereader_t *lr;
    unsigned long lines = 0, too_long = 0;
    long longest = 0;
    size_t got;

    if (argc > 1)
        max_line = (size_t)strtoul(argv[1], NULL, 10);
    lr = lr_create(max_line);
    line = malloc(max_line + 1);
    if (lr == NULL || line == NULL) {
        fprintf(stderr, "linestat: bad MAX_LINE\n");
        return 2;
    }

    while ((got = fread(chunk, 1, sizeof chunk, stdin)) > 0) {
        size_t off = 0;
        while (off < got) {
            long r;
            off += lr_feed(lr, chunk + off, got - off);
            while ((r = lr_next(lr, line, max_line + 1)) != LR_AGAIN) {
                if (r == LR_TOO_LONG) {
                    too_long++;
                    continue;
                }
                lines++;
                if (r > longest)
                    longest = r;
            }
        }
    }
    if (lr_pending(lr) > 0)
        lines++; /* unterminated last line */

    printf("lines=%lu longest=%ld too_long=%lu\n", lines, longest, too_long);
    free(line);
    lr_destroy(lr);
    return 0;
}
