CC      = gcc
CFLAGS  = -Wall -Wextra -std=c11 -pthread
TARGET  = uti_server
SRCS    = main.c patient.c vitals.c network.c
OBJS    = $(SRCS:.c=.o)

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^

%.o: %.c patient.h
	$(CC) $(CFLAGS) -c -o $@ $<

run: all
	./$(TARGET)

clean:
	rm -f $(TARGET) $(OBJS) uti_history.log
