#include "../include/tool_registry.h"
#include "../include/types.h"
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

static char* extract_json_string_value(const char* json, const char* key) {
    char* key_start = strstr(json, key);
    if (!key_start) return NULL;
    
    char* value_start = strchr(key_start + strlen(key), ':');
    if (!value_start) return NULL;
    
    while (*value_start == ' ' || *value_start == ':') value_start++;
    
    if (*value_start == '"') {
        value_start++;
        char* value_end = strchr(value_start, '"');
        if (!value_end) return NULL;
        size_t len = value_end - value_start;
        char* result = malloc(len + 1);
        strncpy(result, value_start, len);
        result[len] = '\0';
        return result;
    }
    
    char* value_end = value_start;
    while (*value_end && *value_end != ',' && *value_end != '}' && *value_end != ']') {
        value_end++;
    }
    size_t len = value_end - value_start;
    char* result = malloc(len + 1);
    strncpy(result, value_start, len);
    result[len] = '\0';
    return result;
}

ToolResultBlock* sleep_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    (void)tool;
    (void)ctx;
    
    char* seconds_str = extract_json_string_value(input_json, "\"seconds\"");
    int seconds = 1;
    
    if (seconds_str) {
        seconds = atoi(seconds_str);
        free(seconds_str);
        
        if (seconds < 0) {
            return tool_result_block_create("sleep_error", 
                "Error: seconds must be positive", true);
        }
        
        if (seconds > 300) {
            return tool_result_block_create("sleep_error", 
                "Error: maximum sleep time is 300 seconds", true);
        }
    }
    
    sleep(seconds);
    
    char* result = malloc(128);
    snprintf(result, 128, "Slept for %d seconds", seconds);
    
    ToolResultBlock* block = tool_result_block_create("sleep_result", result, false);
    free(result);
    return block;
}

Tool* sleep_tool_create(void) {
    Tool* tool = calloc(1, sizeof(Tool));
    tool->name = strdup("Sleep");
    tool->description = strdup(
        "Pause execution for specified seconds. "
        "Use for rate limiting, retry delays, or timing operations.");
    tool->execute = sleep_tool_execute;
    tool->is_read_only = true;
    tool->is_destructive = false;
    tool->is_concurrency_safe = true;
    tool->requires_approval = false;
    return tool;
}