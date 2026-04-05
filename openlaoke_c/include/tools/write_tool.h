/* OpenLaoKe C - Write tool */
#ifndef OPENLAOKE_TOOL_WRITE_H
#define OPENLAOKE_TOOL_WRITE_H

#include "../types.h"
#include "../tool_registry.h"

typedef struct {
    char* file_path;
    char* content;
    bool create_dirs;
    bool overwrite;
    char* encoding;
    bool append;
} WriteToolInput;

typedef struct {
    char* file_path;
    size_t bytes_written;
    bool created_new;
    bool success;
    char* error_message;
    char* backup_path;
} WriteToolResult;

ToolResultBlock* write_tool_execute(Tool* tool, void* ctx, const char* input_json);
WriteToolInput* write_tool_input_from_json(const char* json);
void write_tool_input_destroy(WriteToolInput* input);
WriteToolResult* write_tool_result_create(void);
void write_tool_result_destroy(WriteToolResult* result);
char* write_tool_result_to_json(WriteToolResult* result);

bool file_exists(const char* path);
bool create_directory_recursive(const char* path);
bool backup_file(const char* path);
char* get_file_backup_path(const char* path);

#endif
