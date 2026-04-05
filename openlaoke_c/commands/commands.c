#include "../include/commands.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

CommandRegistry* command_registry_create(void) {
    CommandRegistry* registry = (CommandRegistry*)calloc(1, sizeof(CommandRegistry));
    return registry;
}

void command_registry_destroy(CommandRegistry* registry) {
    if (!registry) return;
    for (int i = 0; i < registry->count; i++) {
        slash_command_destroy(registry->commands[i]);
    }
    free(registry->commands);
    free(registry);
}

int command_registry_register(CommandRegistry* registry, SlashCommand* cmd) {
    if (!registry || !cmd) return -1;
    if (registry->count >= registry->capacity) {
        int new_cap = registry->capacity == 0 ? 10 : registry->capacity * 2;
        SlashCommand** new_cmds = (SlashCommand**)realloc(registry->commands, new_cap * sizeof(SlashCommand*));
        if (!new_cmds) return -1;
        registry->commands = new_cmds;
        registry->capacity = new_cap;
    }
    registry->commands[registry->count++] = cmd;
    return 0;
}

SlashCommand* command_registry_get(CommandRegistry* registry, const char* name) {
    if (!registry || !name) return NULL;
    for (int i = 0; i < registry->count; i++) {
        if (strcmp(registry->commands[i]->name, name) == 0) {
            return registry->commands[i];
        }
    }
    return NULL;
}

SlashCommand* slash_command_create(const char* name, const char* description, CommandExecuteFunc execute) {
    SlashCommand* cmd = (SlashCommand*)calloc(1, sizeof(SlashCommand));
    if (!cmd) return NULL;
    cmd->name = strdup(name);
    cmd->description = strdup(description);
    cmd->execute = execute;
    return cmd;
}

void slash_command_destroy(SlashCommand* cmd) {
    if (!cmd) return;
    free(cmd->name);
    free(cmd->description);
    free(cmd);
}

int command_help(SlashCommand* cmd, void* ctx, char* args) {
    printf("Available commands:\n  /help - Show help\n  /exit - Exit\n");
    return 0;
}

int command_exit(SlashCommand* cmd, void* ctx, char* args) {
    return 999;
}

int register_builtin_commands(CommandRegistry* registry) {
    command_registry_register(registry, slash_command_create("help", "Show help", command_help));
    command_registry_register(registry, slash_command_create("exit", "Exit program", command_exit));
    return registry->count;
}
