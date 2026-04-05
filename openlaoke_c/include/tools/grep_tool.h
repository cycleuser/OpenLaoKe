/* OpenLaoKe C - Grep tool */

#ifndef OPENLAOKE_TOOL_GREP_H
#define OPENLAOKE_TOOL_GREP_H

#include "../types.h"
#include "../tool_registry.h"

/* Grep tool input */
typedef struct {
    char* pattern;
    char* path;
    char* include_pattern;
    char* exclude_pattern;
    bool ignore_case;
    bool use_regex;
    bool show_line_numbers;
    bool show_context;
    int context_lines;
    int max_results;
    bool invert_match;
} GrepToolInput;

/* Grep tool result */
typedef struct {
    char** matches;
    int match_count;
    int total_matches;
    int files_searched;
    bool truncated;
    char* error_message;
} GrepToolResult;

/* Grep match */
typedef struct {
    char* file_path;
    int line_number;
    char* line_content;
    char* match_text;
    int match_start;
    int match_end;
} GrepMatch;

/* Grep tool functions */
ToolResultBlock* grep_tool_execute(Tool* tool, void* ctx, const char* input_json);
GrepToolInput* grep_tool_input_from_json(const char* json);
void grep_tool_input_destroy(GrepToolInput* input);
GrepToolResult* grep_tool_result_create(void);
void grep_tool_result_destroy(GrepToolResult* result);
char* grep_tool_result_to_json(GrepToolResult* result);

/* Grep utilities */
GrepMatch** grep_search_file(const char* filepath, GrepToolInput* input, int* match_count);
bool grep_match_line(const char* line, GrepToolInput* input);

#endif /* OPENLAOKE_TOOL_GREP_H */