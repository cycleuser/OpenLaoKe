#include "../include/tools/edit_tool.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

ToolResultBlock* edit_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    /* Parse input */
    EditToolInput* input = edit_tool_input_from_json(input_json);
    if (!input) {
        return tool_result_block_create("edit_error", "Invalid input JSON", true);
    }
    
    /* Read file */
    FILE* f = fopen(input->file_path, "r");
    if (!f) {
        char error[512];
        snprintf(error, sizeof(error), "Cannot open file: %s", input->file_path);
        edit_tool_input_destroy(input);
        return tool_result_block_create("edit_error", error, true);
    }
    
    /* Get file size */
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    
    /* Read content */
    char* content = (char*)malloc(size + 1);
    fread(content, 1, size, f);
    content[size] = '\0';
    fclose(f);
    
    /* Apply edit */
    int replacements = 0;
    char* new_content = apply_edit(content, input, &replacements);
    
    if (!new_content) {
        char error[256];
        snprintf(error, sizeof(error), "Failed to apply edit");
        free(content);
        edit_tool_input_destroy(input);
        return tool_result_block_create("edit_error", error, true);
    }
    
    /* Write back */
    f = fopen(input->file_path, "w");
    if (!f) {
        char error[512];
        snprintf(error, sizeof(error), "Cannot write to file: %s", input->file_path);
        free(content);
        free(new_content);
        edit_tool_input_destroy(input);
        return tool_result_block_create("edit_error", error, true);
    }
    
    fwrite(new_content, 1, strlen(new_content), f);
    fclose(f);
    
    /* Create result */
    char result[512];
    snprintf(result, sizeof(result), "Applied %d replacement(s) to %s", 
             replacements, input->file_path);
    
    free(content);
    free(new_content);
    edit_tool_input_destroy(input);
    
    return tool_result_block_create("edit_result", result, false);
}

EditToolInput* edit_tool_input_from_json(const char* json) {
    if (!json) return NULL;
    
    EditToolInput* input = (EditToolInput*)calloc(1, sizeof(EditToolInput));
    if (!input) return NULL;
    
    /* Simple JSON parsing */
    const char* file_start = strstr(json, "\"file_path\"");
    if (file_start) {
        file_start = strchr(file_start, ':');
        if (file_start) {
            file_start = strchr(file_start, '"');
            if (file_start) {
                file_start++;
                const char* file_end = strchr(file_start, '"');
                if (file_end) {
                    size_t len = file_end - file_start;
                    input->file_path = (char*)malloc(len + 1);
                    strncpy(input->file_path, file_start, len);
                    input->file_path[len] = '\0';
                }
            }
        }
    }
    
    /* Set defaults */
    input->operation = EDIT_REPLACE;
    input->replace_all = false;
    
    return input;
}

void edit_tool_input_destroy(EditToolInput* input) {
    if (!input) return;
    free(input->file_path);
    free(input->old_string);
    free(input->new_string);
    free(input);
}

EditToolResult* edit_tool_result_create(void) {
    return (EditToolResult*)calloc(1, sizeof(EditToolResult));
}

void edit_tool_result_destroy(EditToolResult* result) {
    if (!result) return;
    free(result->file_path);
    free(result->diff_preview);
    free(result->error_message);
    free(result->backup_path);
    free(result);
}

char* edit_tool_result_to_json(EditToolResult* result) {
    if (!result) return NULL;
    
    char* json = (char*)malloc(512);
    if (!json) return NULL;
    
    snprintf(json, 512,
        "{\"file_path\":\"%s\",\"replacements_made\":%d,\"success\":%s}",
        result->file_path ? result->file_path : "",
        result->replacements_made,
        result->success ? "true" : "false");
    
    return json;
}

char* apply_edit(const char* content, EditToolInput* input, int* replacements) {
    if (!content || !input || !replacements) return NULL;
    
    *replacements = 0;
    
    /* Simple string replacement */
    if (!input->old_string || !input->new_string) {
        return strdup(content);
    }
    
    /* Count occurrences */
    size_t old_len = strlen(input->old_string);
    size_t new_len = strlen(input->new_string);
    const char* p = content;
    int count = 0;
    
    while ((p = strstr(p, input->old_string)) != NULL) {
        count++;
        p += old_len;
    }
    
    if (count == 0) {
        return strdup(content);
    }
    
    /* Allocate new buffer */
    size_t new_size = strlen(content) + count * (new_len - old_len) + 1;
    char* new_content = (char*)malloc(new_size);
    if (!new_content) return NULL;
    
    /* Replace */
    char* dst = new_content;
    p = content;
    const char* prev = content;
    
    while ((p = strstr(prev, input->old_string)) != NULL) {
        if (!input->replace_all && *replacements > 0) break;
        
        size_t before = p - prev;
        memcpy(dst, prev, before);
        dst += before;
        
        memcpy(dst, input->new_string, new_len);
        dst += new_len;
        
        prev = p + old_len;
        (*replacements)++;
    }
    
    strcpy(dst, prev);
    
    return new_content;
}

char* generate_diff_preview(const char* old_content, const char* new_content) {
    /* Simple diff - just show changes */
    return strdup("Diff preview not implemented");
}

bool validate_edit_input(EditToolInput* input, const char* content) {
    if (!input || !content) return false;
    if (!input->file_path) return false;
    if (!input->old_string) return false;
    return true;
}
