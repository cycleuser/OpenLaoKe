/* OpenLaoKe C - Tool implementations */

#ifndef OPENLAOKE_TOOLS_H
#define OPENLAOKE_TOOLS_H

#include "types.h"
#include "tool_registry.h"

/* Bash tool */
ToolResultBlock* tool_bash_execute(Tool* tool, void* ctx, const char* input);

/* Read tool */
ToolResultBlock* tool_read_execute(Tool* tool, void* ctx, const char* input);

/* Write tool */
ToolResultBlock* tool_write_execute(Tool* tool, void* ctx, const char* input);

/* Edit tool */
ToolResultBlock* tool_edit_execute(Tool* tool, void* ctx, const char* input);

/* Glob tool */
ToolResultBlock* tool_glob_execute(Tool* tool, void* ctx, const char* input);

/* Grep tool */
ToolResultBlock* tool_grep_execute(Tool* tool, void* ctx, const char* input);

/* List directory tool */
ToolResultBlock* tool_ls_execute(Tool* tool, void* ctx, const char* input);

/* Git tool */
ToolResultBlock* tool_git_execute(Tool* tool, void* ctx, const char* input);

/* Web fetch tool */
ToolResultBlock* tool_webfetch_execute(Tool* tool, void* ctx, const char* input);

/* Agent tool */
ToolResultBlock* tool_agent_execute(Tool* tool, void* ctx, const char* input);

/* Register all tools */
int tools_register_all(ToolRegistry* registry);

#endif /* OPENLAOKE_TOOLS_H */