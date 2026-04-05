#include <time.h>
/* OpenLaoKe C - Write tool implementation */

#include "../include/tools/write_tool.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <errno.h>
#include <libgen.h>

ToolResultBlock* write_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    WriteToolInput* input = write_tool_input_from_json(input_json);
    if (!input) {
        return tool_result_block_create("write_error", "Invalid input JSON", true);
    }
    
    /* Validate input */
    if (!input->file_path || !input->content) {
        write_tool_input_destroy(input);
        return tool_result_block_create("write_error", "Missing file_path or content", true);
    }
    
    /* Create directories if needed */
    if (input->create_dirs) {
        if (!create_directory_recursive(input->file_path)) {
            char error[512];
            snprintf(error, sizeof(error), "Failed to create directory for: %s", 
                     input->file_path);
            write_tool_input_destroy(input);
            return tool_result_block_create("write_error", error, true);
        }
    }
    
    /* Backup existing file if it exists */
    bool created_new = true;
    char* backup_path = NULL;
    
    if (file_exists(input->file_path)) {
        created_new = false;
        
        if (!input->overwrite) {
            char error[512];
            snprintf(error, sizeof(error), "File already exists: %s (set overwrite=true to replace)", 
                     input->file_path);
            write_tool_input_destroy(input);
            return tool_result_block_create("write_error", error, true);
        }
        
        backup_path = get_file_backup_path(input->file_path);
        if (backup_path) {
            backup_file(input->file_path);
        }
    }
    
    /* Open file for writing */
    FILE* f = fopen(input->file_path, input->append ? "a" : "w");
    if (!f) {
        char error[512];
        snprintf(error, sizeof(error), "Failed to open file for writing: %s (%s)", 
                 input->file_path, strerror(errno));
        write_tool_input_destroy(input);
        free(backup_path);
        return tool_result_block_create("write_error", error, true);
    }
    
    /* Write content */
    size_t content_len = strlen(input->content);
    size_t bytes_written = fwrite(input->content, 1, content_len, f);
    
    int flush_result = fflush(f);
    fclose(f);
    
    if (bytes_written != content_len || flush_result != 0) {
        char error[512];
        snprintf(error, sizeof(error), "Failed to write complete content to: %s", 
                 input->file_path);
        write_tool_input_destroy(input);
        free(backup_path);
        return tool_result_block_create("write_error", error, true);
    }
    
    /* Create result */
    WriteToolResult* result = write_tool_result_create();
    result->file_path = strdup(input->file_path);
    result->bytes_written = bytes_written;
    result->created_new = created_new;
    result->success = true;
    result->backup_path = backup_path;
    
    char* result_json = write_tool_result_to_json(result);
    ToolResultBlock* block = tool_result_block_create("write_result", 
        result_json ? result_json : "File written successfully", false);
    
    free(result_json);
    write_tool_result_destroy(result);
    write_tool_input_destroy(input);
    
    return block;
}

WriteToolInput* write_tool_input_from_json(const char* json) {
    if (!json) return NULL;
    
    WriteToolInput* input = (WriteToolInput*)calloc(1, sizeof(WriteToolInput));
    if (!input) return NULL;
    
    /* Parse "file_path" field */
    const char* path_start = strstr(json, "\"file_path\"");
    if (path_start) {
        path_start = strchr(path_start, ':');
        if (path_start) {
            path_start = strchr(path_start, '"');
            if (path_start) {
                path_start++;
                const char* path_end = strchr(path_start, '"');
                if (path_end) {
                    size_t len = path_end - path_start;
                    input->file_path = (char*)malloc(len + 1);
                    strncpy(input->file_path, path_start, len);
                    input->file_path[len] = '\0';
                }
            }
        }
    }
    
    /* Parse "content" field - need to handle multi-line content */
    const char* content_start = strstr(json, "\"content\"");
    if (content_start) {
        content_start = strchr(content_start, ':');
        if (content_start) {
            content_start = strchr(content_start, '"');
            if (content_start) {
                content_start++;
                
                /* Find the end of content - handle escaped quotes */
                const char* content_end = content_start;
                while (*content_end) {
                    if (*content_end == '\\' && *(content_end + 1) == '"') {
                        content_end += 2;  /* Skip escaped quote */
                    } else if (*content_end == '"') {
                        break;
                    } else {
                        content_end++;
                    }
                }
                
                if (*content_end == '"') {
                    size_t len = content_end - content_start;
                    input->content = (char*)malloc(len + 1);
                    
                    /* Unescape content */
                    char* dst = input->content;
                    for (const char* src = content_start; src < content_end; src++) {
                        if (*src == '\\' && src + 1 < content_end) {
                            src++;
                            switch (*src) {
                                case 'n': *dst++ = '\n'; break;
                                case 't': *dst++ = '\t'; break;
                                case 'r': *dst++ = '\r'; break;
                                case '\\': *dst++ = '\\'; break;
                                case '"': *dst++ = '"'; break;
                                default: *dst++ = *src; break;
                            }
                        } else {
                            *dst++ = *src;
                        }
                    }
                    *dst = '\0';
                }
            }
        }
    }
    
    /* Set defaults */
    input->create_dirs = true;
    input->overwrite = true;
    input->append = false;
    
    return input;
}

void write_tool_input_destroy(WriteToolInput* input) {
    if (!input) return;
    free(input->file_path);
    free(input->content);
    free(input->encoding);
    free(input);
}

WriteToolResult* write_tool_result_create(void) {
    return (WriteToolResult*)calloc(1, sizeof(WriteToolResult));
}

void write_tool_result_destroy(WriteToolResult* result) {
    if (!result) return;
    free(result->file_path);
    free(result->error_message);
    free(result->backup_path);
    free(result);
}

char* write_tool_result_to_json(WriteToolResult* result) {
    if (!result) return NULL;
    
    size_t size = 512;
    char* json = (char*)malloc(size);
    if (!json) return NULL;
    
    snprintf(json, size,
        "{"
        "\"file_path\":\"%s\","
        "\"bytes_written\":%zu,"
        "\"created_new\":%s,"
        "\"success\":%s"
        "}",
        result->file_path ? result->file_path : "",
        result->bytes_written,
        result->created_new ? "true" : "false",
        result->success ? "true" : "false"
    );
    
    return json;
}

bool create_directory_recursive(const char* path) {
    if (!path) return false;
    
    /* Make a copy of path */
    char* dir_path = strdup(path);
    if (!dir_path) return false;
    
    /* Get directory part */
    char* last_slash = strrchr(dir_path, '/');
    if (!last_slash) {
        free(dir_path);
        return true;  /* No directory part, current directory */
    }
    
    *last_slash = '\0';  /* Truncate to get directory path */
    
    /* Check if directory already exists */
    struct stat st;
    if (stat(dir_path, &st) == 0 && S_ISDIR(st.st_mode)) {
        free(dir_path);
        return true;
    }
    
    /* Create parent directories first */
    char* parent = strdup(dir_path);
    if (parent) {
        create_directory_recursive(parent);
        free(parent);
    }
    
    /* Create this directory */
    int result = mkdir(dir_path, 0755);
    free(dir_path);
    
    return result == 0 || errno == EEXIST;
}

bool backup_file(const char* path) {
    if (!path || !file_exists(path)) return false;
    
    char* backup_path = get_file_backup_path(path);
    if (!backup_path) return false;
    
    /* Copy file to backup */
    FILE* src = fopen(path, "r");
    if (!src) {
        free(backup_path);
        return false;
    }
    
    FILE* dst = fopen(backup_path, "w");
    if (!dst) {
        fclose(src);
        free(backup_path);
        return false;
    }
    
    char buffer[4096];
    size_t bytes;
    bool success = true;
    
    while ((bytes = fread(buffer, 1, sizeof(buffer), src)) > 0) {
        if (fwrite(buffer, 1, bytes, dst) != bytes) {
            success = false;
            break;
        }
    }
    
    fclose(src);
    fclose(dst);
    free(backup_path);
    
    return success;
}

char* get_file_backup_path(const char* path) {
    if (!path) return NULL;
    
    /* Generate backup path with timestamp */
    time_t now = time(NULL);
    struct tm* tm_info = localtime(&now);
    
    char* backup = (char*)malloc(strlen(path) + 30);
    if (!backup) return NULL;
    
    char timestamp[20];
    strftime(timestamp, sizeof(timestamp), "%Y%m%d_%H%M%S", tm_info);
    
    snprintf(backup, strlen(path) + 30, "%s.backup.%s", path, timestamp);
    
    return backup;
}