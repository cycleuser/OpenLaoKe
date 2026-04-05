/* OpenLaoKe C - Bash tool */

#ifndef OPENLAOKE_TOOL_BASH_H
#define OPENLAOKE_TOOL_BASH_H

#include "../types.h"
#include "../tool_registry.h"

/* Bash tool context */
typedef struct {
    char* command;
    char* description;
    char* workdir;
    int timeout;
    bool capture_output;
    bool check_exit_code;
} BashToolInput;

/* Bash tool result */
typedef struct {
    char* stdout_output;
    char* stderr_output;
    int exit_code;
    bool success;
    char* error_message;
    double execution_time;
} BashToolResult;

/* Bash tool functions */
ToolResultBlock* bash_tool_execute(Tool* tool, void* ctx, const char* input_json);
BashToolInput* bash_tool_input_from_json(const char* json);
void bash_tool_input_destroy(BashToolInput* input);
BashToolResult* bash_tool_result_create(void);
void bash_tool_result_destroy(BashToolResult* result);
char* bash_tool_result_to_json(BashToolResult* result);

/* Bash safety classifier */
typedef enum {
    BASH_SAFETY_SAFE,
    BASH_SAFETY_MODERATE,
    BASH_SAFETY_DANGEROUS,
    BASH_SAFETY_UNKNOWN
} BashSafetyLevel;

BashSafetyLevel bash_classify_safety(const char* command);
bool bash_is_readonly_command(const char* command);
bool bash_requires_confirmation(const char* command);

#endif /* OPENLAOKE_TOOL_BASH_H */