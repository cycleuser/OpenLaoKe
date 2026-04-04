/* OpenLaoKe C - Tool registry */

#ifndef OPENLAOKE_TOOL_REGISTRY_H
#define OPENLAOKE_TOOL_REGISTRY_H

#include "types.h"

/* Forward declaration */
typedef struct Tool Tool;

/* Tool function pointer types */
typedef ToolResultBlock* (*ToolExecuteFunc)(Tool* tool, void* ctx, const char* input);

/* Tool structure */
struct Tool {
    char* name;
    char* description;
    char* input_schema;  /* JSON schema */
    ToolExecuteFunc execute;
    void* user_data;
};

/* Tool registry */
struct ToolRegistry {
    Tool** tools;
    int count;
    int capacity;
};

/* Registry functions */
struct ToolRegistry* tool_registry_create(void);
void tool_registry_destroy(ToolRegistry* registry);

/* Tool management */
int tool_registry_register(ToolRegistry* registry, Tool* tool);
struct Tool* tool_registry_get(ToolRegistry* registry, const char* name);
int tool_registry_remove(ToolRegistry* registry, const char* name);

/* Tool creation */
struct Tool* tool_create(const char* name, const char* description, ToolExecuteFunc execute);
void tool_destroy(Tool* tool);

/* Tool schema */
char* tool_get_input_schema(Tool* tool);
int tool_set_input_schema(Tool* tool, const char* schema);

/* List all tools */
char** tool_registry_list(ToolRegistry* registry, int* count);

#endif /* OPENLAOKE_TOOL_REGISTRY_H */