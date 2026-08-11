CC = clang
CFLAGS = -O2 -Wall -fPIC
TARGET = libhand_eval.so

$(TARGET): hand_eval.c
	$(CC) $(CFLAGS) -shared -o $(TARGET) hand_eval.c

clean:
	rm -f $(TARGET)

.PHONY: clean
