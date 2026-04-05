/* OpenLaoKe C - System prompt generator */

#ifndef OPENLAOKE_SYSTEM_PROMPT_H
#define OPENLAOKE_SYSTEM_PROMPT_H

#include "types.h"

/* System prompt context */
typedef struct {
    char* working_directory;
    char* os_info;
    char* shell;
    char** available_tools;
    int tool_count;
    char* provider;
    char* model;
    char** custom_instructions;
    int instruction_count;
    PermissionMode permission_mode;
    HyperAutoMode hyperauto_mode;
} SystemPromptContext;

/* System prompt functions */
char* system_prompt_generate(SystemPromptContext* ctx);
char* system_prompt_generate_with_tools(SystemPromptContext* ctx, char** tool_names, int count);
char* system_prompt_generate_with_skills(SystemPromptContext* ctx, char** skill_names, int count);

/* Tool listing */
char* system_prompt_format_tools(char** tools, int count);
char* system_prompt_format_skills(char** skills, int count);

/* Context creation */
SystemPromptContext* system_prompt_context_create(void);
void system_prompt_context_destroy(SystemPromptContext* ctx);

/* OS detection */
char* detect_os(void);
char* detect_shell(void);

#endif /* OPENLAOKE_SYSTEM_PROMPT_H */