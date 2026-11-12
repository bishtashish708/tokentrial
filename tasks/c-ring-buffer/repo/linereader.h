/* linereader.h - newline-framed reader on top of ringbuf.
 *
 * Bytes arrive in arbitrary chunks (lr_feed); complete lines come out of lr_next.
 * A line is terminated by '\n'; a single '\r' just before the '\n' is stripped too.
 * At most max_line bytes of a line (excluding the terminator) can be buffered.
 */
#ifndef LINEREADER_H
#define LINEREADER_H

#include <stddef.h>

#define LR_AGAIN (-1)    /* no complete line buffered yet: feed more */
#define LR_TOO_LONG (-2) /* buffer full without a newline: buffered bytes were dropped */

typedef struct linereader linereader_t;

linereader_t *lr_create(size_t max_line);
void lr_destroy(linereader_t *lr);

/* Buffer up to n bytes of input; returns how many were accepted (may be fewer when full). */
size_t lr_feed(linereader_t *lr, const char *data, size_t n);

/* Copy the next complete line, NUL-terminated and without its terminator, into out
 * (outsz must be at least max_line + 1) and return its length; or LR_AGAIN / LR_TOO_LONG. */
long lr_next(linereader_t *lr, char *out, size_t outsz);

/* Bytes currently buffered (complete and partial lines). */
size_t lr_pending(const linereader_t *lr);

#endif /* LINEREADER_H */
