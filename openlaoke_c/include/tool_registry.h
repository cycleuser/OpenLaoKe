/* OpenLaoKe C - Tool registry */

#ifndef OPENLAOKE_TOOL_REGISTRY_H
#define OPENLAOKE_TOOL_REGISTRY_H

#include "types.h"

/* Forward declaration */
typedef struct Tool Tool;
typedef struct ToolRegistry ToolRegistry;

/* Tool function pointer types */
typedef ToolResultBlock* (*ToolExecuteFunc)(Tool* tool, void* ctx, const char* input);

/* Tool structure */
struct Tool {
    char* name;
    char* description;
    char* input_schema;  /* JSON schema */
    ToolExecuteFunc execute;
    void* user_data;
    bool is_read_only;
    bool is_destructive;
    bool is_concurrency_safe;
    bool requires_approval;
};

/* Tool registry */
struct ToolRegistry {
    Tool** tools;
    int count;
    int capacity;
};

/* Registry functions */
ToolRegistry* tool_registry_create(void);
void tool_registry_destroy(ToolRegistry* registry);

/* Tool management */
int tool_registry_register(ToolRegistry* registry, Tool* tool);
Tool* tool_registry_get(ToolRegistry* registry, const char* name);
int tool_registry_remove(ToolRegistry* registry, const char* name);

/* Tool creation */
Tool* tool_create(const char* name, const char* description, ToolExecuteFunc execute);
void tool_destroy(Tool* tool);

/* Tool schema */
char* tool_get_input_schema(Tool* tool);
int tool_set_input_schema(Tool* tool, const char* schema);

/* List all tools */
char** tool_registry_list(ToolRegistry* registry, int* count);

#endif /* OPENLAOKE_TOOL_REGISTRY_H */