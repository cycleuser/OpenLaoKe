/* OpenLaoKe C - Read tool implementation */

#include "../include/tools/read_tool.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <errno.h>

ToolResultBlock* read_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    ReadToolInput* input = read_tool_input_from_json(input_json);
    if (!input) {
        return tool_result_block_create("read_error", "Invalid input JSON", true);
    }
    
    /* Check if file exists */
    if (!file_exists(input->file_path)) {
        char error[512];
        snprintf(error, sizeof(error), "File does not exist: %s", input->file_path);
        read_tool_input_destroy(input);
        return tool_result_block_create("read_error", error, true);
    }
    
    /* Check if binary file */
    if (is_binary_file(input->file_path)) {
        char error[512];
        snprintf(error, sizeof(error), "Cannot read binary file: %s", input->file_path);
        read_tool_input_destroy(input);
        return tool_result_block_create("read_error", error, true);
    }
    
    /* Open file */
    FILE* f = fopen(input->file_path, "r");
    if (!f) {
        char error[512];
        snprintf(error, sizeof(error), "Failed to open file: %s (%s)", 
                 input->file_path, strerror(errno));
        read_tool_input_destroy(input);
        return tool_result_block_create("read_error", error, true);
    }
    
    /* Get file size */
    fseek(f, 0, SEEK_END);
    long file_size = ftell(f);
    fseek(f, 0, SEEK_SET);
    
    /* Allocate buffer */
    char* content = (char*)malloc(file_size + 1);
    if (!content) {
        fclose(f);
        read_tool_input_destroy(input);
        return tool_result_block_create("read_error", "Memory allocation failed", true);
    }
    
    /* Read file */
    size_t bytes_read = fread(content, 1, file_size, f);
    content[bytes_read] = '\0';
    fclose(f);
    
    /* Process line numbers if requested */
    if (input->show_line_numbers) {
        /* Add line numbers */
        char* numbered_content = (char*)malloc(file_size * 2 + 1000);
        if (numbered_content) {
            char* src = content;
            char* dst = numbered_content;
            int line_num = 1;
            
            while (*src) {
                /* Add line number */
                dst += sprintf(dst, "%6d: ", line_num);
                
                /* Copy line */
                while (*src && *src != '\n') {
                    *dst++ = *src++;
                }
                
                /* Copy newline */
                if (*src == '\n') {
                    *dst++ = *src++;
                }
                
                line_num++;
            }
            *dst = '\0';
            
            free(content);
            content = numbered_content;
            bytes_read = dst - numbered_content;
        }
    }
    
    /* Handle offset and limit */
    if (input->offset > 0 || input->limit > 0) {
        /* Count lines */
        int total_lines = 0;
        for (char* p = content; *p; p++) {
            if (*p == '\n') total_lines++;
        }
        
        /* Find start and end positions */
        char* start = content;
        int line_count = 0;
        
        if (input->offset > 0) {
            while (*start && line_count < input->offset) {
                if (*start == '\n') line_count++;
                start++;
            }
        }
        
        char* end = start;
        line_count = 0;
        
        if (input->limit > 0) {
            while (*end && line_count < input->limit) {
                if (*end == '\n') line_count++;
                end++;
            }
        } else {
            end = content + bytes_read;
        }
        
        /* Extract portion */
        size_t portion_size = end - start;
        char* portion = (char*)malloc(portion_size + 1);
        if (portion) {
            strncpy(portion, start, portion_size);
            portion[portion_size] = '\0';
            free(content);
            content = portion;
            bytes_read = portion_size;
        }
    }
    
    /* Create result */
    ReadToolResult* result = read_tool_result_create();
    result->content = content;
    result->bytes_read = bytes_read;
    result->total_lines = count_file_lines(input->file_path);
    
    char* result_json = read_tool_result_to_json(result);
    ToolResultBlock* block = tool_result_block_create("read_result", 
        result_json ? result_json : content, false);
    
    free(result_json);
    read_tool_result_destroy(result);
    read_tool_input_destroy(input);
    
    return block;
}

ReadToolInput* read_tool_input_from_json(const char* json) {
    if (!json) return NULL;
    
    ReadToolInput* input = (ReadToolInput*)calloc(1, sizeof(ReadToolInput));
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
    
    /* Set defaults */
    input->offset = 0;
    input->limit = 0;
    input->show_line_numbers = false;
    
    return input;
}

void read_tool_input_destroy(ReadToolInput* input) {
    if (!input) return;
    free(input->file_path);
    free(input);
}

ReadToolResult* read_tool_result_create(void) {
    return (ReadToolResult*)calloc(1, sizeof(ReadToolResult));
}

void read_tool_result_destroy(ReadToolResult* result) {
    if (!result) return;
    free(result->content);
    free(result->encoding);
    free(result->error_message);
    free(result);
}

char* read_tool_result_to_json(ReadToolResult* result) {
    if (!result) return NULL;
    
    size_t size = 256 + (result->content ? strlen(result->content) * 2 : 0);
    char* json = (char*)malloc(size);
    if (!json) return NULL;
    
    /* Escape content for JSON */
    char* escaped_content = NULL;
    if (result->content) {
        size_t len = strlen(result->content);
        escaped_content = (char*)malloc(len * 2 + 1);
        if (escaped_content) {
            char* dst = escaped_content;
            for (const char* src = result->content; *src; src++) {
                if (*src == '"' || *src == '\\') {
                    *dst++ = '\\';
                } else if (*src == '\n') {
                    *dst++ = '\\';
                    *dst++ = 'n';
                    continue;
                } else if (*src == '\t') {
                    *dst++ = '\\';
                    *dst++ = 't';
                    continue;
                }
                *dst++ = *src;
            }
            *dst = '\0';
        }
    }
    
    snprintf(json, size,
        "{"
        "\"total_lines\":%d,"
        "\"bytes_read\":%d,"
        "\"content\":\"%s\""
        "}",
        result->total_lines,
        result->bytes_read,
        escaped_content ? escaped_content : ""
    );
    
    free(escaped_content);
    return json;
}

bool file_exists(const char* path) {
    if (!path) return false;
    struct stat st;
    return stat(path, &st) == 0;
}

bool is_binary_file(const char* path) {
    if (!path) return false;
    
    FILE* f = fopen(path, "r");
    if (!f) return false;
    
    /* Read first 512 bytes and check for null bytes */
    unsigned char buffer[512];
    size_t bytes_read = fread(buffer, 1, sizeof(buffer), f);
    fclose(f);
    
    for (size_t i = 0; i < bytes_read; i++) {
        if (buffer[i] == 0) {
            return true;  /* Binary file */
        }
    }
    
    return false;  /* Text file */
}

char* detect_encoding(const char* content, size_t length) {
    if (!content || length == 0) return strdup("UTF-8");
    
    /* Simple encoding detection */
    /* Check for BOM */
    if (length >= 3 && 
        (unsigned char)content[0] == 0xEF &&
        (unsigned char)content[1] == 0xBB &&
        (unsigned char)content[2] == 0xBF) {
        return strdup("UTF-8-BOM");
    }
    
    if (length >= 2) {
        if ((unsigned char)content[0] == 0xFF && 
            (unsigned char)content[1] == 0xFE) {
            return strdup("UTF-16-LE");
        }
        if ((unsigned char)content[0] == 0xFE && 
            (unsigned char)content[1] == 0xFF) {
            return strdup("UTF-16-BE");
        }
    }
    
    return strdup("UTF-8");
}

int count_file_lines(const char* path) {
    if (!path) return 0;
    
    FILE* f = fopen(path, "r");
    if (!f) return 0;
    
    int count = 0;
    int ch;
    while ((ch = fgetc(f)) != EOF) {
        if (ch == '\n') count++;
    }
    
    fclose(f);
    return count;
}