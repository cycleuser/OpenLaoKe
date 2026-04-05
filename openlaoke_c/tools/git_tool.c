#include "../include/tools/git_tool.h"
#include "../include/types.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_GIT_OUTPUT 65536

static char* extract_json_string_value(const char* json, const char* key) {
    char* key_start = strstr(json, key);
    if (!key_start) return NULL;
    
    char* value_start = strchr(key_start + strlen(key), ':');
    if (!value_start) return NULL;
    
    while (*value_start == ' ' || *value_start == ':') value_start++;
    
    if (*value_start == '"') {
        value_start++;
        char* value_end = strchr(value_start, '"');
        if (!value_end) return NULL;
        size_t len = value_end - value_start;
        char* result = malloc(len + 1);
        strncpy(result, value_start, len);
        result[len] = '\0';
        return result;
    }
    
    return NULL;
}

static GitOperation parse_operation(const char* op_str) {
    if (!op_str) return GIT_STATUS;
    
    if (strcmp(op_str, "status") == 0) return GIT_STATUS;
    if (strcmp(op_str, "diff") == 0) return GIT_DIFF;
    if (strcmp(op_str, "log") == 0) return GIT_LOG;
    if (strcmp(op_str, "add") == 0) return GIT_ADD;
    if (strcmp(op_str, "commit") == 0) return GIT_COMMIT;
    if (strcmp(op_str, "push") == 0) return GIT_PUSH;
    if (strcmp(op_str, "pull") == 0) return GIT_PULL;
    if (strcmp(op_str, "branch") == 0) return GIT_BRANCH;
    if (strcmp(op_str, "checkout") == 0) return GIT_CHECKOUT;
    if (strcmp(op_str, "merge") == 0) return GIT_MERGE;
    if (strcmp(op_str, "rebase") == 0) return GIT_REBASE;
    if (strcmp(op_str, "stash") == 0) return GIT_STASH;
    if (strcmp(op_str, "reset") == 0) return GIT_RESET;
    if (strcmp(op_str, "revert") == 0) return GIT_REVERT;
    if (strcmp(op_str, "cherry_pick") == 0) return GIT_CHERRY_PICK;
    
    return GIT_STATUS;
}

const char* git_operation_to_string(GitOperation op) {
    switch (op) {
        case GIT_STATUS: return "status";
        case GIT_DIFF: return "diff";
        case GIT_LOG: return "log";
        case GIT_ADD: return "add";
        case GIT_COMMIT: return "commit";
        case GIT_PUSH: return "push";
        case GIT_PULL: return "pull";
        case GIT_BRANCH: return "branch";
        case GIT_CHECKOUT: return "checkout";
        case GIT_MERGE: return "merge";
        case GIT_REBASE: return "rebase";
        case GIT_STASH: return "stash";
        case GIT_RESET: return "reset";
        case GIT_REVERT: return "revert";
        case GIT_CHERRY_PICK: return "cherry-pick";
        default: return "status";
    }
}

static char* run_git_command(const char* repo_path, GitOperation op, const char** args, int arg_count) {
    char* output = malloc(MAX_GIT_OUTPUT);
    size_t offset = 0;
    
    char cmd[512];
    offset += snprintf(cmd, sizeof(cmd), "git %s", git_operation_to_string(op));
    
    for (int i = 0; i < arg_count && offset < 400; i++) {
        offset += snprintf(cmd + offset, sizeof(cmd) - offset, " %s", args[i]);
    }
    
    FILE* fp = popen(cmd, "r");
    if (!fp) {
        snprintf(output, MAX_GIT_OUTPUT, "Error: Failed to execute git command: %s", cmd);
        return output;
    }
    
    offset = 0;
    char line[1024];
    while (fgets(line, sizeof(line), fp) && offset < MAX_GIT_OUTPUT - 1024) {
        offset += snprintf(output + offset, MAX_GIT_OUTPUT - offset, "%s", line);
    }
    
    int exit_code = pclose(fp);
    
    if (exit_code != 0) {
        offset += snprintf(output + offset, MAX_GIT_OUTPUT - offset, 
                          "\n[Exit code: %d]", exit_code);
    }
    
    return output;
}

GitToolInput* git_tool_input_from_json(const char* json) {
    GitToolInput* input = calloc(1, sizeof(GitToolInput));
    if (!input) return NULL;
    
    char* op_str = extract_json_string_value(json, "\"operation\"");
    input->operation = parse_operation(op_str);
    free(op_str);
    
    input->repo_path = extract_json_string_value(json, "\"repo_path\"");
    input->message = extract_json_string_value(json, "\"message\"");
    input->branch = extract_json_string_value(json, "\"branch\"");
    
    char* porcelain_str = extract_json_string_value(json, "\"porcelain\"");
    if (porcelain_str && strcmp(porcelain_str, "true") == 0) {
        input->porcelain = true;
    }
    free(porcelain_str);
    
    char* force_str = extract_json_string_value(json, "\"force\"");
    if (force_str && strcmp(force_str, "true") == 0) {
        input->force = true;
    }
    free(force_str);
    
    char* count_str = extract_json_string_value(json, "\"count\"");
    if (count_str) {
        input->count = atoi(count_str);
    }
    free(count_str);
    
    return input;
}

void git_tool_input_destroy(GitToolInput* input) {
    if (!input) return;
    free(input->repo_path);
    free(input->message);
    free(input->branch);
    for (int i = 0; i < input->arg_count; i++) {
        free(input->args[i]);
    }
    free(input->args);
    free(input);
}

GitToolResult* git_tool_result_create(void) {
    GitToolResult* result = calloc(1, sizeof(GitToolResult));
    if (!result) return NULL;
    
    result->stdout_output = strdup("");
    result->stderr_output = strdup("");
    result->exit_code = 0;
    result->success = true;
    
    return result;
}

void git_tool_result_destroy(GitToolResult* result) {
    if (!result) return;
    free(result->stdout_output);
    free(result->stderr_output);
    free(result->error_message);
    for (int i = 0; i < result->file_count; i++) {
        free(result->files_changed[i]);
    }
    free(result->files_changed);
    free(result);
}

char* git_tool_result_to_json(GitToolResult* result) {
    char* json = malloc(1024);
    snprintf(json, 1024,
             "{\"success\": %s, \"exit_code\": %d, \"output\": \"%s\"}",
             result->success ? "true" : "false",
             result->exit_code,
             result->stdout_output ? result->stdout_output : "");
    return json;
}

ToolResultBlock* git_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    (void)tool;
    (void)ctx;
    
    GitToolInput* input = git_tool_input_from_json(input_json);
    if (!input) {
        return tool_result_block_create("git_error", 
            "Error: Failed to parse input JSON", true);
    }
    
    const char* args[10];
    int arg_count = 0;
    
    switch (input->operation) {
        case GIT_STATUS:
            if (input->porcelain) {
                args[arg_count++] = "--porcelain";
            }
            break;
        case GIT_LOG:
            if (input->count > 0) {
                char count_arg[32];
                snprintf(count_arg, sizeof(count_arg), "-n%d", input->count);
                args[arg_count++] = count_arg;
            }
            args[arg_count++] = "--oneline";
            break;
        case GIT_COMMIT:
            if (input->message) {
                char msg_arg[256];
                snprintf(msg_arg, sizeof(msg_arg), "-m\"%s\"", input->message);
                args[arg_count++] = msg_arg;
            }
            break;
        case GIT_BRANCH:
            if (input->branch) {
                args[arg_count++] = input->branch;
            }
            break;
        case GIT_CHECKOUT:
            if (input->branch) {
                args[arg_count++] = input->branch;
            }
            if (input->force) {
                args[arg_count++] = "-f";
            }
            break;
        case GIT_PUSH:
        case GIT_PULL:
            if (input->force) {
                args[arg_count++] = "-f";
            }
            break;
        default:
            break;
    }
    
    char* output = run_git_command(input->repo_path, input->operation, args, arg_count);
    
    GitToolResult* result = git_tool_result_create();
    result->stdout_output = output;
    result->success = (strstr(output, "Error:") == NULL);
    
    char* json = git_tool_result_to_json(result);
    
    git_tool_input_destroy(input);
    git_tool_result_destroy(result);
    
    ToolResultBlock* block = tool_result_block_create("git_result", json, false);
    free(json);
    return block;
}

Tool* git_tool_create(void) {
    Tool* tool = calloc(1, sizeof(Tool));
    tool->name = strdup("Git");
    tool->description = strdup(
        "Execute git commands for version control. "
        "Operations: status, diff, log, add, commit, push, pull, branch, checkout, etc.");
    tool->execute = git_tool_execute;
    tool->is_read_only = false;
    tool->is_destructive = true;
    tool->is_concurrency_safe = true;
    tool->requires_approval = true;
    return tool;
}