/* OpenLaoKe C - Glob tool */

#ifndef OPENLAOKE_TOOL_GLOB_H
#define OPENLAOKE_TOOL_GLOB_H

#include "../types.h"
#include "../tool_registry.h"

/* Glob tool input */
typedef struct {
    char* pattern;
    char* path;
    bool recursive;
    bool include_hidden;
    int max_results;
    bool case_sensitive;
} GlobToolInput;

/* Glob tool result */
typedef struct {
    char** files;
    int file_count;
    int total_matches;
    bool truncated;
    char* base_path;
    char* error_message;
} GlobToolResult;

/* Glob tool functions */
ToolResultBlock* glob_tool_execute(Tool* tool, void* ctx, const char* input_json);
GlobToolInput* glob_tool_input_from_json(const char* json);
void glob_tool_input_destroy(GlobToolInput* input);
GlobToolResult* glob_tool_result_create(void);
void glob_tool_result_destroy(GlobToolResult* result);
char* glob_tool_result_to_json(GlobToolResult* result);

/* Glob utilities */
char** glob_search(const char* pattern, const char* base_path, int* count, int max_results);
bool match_glob_pattern(const char* filename, const char* pattern);

#endif /* OPENLAOKE_TOOL_GLOB_H */