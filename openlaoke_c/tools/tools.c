/* OpenLaoKe C - Tool implementations */

#include "../include/tools.h"
#include "../include/state.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/stat.h>

/* Bash tool */
ToolResultBlock* tool_bash_execute(Tool* tool, void* ctx, const char* input) {
    /* Parse JSON input to get command */
    /* For simplicity, we'll assume input is the command directly */
    
    FILE* pipe = popen(input, "r");
    if (!pipe) {
        return tool_result_block_create("bash_error", "Failed to execute command", true);
    }
    
    char buffer[4096];
    char* output = (char*)malloc(65536);
    output[0] = '\0';
    size_t total = 0;
    
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        size_t len = strlen(buffer);
        if (total + len < 65536) {
            strcat(output, buffer);
            total += len;
        }
    }
    
    int exit_code = pclose(pipe);
    
    char result[65536];
    snprintf(result, sizeof(result), "Exit code: %d\n%s", exit_code, output);
    free(output);
    
    return tool_result_block_create("bash_result", result, exit_code != 0);
}

/* Read tool */
ToolResultBlock* tool_read_execute(Tool* tool, void* ctx, const char* filepath) {
    FILE* f = fopen(filepath, "r");
    if (!f) {
        char error[256];
        snprintf(error, sizeof(error), "Failed to open file: %s", filepath);
        return tool_result_block_create("read_error", error, true);
    }
    
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    
    char* content = (char*)malloc(size + 1);
    if (!content) {
        fclose(f);
        return tool_result_block_create("read_error", "Memory allocation failed", true);
    }
    
    fread(content, 1, size, f);
    content[size] = '\0';
    fclose(f);
    
    ToolResultBlock* result = tool_result_block_create("read_result", content, false);
    free(content);
    
    return result;
}

/* Write tool */
ToolResultBlock* tool_write_execute(Tool* tool, void* ctx, const char* input) {
    /* Parse JSON input to get filepath and content */
    /* For simplicity, input format: "filepath:content" */
    
    char* colon = strchr(input, ':');
    if (!colon) {
        return tool_result_block_create("write_error", "Invalid input format", true);
    }
    
    size_t path_len = colon - input;
    char* filepath = (char*)malloc(path_len + 1);
    strncpy(filepath, input, path_len);
    filepath[path_len] = '\0';
    
    const char* content = colon + 1;
    
    /* Create directories if needed */
    char* last_slash = strrchr(filepath, '/');
    if (last_slash) {
        *last_slash = '\0';
        char cmd[512];
        snprintf(cmd, sizeof(cmd), "mkdir -p %s", filepath);
        system(cmd);
        *last_slash = '/';
    }
    
    FILE* f = fopen(filepath, "w");
    if (!f) {
        char error[256];
        snprintf(error, sizeof(error), "Failed to create file: %s", filepath);
        free(filepath);
        return tool_result_block_create("write_error", error, true);
    }
    
    fprintf(f, "%s", content);
    fclose(f);
    
    char result[256];
    snprintf(result, sizeof(result), "Successfully wrote to: %s", filepath);
    free(filepath);
    
    return tool_result_block_create("write_result", result, false);
}

/* List directory tool */
ToolResultBlock* tool_ls_execute(Tool* tool, void* ctx, const char* path) {
    const char* dirpath = path && strlen(path) > 0 ? path : ".";
    
    DIR* dir = opendir(dirpath);
    if (!dir) {
        char error[256];
        snprintf(error, sizeof(error), "Failed to open directory: %s", dirpath);
        return tool_result_block_create("ls_error", error, true);
    }
    
    char* output = (char*)malloc(65536);
    output[0] = '\0';
    strcat(output, "Contents of ");
    strcat(output, dirpath);
    strcat(output, ":\n\n");
    
    struct dirent* entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
        }
        
        char line[512];
        snprintf(line, sizeof(line), "  %s\n", entry->d_name);
        strcat(output, line);
    }
    
    closedir(dir);
    
    ToolResultBlock* result = tool_result_block_create("ls_result", output, false);
    free(output);
    
    return result;
}

/* Register all tools */
int tools_register_all(ToolRegistry* registry) {
    if (!registry) return -1;
    
    tool_registry_register(registry, tool_create("bash", "Execute bash commands", tool_bash_execute));
    tool_registry_register(registry, tool_create("read", "Read file contents", tool_read_execute));
    tool_registry_register(registry, tool_create("write", "Write to files", tool_write_execute));
    tool_registry_register(registry, tool_create("ls", "List directory contents", tool_ls_execute));
    
    return registry->count;
}