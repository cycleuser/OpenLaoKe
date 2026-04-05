/* OpenLaoKe C - Command base and registry */

#ifndef OPENLAOKE_COMMANDS_H
#define OPENLAOKE_COMMANDS_H

#include "types.h"

/* Forward declaration */
typedef struct SlashCommand SlashCommand;

/* Command execute function */
typedef int (*CommandExecuteFunc)(SlashCommand* cmd, void* ctx, char* args);

/* Slash command */
struct SlashCommand {
    char* name;
    char** aliases;
    int alias_count;
    char* description;
    char* usage;
    CommandExecuteFunc execute;
    bool requires_confirmation;
    void* user_data;
};

/* Command registry */
typedef struct {
    SlashCommand** commands;
    int count;
    int capacity;
} CommandRegistry;

/* Command functions */
CommandRegistry* command_registry_create(void);
void command_registry_destroy(CommandRegistry* registry);

int command_registry_register(CommandRegistry* registry, SlashCommand* cmd);
SlashCommand* command_registry_get(CommandRegistry* registry, const char* name);
int command_registry_remove(CommandRegistry* registry, const char* name);
char** command_registry_list(CommandRegistry* registry, int* count);

/* Command creation */
SlashCommand* slash_command_create(const char* name, const char* description, CommandExecuteFunc execute);
void slash_command_destroy(SlashCommand* cmd);

/* Command execution */
int slash_command_execute(SlashCommand* cmd, void* ctx, char* args);

/* Parse command from input */
SlashCommand* parse_command(CommandRegistry* registry, const char* input, char** args_out);

/* Built-in commands */
int command_help(SlashCommand* cmd, void* ctx, char* args);
int command_status(SlashCommand* cmd, void* ctx, char* args);
int command_version(SlashCommand* cmd, void* ctx, char* args);
int command_exit(SlashCommand* cmd, void* ctx, char* args);
int command_tools(SlashCommand* cmd, void* ctx, char* args);
int command_model(SlashCommand* cmd, void* ctx, char* args);
int command_provider(SlashCommand* cmd, void* ctx, char* args);
int command_clear(SlashCommand* cmd, void* ctx, char* args);
int command_save(SlashCommand* cmd, void* ctx, char* args);
int command_load(SlashCommand* cmd, void* ctx, char* args);

/* Register built-in commands */
int register_builtin_commands(CommandRegistry* registry);

#endif /* OPENLAOKE_COMMANDS_H */