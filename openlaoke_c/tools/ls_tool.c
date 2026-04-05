#include "../include/tool_registry.h"
#include <stdio.h>
#include <stdlib.h>
#include <dirent.h>

ToolResultBlock* ls_tool_execute(Tool* tool, void* ctx, const char* input) {
    DIR* dir = opendir(".");
    if (!dir) return tool_result_block_create("ls_error", "Cannot open directory", true);
    
    char result[65536];
    char* p = result;
    struct dirent* entry;
    
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] == '.') continue;
        p += sprintf(p, "%s\n", entry->d_name);
    }
    
    closedir(dir);
    return tool_result_block_create("ls_result", result, false);
}
