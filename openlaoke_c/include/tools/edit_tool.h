/* OpenLaoKe C - Edit tool */

#ifndef OPENLAOKE_TOOL_EDIT_H
#define OPENLAOKE_TOOL_EDIT_H

#include "../types.h"
#include "../tool_registry.h"

/* Edit operation type */
typedef enum {
    EDIT_REPLACE,
    EDIT_INSERT_BEFORE,
    EDIT_INSERT_AFTER,
    EDIT_DELETE,
    EDIT_APPEND
} EditOperation;

/* Edit tool input */
typedef struct {
    char* file_path;
    char* old_string;
    char* new_string;
    bool replace_all;
    EditOperation operation;
    int line_number;
    bool start_of_file;
    bool end_of_file;
} EditToolInput;

/* Edit tool result */
typedef struct {
    char* file_path;
    int replacements_made;
    char* diff_preview;
    bool success;
    char* error_message;
    char* backup_path;
} EditToolResult;

/* Edit tool functions */
ToolResultBlock* edit_tool_execute(Tool* tool, void* ctx, const char* input_json);
EditToolInput* edit_tool_input_from_json(const char* json);
void edit_tool_input_destroy(EditToolInput* input);
EditToolResult* edit_tool_result_create(void);
void edit_tool_result_destroy(EditToolResult* result);
char* edit_tool_result_to_json(EditToolResult* result);

/* Edit utilities */
char* apply_edit(const char* content, EditToolInput* input, int* replacements);
char* generate_diff_preview(const char* old_content, const char* new_content);
bool validate_edit_input(EditToolInput* input, const char* content);

#endif /* OPENLAOKE_TOOL_EDIT_H */