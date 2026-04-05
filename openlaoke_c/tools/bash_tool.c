/* OpenLaoKe C - Bash tool implementation */

#include "../include/tools/bash_tool.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <signal.h>
#include <errno.h>
#include <time.h>

ToolResultBlock* bash_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    BashToolInput* input = bash_tool_input_from_json(input_json);
    if (!input) {
        return tool_result_block_create("bash_error", "Invalid input JSON", true);
    }
    
    BashToolResult* result = bash_tool_result_create();
    if (!result) {
        bash_tool_input_destroy(input);
        return tool_result_block_create("bash_error", "Memory allocation failed", true);
    }
    
    /* Execute command */
    FILE* pipe = NULL;
    char* stdout_buffer = NULL;
    char* stderr_buffer = NULL;
    size_t stdout_size = 0;
    size_t stderr_size = 0;
    
    time_t start_time = time(NULL);
    
    /* Build command with directory change if needed */
    char* full_command = NULL;
    if (input->workdir) {
        full_command = (char*)malloc(strlen(input->workdir) + strlen(input->command) + 20);
        sprintf(full_command, "cd '%s' && %s", input->workdir, input->command);
    } else {
        full_command = strdup(input->command);
    }
    
    /* Open pipe for both stdout and stderr */
    pipe = popen(full_command, "r");
    if (!pipe) {
        result->success = false;
        result->error_message = strdup(strerror(errno));
        free(full_command);
        bash_tool_input_destroy(input);
        
        ToolResultBlock* block = tool_result_block_create("bash_result", 
            result->error_message ? result->error_message : "Unknown error", true);
        bash_tool_result_destroy(result);
        return block;
    }
    
    /* Read output */
    char buffer[4096];
    size_t buffer_size = 65536;  /* 64KB initial size */
    stdout_buffer = (char*)malloc(buffer_size);
    stdout_buffer[0] = '\0';
    
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        size_t len = strlen(buffer);
        if (stdout_size + len >= buffer_size) {
            buffer_size *= 2;
            char* new_buffer = (char*)realloc(stdout_buffer, buffer_size);
            if (!new_buffer) {
                result->success = false;
                result->error_message = strdup("Output too large");
                free(stdout_buffer);
                pclose(pipe);
                free(full_command);
                bash_tool_input_destroy(input);
                bash_tool_result_destroy(result);
                return tool_result_block_create("bash_error", result->error_message, true);
            }
            stdout_buffer = new_buffer;
        }
        strcat(stdout_buffer + stdout_size, buffer);
        stdout_size += len;
    }
    
    int exit_code = pclose(pipe);
    time_t end_time = time(NULL);
    
    result->stdout_output = stdout_buffer;
    result->exit_code = WIFEXITED(exit_code) ? WEXITSTATUS(exit_code) : exit_code;
    result->success = (result->exit_code == 0);
    result->execution_time = difftime(end_time, start_time);
    
    if (!result->success && input->check_exit_code) {
        char error_msg[256];
        snprintf(error_msg, sizeof(error_msg), "Command exited with code %d", result->exit_code);
        result->error_message = strdup(error_msg);
    }
    
    char* result_json = bash_tool_result_to_json(result);
    ToolResultBlock* block = tool_result_block_create("bash_result", result_json, !result->success);
    
    free(result_json);
    free(full_command);
    bash_tool_input_destroy(input);
    bash_tool_result_destroy(result);
    
    return block;
}

BashToolInput* bash_tool_input_from_json(const char* json) {
    if (!json) return NULL;
    
    BashToolInput* input = (BashToolInput*)calloc(1, sizeof(BashToolInput));
    if (!input) return NULL;
    
    /* Simple JSON parsing - in production, use a JSON library */
    /* Parse "command" field */
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
                    input->command = (char*)malloc(len + 1);
                    strncpy(input->command, cmd_start, len);
                    input->command[len] = '\0';
                }
            }
        }
    }
    
    /* Parse "description" field */
    const char* desc_start = strstr(json, "\"description\"");
    if (desc_start) {
        desc_start = strchr(desc_start, ':');
        if (desc_start) {
            desc_start = strchr(desc_start, '"');
            if (desc_start) {
                desc_start++;
                const char* desc_end = strchr(desc_start, '"');
                if (desc_end) {
                    size_t len = desc_end - desc_start;
                    input->description = (char*)malloc(len + 1);
                    strncpy(input->description, desc_start, len);
                    input->description[len] = '\0';
                }
            }
        }
    }
    
    /* Set defaults */
    input->timeout = 300;  /* 5 minutes */
    input->capture_output = true;
    input->check_exit_code = true;
    
    return input;
}

void bash_tool_input_destroy(BashToolInput* input) {
    if (!input) return;
    free(input->command);
    free(input->description);
    free(input->workdir);
    free(input);
}

BashToolResult* bash_tool_result_create(void) {
    return (BashToolResult*)calloc(1, sizeof(BashToolResult));
}

void bash_tool_result_destroy(BashToolResult* result) {
    if (!result) return;
    free(result->stdout_output);
    free(result->stderr_output);
    free(result->error_message);
    free(result);
}

char* bash_tool_result_to_json(BashToolResult* result) {
    if (!result) return NULL;
    
    /* Allocate large enough buffer */
    size_t size = 1024 + (result->stdout_output ? strlen(result->stdout_output) * 2 : 0);
    char* json = (char*)malloc(size);
    if (!json) return NULL;
    
    /* Escape stdout output for JSON */
    char* escaped_stdout = NULL;
    if (result->stdout_output) {
        size_t len = strlen(result->stdout_output);
        escaped_stdout = (char*)malloc(len * 2 + 1);
        if (escaped_stdout) {
            char* dst = escaped_stdout;
            for (const char* src = result->stdout_output; *src; src++) {
                if (*src == '"' || *src == '\\') {
                    *dst++ = '\\';
                }
                *dst++ = *src;
            }
            *dst = '\0';
        }
    }
    
    snprintf(json, size,
        "{"
        "\"exit_code\":%d,"
        "\"success\":%s,"
        "\"stdout\":\"%s\","
        "\"execution_time\":%.2f"
        "}",
        result->exit_code,
        result->success ? "true" : "false",
        escaped_stdout ? escaped_stdout : "",
        result->execution_time
    );
    
    free(escaped_stdout);
    return json;
}

BashSafetyLevel bash_classify_safety(const char* command) {
    if (!command) return BASH_SAFETY_UNKNOWN;
    
    /* Safe commands - readonly */
    const char* safe_commands[] = {
        "ls", "cat", "head", "tail", "grep", "find", "pwd", "whoami",
        "echo", "which", "type", "stat", "file", "wc", "sort", "uniq",
        NULL
    };
    
    /* Dangerous commands */
    const char* dangerous_commands[] = {
        "rm -rf", "sudo", "chmod 777", "chown", "mkfs", "dd if=",
        "> /dev/", "curl | bash", "wget | bash", "eval", "exec",
        NULL
    };
    
    /* Check for dangerous commands first */
    for (int i = 0; dangerous_commands[i]; i++) {
        if (strstr(command, dangerous_commands[i])) {
            return BASH_SAFETY_DANGEROUS;
        }
    }
    
    /* Check for safe commands */
    char first_word[64] = {0};
    sscanf(command, "%63s", first_word);
    
    for (int i = 0; safe_commands[i]; i++) {
        if (strcmp(first_word, safe_commands[i]) == 0) {
            return BASH_SAFETY_SAFE;
        }
    }
    
    /* Check for redirection or pipe */
    if (strchr(command, '>') || strchr(command, '<') || strchr(command, '|')) {
        return BASH_SAFETY_MODERATE;
    }
    
    return BASH_SAFETY_MODERATE;
}

bool bash_is_readonly_command(const char* command) {
    return bash_classify_safety(command) == BASH_SAFETY_SAFE;
}

bool bash_requires_confirmation(const char* command) {
    BashSafetyLevel level = bash_classify_safety(command);
    return level >= BASH_SAFETY_MODERATE;
}