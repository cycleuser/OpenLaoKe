/* OpenLaoKe C - Tool registry implementation */

#include "../include/tool_registry.h"
#include <stdio.h>

ToolRegistry* tool_registry_create(void) {
    ToolRegistry* registry = (ToolRegistry*)malloc(sizeof(ToolRegistry));
    if (!registry) return NULL;
    
    registry->tools = NULL;
    registry->count = 0;
    registry->capacity = 0;
    
    return registry;
}

void tool_registry_destroy(ToolRegistry* registry) {
    if (!registry) return;
    
    for (int i = 0; i < registry->count; i++) {
        tool_destroy(registry->tools[i]);
    }
    free(registry->tools);
    free(registry);
}

int tool_registry_register(ToolRegistry* registry, Tool* tool) {
    if (!registry || !tool) return -1;
    
    if (registry->count >= registry->capacity) {
        int new_capacity = registry->capacity == 0 ? 10 : registry->capacity * 2;
        Tool** new_tools = (Tool**)realloc(registry->tools, new_capacity * sizeof(Tool*));
        if (!new_tools) return -1;
        
        registry->tools = new_tools;
        registry->capacity = new_capacity;
    }
    
    registry->tools[registry->count++] = tool;
    return registry->count - 1;
}

Tool* tool_registry_get(ToolRegistry* registry, const char* name) {
    if (!registry || !name) return NULL;
    
    for (int i = 0; i < registry->count; i++) {
        if (strcmp(registry->tools[i]->name, name) == 0) {
            return registry->tools[i];
        }
    }
    
    return NULL;
}

int tool_registry_remove(ToolRegistry* registry, const char* name) {
    if (!registry || !name) return -1;
    
    for (int i = 0; i < registry->count; i++) {
        if (strcmp(registry->tools[i]->name, name) == 0) {
            tool_destroy(registry->tools[i]);
            
            for (int j = i; j < registry->count - 1; j++) {
                registry->tools[j] = registry->tools[j + 1];
            }
            
            registry->count--;
            return 0;
        }
    }
    
    return -1;
}

Tool* tool_create(const char* name, const char* description, ToolExecuteFunc execute) {
    Tool* tool = (Tool*)malloc(sizeof(Tool));
    if (!tool) return NULL;
    
    tool->name = strdup(name);
    tool->description = strdup(description);
    tool->input_schema = NULL;
    tool->execute = execute;
    tool->user_data = NULL;
    
    return tool;
}

void tool_destroy(Tool* tool) {
    if (!tool) return;
    
    free(tool->name);
    free(tool->description);
    free(tool->input_schema);
    free(tool);
}

char* tool_get_input_schema(Tool* tool) {
    if (!tool) return NULL;
    return tool->input_schema ? strdup(tool->input_schema) : NULL;
}

int tool_set_input_schema(Tool* tool, const char* schema) {
    if (!tool || !schema) return -1;
    
    free(tool->input_schema);
    tool->input_schema = strdup(schema);
    
    return tool->input_schema ? 0 : -1;
}

char** tool_registry_list(ToolRegistry* registry, int* count) {
    if (!registry || !count) return NULL;
    
    *count = registry->count;
    char** names = (char**)malloc(registry->count * sizeof(char*));
    if (!names) return NULL;
    
    for (int i = 0; i < registry->count; i++) {
        names[i] = strdup(registry->tools[i]->name);
    }
    
    return names;
}