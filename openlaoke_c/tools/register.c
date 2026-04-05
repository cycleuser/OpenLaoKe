#include "../include/tool_registry.h"
#include "../include/tools/bash_tool.h"
#include "../include/tools/read_tool.h"
#include <string.h>

extern ToolResultBlock* agent_tool_execute(Tool*, void*, const char*);
extern ToolResultBlock* batch_tool_execute(Tool*, void*, const char*);
extern ToolResultBlock* webfetch_tool_execute(Tool*, void*, const char*);
extern ToolResultBlock* websearch_tool_execute(Tool*, void*, const char*);
extern ToolResultBlock* todo_tool_execute(Tool*, void*, const char*);
extern ToolResultBlock* ls_tool_execute(Tool*, void*, const char*);
extern ToolResultBlock* sleep_tool_execute(Tool*, void*, const char*);
extern ToolResultBlock* question_tool_execute(Tool*, void*, const char*);

int tools_register_all_extended(ToolRegistry* registry) {
    int count = 0;
    
    tool_registry_register(registry, tool_create("bash", "Execute bash", bash_tool_execute));
    tool_registry_register(registry, tool_create("read", "Read files", read_tool_execute));
    tool_registry_register(registry, tool_create("write", "Write files", write_tool_execute));
    tool_registry_register(registry, tool_create("edit", "Edit files", edit_tool_execute));
    tool_registry_register(registry, tool_create("glob", "Glob search", glob_tool_execute));
    tool_registry_register(registry, tool_create("grep", "Grep search", grep_tool_execute));
    tool_registry_register(registry, tool_create("git", "Git operations", git_tool_execute));
    tool_registry_register(registry, tool_create("agent", "Agent tasks", agent_tool_execute));
    tool_registry_register(registry, tool_create("batch", "Batch tools", batch_tool_execute));
    tool_registry_register(registry, tool_create("webfetch", "Fetch web", webfetch_tool_execute));
    tool_registry_register(registry, tool_create("websearch", "Search web", websearch_tool_execute));
    tool_registry_register(registry, tool_create("todo", "Todo list", todo_tool_execute));
    tool_registry_register(registry, tool_create("ls", "List dir", ls_tool_execute));
    tool_registry_register(registry, tool_create("sleep", "Sleep", sleep_tool_execute));
    tool_registry_register(registry, tool_create("question", "Questions", question_tool_execute));
    
    return 15;
}
