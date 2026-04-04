# OpenLaoKe C - Build configuration

CC = gcc
CFLAGS = -Wall -Wextra -O2 -I./include
LDFLAGS = -lcurl -ljansson -lpthread

# Directories
SRC_DIR = .
BUILD_DIR = build
BIN_DIR = bin
OBJ_DIR = obj

# Source files
SOURCES = main.c \
          core/state.c \
          core/tool_registry.c \
          tools/tools.c \
          types/types.c

OBJECTS = $(SOURCES:%.c=$(OBJ_DIR)/%.o)
TARGET = $(BIN_DIR)/openlaoke

# Default target
all: directories $(TARGET)

# Create necessary directories
directories:
	@mkdir -p $(BUILD_DIR)
	@mkdir -p $(BIN_DIR)
	@mkdir -p $(OBJ_DIR)
	@mkdir -p $(OBJ_DIR)/core
	@mkdir -p $(OBJ_DIR)/tools
	@mkdir -p $(OBJ_DIR)/types

# Link the executable
$(TARGET): $(OBJECTS)
	$(CC) $(OBJECTS) -o $@ $(LDFLAGS)
	@echo "Build complete: $@"

# Compile source files
$(OBJ_DIR)/%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR) $(BIN_DIR) $(OBJ_DIR)
	@echo "Clean complete"

# Install to system
install: $(TARGET)
	install -m 755 $(TARGET) /usr/local/bin/
	@echo "Installed to /usr/local/bin/openlaoke"

# Uninstall from system
uninstall:
	rm -f /usr/local/bin/openlaoke
	@echo "Uninstalled from /usr/local/bin"

# Run tests
test: $(TARGET)
	@echo "Running tests..."
	./$(TARGET) --version

# Debug build
debug: CFLAGS += -g -DDEBUG
debug: clean all

# Release build
release: CFLAGS += -DNDEBUG
release: clean all

# Format code
format:
	find . -name "*.c" -o -name "*.h" | xargs clang-format -i

# Static analysis
analyze:
	scan-build make clean all

# Package for distribution
package: release
	tar -czf openlaoke-c-$(shell date +%Y%m%d).tar.gz \
		--exclude='*.o' \
		--exclude='build' \
		--exclude='bin' \
		--exclude='obj' \
		.

.PHONY: all clean install uninstall test debug release format analyze package directories