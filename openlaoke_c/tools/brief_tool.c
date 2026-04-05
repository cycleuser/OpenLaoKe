#include "../include/tool_registry.h"
#include "../include/types.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

ToolResultBlock* brief_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    (void)tool;
    (void)ctx;
    
    char* result = malloc(256);
    snprintf(result, 256, "{\"status\": \"ready\", \"tool\": \"brief\", \"message\": \"Tool initialized and ready for use\"}");
    
    ToolResultBlock* block = tool_result_block_create("brief_result", result, false);
    free(result);
    return block;
}

Tool* brief_tool_create(void) {
    Tool* tool = calloc(1, sizeof(Tool));
    tool->name = strdup("brief");
    tool->description = strdup("brief tool for OpenLaoKe");
    tool->execute = brief_tool_execute;
    tool->is_read_only = false;
    tool->is_destructive = false;
    tool->is_concurrency_safe = true;
    tool->requires_approval = false;
    return tool;
}
