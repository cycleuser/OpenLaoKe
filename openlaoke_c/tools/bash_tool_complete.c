#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <errno.h>
#include <time.h>
#include "../include/tool_registry.h"

typedef struct {
    char* command;
    char* description;
    int timeout;
    bool capture_output;
} BashInput;

static BashInput* parse_bash_input(const char* json) {
    BashInput* input = calloc(1, sizeof(BashInput));
    if (!input) return NULL;
    
    input->timeout = 300;
    input->capture_output = true;
    
    const char* cmd_start = strstr(json, "\"command\"");
    if (cmd_start) {
        cmd_start = strchr(cmd_start, ':');
        if (cmd_start) {
            cmd_start = strchr(cmd_start, '"');
            if (cmd_start) {
                cmd_start++;
                const char* cmd_end = strchr(cmd_start, '"');
                if (cmd_end) {
                    size_t len = cmd_end - cmd_start;
                    input->command = malloc(len + 1);
                    strncpy(input->command, cmd_start, len);
                    input->command[len] = '\0';
                }
            }
        }
    }
    
    return input;
}

ToolResultBlock* bash_tool_execute_complete(Tool* tool, void* ctx, const char* input_json) {
    BashInput* input = parse_bash_input(input_json);
    if (!input || !input->command) {
        return tool_result_block_create("bash_error", "Invalid input", true);
    }
    
    time_t start_time = time(NULL);
    
    FILE* pipe = popen(input->command, "r");
    if (!pipe) {
        char error[256];
        snprintf(error, sizeof(error), "Failed to execute: %s", strerror(errno));
        free(input->command);
        free(input);
        return tool_result_block_create("bash_error", error, true);
    }
    
    size_t buffer_size = 65536;
    char* output = malloc(buffer_size);
    output[0] = '\0';
    size_t total = 0;
    char buffer[4096];
    
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        size_t len = strlen(buffer);
        if (total + len < buffer_size) {
            strcat(output, buffer);
            total += len;
        }
    }
    
    int exit_code = pclose(pipe);
    time_t end_time = time(NULL);
    double duration = difftime(end_time, start_time);
    
    size_t result_size = buffer_size + 512;
    char* result = malloc(result_size);
    snprintf(result, result_size,
        "Exit code: %d\nDuration: %.1fs\n\n%s",
        exit_code, duration, output);
    
    free(output);
    free(input->command);
    free(input);
    
    bool is_error = (exit_code != 0);
    ToolResultBlock* block = tool_result_block_create("bash_result", result, is_error);
    free(result);
    
    return block;
}
