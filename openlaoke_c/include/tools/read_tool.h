/* OpenLaoKe C - Read tool */

#ifndef OPENLAOKE_TOOL_READ_H
#define OPENLAOKE_TOOL_READ_H

#include "../types.h"
#include "../tool_registry.h"

/* Read tool input */
typedef struct {
    char* file_path;
    int offset;
    int limit;
    bool show_line_numbers;
} ReadToolInput;

/* Read tool result */
typedef struct {
    char* content;
    int total_lines;
    int bytes_read;
    bool is_binary;
    char* encoding;
    char* error_message;
} ReadToolResult;

/* Read tool functions */
ToolResultBlock* read_tool_execute(Tool* tool, void* ctx, const char* input_json);
ReadToolInput* read_tool_input_from_json(const char* json);
void read_tool_input_destroy(ReadToolInput* input);
ReadToolResult* read_tool_result_create(void);
void read_tool_result_destroy(ReadToolResult* result);
char* read_tool_result_to_json(ReadToolResult* result);

/* File utilities */
bool file_exists(const char* path);
bool is_binary_file(const char* path);
char* detect_encoding(const char* content, size_t length);
int count_file_lines(const char* path);

#endif /* OPENLAOKE_TOOL_READ_H */