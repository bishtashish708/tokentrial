CC ?= cc
CFLAGS ?= -std=c11 -Wall -Wextra -O1 -g
BUILD := build

LIB_SRC := ringbuf.c linereader.c
LIB_HDR := ringbuf.h linereader.h

.PHONY: all test clean

all: $(BUILD)/linestat $(BUILD)/test_ringbuf

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/linestat: examples/linestat.c $(LIB_SRC) $(LIB_HDR) | $(BUILD)
	$(CC) $(CFLAGS) -I. -o $@ examples/linestat.c $(LIB_SRC)

$(BUILD)/test_ringbuf: tests/test_ringbuf.c $(LIB_SRC) $(LIB_HDR) | $(BUILD)
	$(CC) $(CFLAGS) -I. -o $@ tests/test_ringbuf.c $(LIB_SRC)

test: $(BUILD)/test_ringbuf
	./$(BUILD)/test_ringbuf

clean:
	rm -rf $(BUILD)
