#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <regex.h>
#include <dirent.h>
#include <sys/stat.h>
#include "../include/tool_registry.h"

typedef struct {
    char* pattern;
    char* path;
    bool ignore_case;
    bool show_line_numbers;
    int max_results;
} GrepInput;

static GrepInput* parse_grep_input(const char* json) {
    GrepInput* input = calloc(1, sizeof(GrepInput));
    if (!input) return NULL;
    
    input->ignore_case = true;
    input->show_line_numbers = true;
    input->max_results = 100;
    input->path = strdup(".");
    
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
                    input->pattern = malloc(len + 1);
                    strncpy(input->pattern, pattern_start, len);
                    input->pattern[len] = '\0';
                }
            }
        }
    }
    
    return input;
}

static int grep_file(const char* filepath, const char* pattern, bool ignore_case, 
                     char** results, int max_results, int* count) {
    FILE* f = fopen(filepath, "r");
    if (!f) return -1;
    
    regex_t regex;
    int cflags = REG_EXTENDED | (ignore_case ? REG_ICASE : 0);
    if (regcomp(&regex, pattern, cflags) != 0) {
        fclose(f);
        return -1;
    }
    
    char line[4096];
    int line_num = 0;
    
    while (fgets(line, sizeof(line), f) && *count < max_results) {
        line_num++;
        if (regexec(&regex, line, 0, NULL, 0) == 0) {
            char* match = malloc(8192);
            snprintf(match, 8192, "%s:%d: %s", filepath, line_num, line);
            results[*count] = match;
            (*count)++;
        }
    }
    
    regfree(&regex);
    fclose(f);
    return 0;
}

ToolResultBlock* grep_tool_execute_complete(Tool* tool, void* ctx, const char* input_json) {
    GrepInput* input = parse_grep_input(input_json);
    if (!input || !input->pattern) {
        return tool_result_block_create("grep_error", "Invalid input", true);
    }
    
    char** results = malloc(input->max_results * sizeof(char*));
    int count = 0;
    
    DIR* dir = opendir(input->path);
    if (!dir) {
        free(results);
        free(input->pattern);
        free(input->path);
        free(input);
        return tool_result_block_create("grep_error", "Cannot open directory", true);
    }
    
    struct dirent* entry;
    while ((entry = readdir(dir)) != NULL && count < input->max_results) {
        if (entry->d_name[0] == '.') continue;
        
        char filepath[4096];
        snprintf(filepath, sizeof(filepath), "%s/%s", input->path, entry->d_name);
        
        struct stat st;
        if (stat(filepath, &st) == 0 && S_ISREG(st.st_mode)) {
            grep_file(filepath, input->pattern, input->ignore_case, 
                     results, input->max_results, &count);
        }
    }
    
    closedir(dir);
    
    size_t result_size = 65536;
    char* output = malloc(result_size);
    output[0] = '\0';
    char* p = output;
    
    for (int i = 0; i < count; i++) {
        p += snprintf(p, result_size - (p - output), "%s", results[i]);
        free(results[i]);
    }
    
    free(results);
    free(input->pattern);
    free(input->path);
    free(input);
    
    return tool_result_block_create("grep_result", output, false);
}
