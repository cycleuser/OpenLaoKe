#include "../include/tool_registry.h"
#include <stdlib.h>

ToolResultBlock* question_tool_execute(Tool* tool, void* ctx, const char* input) {
    return tool_result_block_create("question_result", "Question tool ready", false);
}
