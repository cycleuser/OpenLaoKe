/* OpenLaoKe C - Glob tool implementation */

#include "../include/tools/glob_tool.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include <fnmatch.h>

ToolResultBlock* glob_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    GlobToolInput* input = glob_tool_input_from_json(input_json);
    if (!input) {
        return tool_result_block_create("glob_error", "Invalid input JSON", true);
    }
    
    /* Search for files */
    int match_count = 0;
    char** files = glob_search(input->pattern, input->path, &match_count, input->max_results);
    
    /* Create result */
    GlobToolResult* result = glob_tool_result_create();
    result->files = files;
    result->file_count = match_count;
    result->total_matches = match_count;
    result->truncated = (input->max_results > 0 && match_count >= input->max_results);
    result->base_path = input->path ? strdup(input->path) : strdup(".");
    
    char* result_json = glob_tool_result_to_json(result);
    ToolResultBlock* block = tool_result_block_create("glob_result", 
        result_json ? result_json : "Search completed", false);
    
    free(result_json);
    glob_tool_result_destroy(result);
    glob_tool_input_destroy(input);
    
    return block;
}

GlobToolInput* glob_tool_input_from_json(const char* json) {
    if (!json) return NULL;
    
    GlobToolInput* input = (GlobToolInput*)calloc(1, sizeof(GlobToolInput));
    if (!input) return NULL;
    
    /* Parse "pattern" field */
    const char* pattern_start = strstr(json, "\"pattern\"");
    if (pattern_start) {
        pattern_start = strchr(pattern_start, ':');
        if (pattern_start) {
            pattern_start = strchr(pattern_start, '"');
            if (pattern_start) {
                pattern_start++;
                const char* pattern_end = strchr(pattern_start, '"');
                if (pattern_end) {
                    size_t len = pattern_end - pattern_start;
                    input->pattern = (char*)malloc(len + 1);
                    strncpy(input->pattern, pattern_start, len);
                    input->pattern[len] = '\0';
                }
            }
        }
    }
    
    /* Parse "path" field */
    const char* path_start = strstr(json, "\"path\"");
    if (path_start) {
        path_start = strchr(path_start, ':');
        if (path_start) {
            path_start = strchr(path_start, '"');
            if (path_start) {
                path_start++;
                const char* path_end = strchr(path_start, '"');
                if (path_end) {
                    size_t len = path_end - path_start;
                    input->path = (char*)malloc(len + 1);
                    strncpy(input->path, path_start, len);
                    input->path[len] = '\0';
                }
            }
        }
    }
    
    /* Set defaults */
    input->recursive = true;
    input->include_hidden = false;
    input->max_results = 1000;
    input->case_sensitive = false;
    
    return input;
}

void glob_tool_input_destroy(GlobToolInput* input) {
    if (!input) return;
    free(input->pattern);
    free(input->path);
    free(input);
}

GlobToolResult* glob_tool_result_create(void) {
    return (GlobToolResult*)calloc(1, sizeof(GlobToolResult));
}

void glob_tool_result_destroy(GlobToolResult* result) {
    if (!result) return;
    
    if (result->files) {
        for (int i = 0; i < result->file_count; i++) {
            free(result->files[i]);
        }
        free(result->files);
    }
    
    free(result->base_path);
    free(result->error_message);
    free(result);
}

char* glob_tool_result_to_json(GlobToolResult* result) {
    if (!result) return NULL;
    
    /* Calculate size needed */
    size_t size = 256;
    for (int i = 0; i < result->file_count; i++) {
        size += strlen(result->files[i]) + 10;
    }
    
    char* json = (char*)malloc(size);
    if (!json) return NULL;
    
    char* p = json;
    p += sprintf(p, "{\"files\":[");
    
    for (int i = 0; i < result->file_count; i++) {
        if (i > 0) p += sprintf(p, ",");
        p += sprintf(p, "\"%s\"", result->files[i]);
    }
    
    p += sprintf(p, "],\"count\":%d", result->file_count);
    
    if (result->base_path) {
        p += sprintf(p, ",\"base_path\":\"%s\"", result->base_path);
    }
    
    p += sprintf(p, "}");
    
    return json;
}

char** glob_search(const char* pattern, const char* base_path, int* count, int max_results) {
    if (!pattern || !count) return NULL;
    
    *count = 0;
    int capacity = 100;
    char** results = (char**)malloc(capacity * sizeof(char*));
    if (!results) return NULL;
    
    const char* search_path = base_path ? base_path : ".";
    
    /* Open directory */
    DIR* dir = opendir(search_path);
    if (!dir) {
        free(results);
        return NULL;
    }
    
    struct dirent* entry;
    while ((entry = readdir(dir)) != NULL && (max_results <= 0 || *count < max_results)) {
        /* Skip . and .. */
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
        }
        
        /* Skip hidden files if not included */
        if (entry->d_name[0] == '.' && !strstr(pattern, ".")) {
            continue;
        }
        
        /* Check if matches pattern */
        if (match_glob_pattern(entry->d_name, pattern)) {
            /* Make full path */
            char full_path[4096];
            snprintf(full_path, sizeof(full_path), "%s/%s", search_path, entry->d_name);
            
            /* Expand array if needed */
            if (*count >= capacity) {
                capacity *= 2;
                char** new_results = (char**)realloc(results, capacity * sizeof(char*));
                if (!new_results) break;
                results = new_results;
            }
            
            results[*count] = strdup(full_path);
            (*count)++;
        }
    }
    
    closedir(dir);
    return results;
}

bool match_glob_pattern(const char* filename, const char* pattern) {
    if (!filename || !pattern) return false;
    
    /* Use fnmatch for glob pattern matching */
    int result = fnmatch(pattern, filename, FNM_NOESCAPE);
    return result == 0;
}