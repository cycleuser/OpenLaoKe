CC=gcc
CFLAGS=-Wall -Wextra -O2 -I./include
LDFLAGS=-lpthread -lcurl

SRCS=main.c core/state.c core/tool_registry.c core/repl.c core/sessions.c \
     core/config.c core/types_extended.c core/hyperauto_types.c \
     core/system_prompt.c core/config_wizard.c core/hyperauto_engine.c \
     core/error_handler.c \
     tools/tools.c tools/bash_tool.c tools/read_tool.c tools/write_tool.c \
     tools/edit_tool.c tools/glob_tool.c tools/grep_tool.c tools/git_tool.c \
     tools/agent_tool.c tools/batch_tool.c tools/webfetch_tool.c tools/websearch_tool.c \
     tools/todo_tool.c tools/ls_tool.c tools/sleep_tool.c tools/question_tool.c \
     tools/tmux_tool.c tools/cron_tool.c tools/taskkill_tool.c tools/notebook_tool.c \
     tools/plan_tool.c tools/lsp_tool.c tools/brief_tool.c tools/patch_tool.c \
     tools/powershell_tool.c tools/repl_tool.c tools/reference_tool.c tools/browser_tool.c \
     types/types.c commands/commands.c

OBJS=$(SRCS:%.c=obj/%.o)

all: bin/openlaoke tests/test_core tests/test_hyperauto tests/test_functionality

bin/openlaoke: $(OBJS)
	mkdir -p bin
	$(CC) $^ -o $@ $(LDFLAGS)
	@echo "✓ Build complete: $@"

tests/test_core: tests/test_core.c obj/core/state.o obj/core/tool_registry.o obj/types/types.o
	mkdir -p tests
	$(CC) $(CFLAGS) $^ -o $@ $(LDFLAGS)
	@echo "✓ Test build: $@"

tests/test_hyperauto: tests/test_hyperauto.c obj/core/state.o obj/core/tool_registry.o obj/types/types.o obj/core/types_extended.o obj/core/hyperauto_types.o
	mkdir -p tests
	$(CC) $(CFLAGS) $^ -o $@ $(LDFLAGS)
	@echo "✓ Test build: $@"

tests/test_functionality: tests/test_functionality.c obj/core/state.o obj/core/tool_registry.o obj/types/types.o obj/core/types_extended.o obj/core/error_handler.o
	mkdir -p tests
	$(CC) $(CFLAGS) $^ -o $@ $(LDFLAGS)
	@echo "✓ Test build: $@"

obj/%.o: %.c
	mkdir -p obj obj/core obj/tools obj/types obj/commands
	$(CC) $(CFLAGS) -c $< -o $@

test: tests/test_core tests/test_hyperauto tests/test_functionality
	./tests/test_core
	./tests/test_hyperauto
	./tests/test_functionality

clean:
	rm -rf obj bin tests/test_core tests/test_hyperauto tests/test_functionality

.PHONY: all clean test
