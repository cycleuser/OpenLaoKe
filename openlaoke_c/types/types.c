/* OpenLaoKe C - Type implementation */

#include "../include/types.h"
#include <stdio.h>

/* String conversion functions */
const char* permission_mode_to_string(PermissionMode mode) {
    switch (mode) {
        case PERMISSION_MODE_DEFAULT: return "default";
        case PERMISSION_MODE_AUTO: return "auto";
        case PERMISSION_MODE_BYPASS: return "bypass";
        default: return "unknown";
    }
}

const char* hyperauto_mode_to_string(HyperAutoMode mode) {
    switch (mode) {
        case HYPERAUTO_MODE_SEMI_AUTO: return "semi_auto";
        case HYPERAUTO_MODE_FULL_AUTO: return "full_auto";
        case HYPERAUTO_MODE_HYPER_AUTO: return "hyper_auto";
        default: return "unknown";
    }
}

const char* permission_result_to_string(PermissionResult result) {
    switch (result) {
        case PERMISSION_RESULT_ALLOW: return "allow";
        case PERMISSION_RESULT_DENY: return "deny";
        case PERMISSION_RESULT_ASK: return "ask";
        default: return "unknown";
    }
}

const char* task_type_to_string(TaskType type) {
    switch (type) {
        case TASK_TYPE_LOCAL_BASH: return "local_bash";
        case TASK_TYPE_LOCAL_AGENT: return "local_agent";
        case TASK_TYPE_REMOTE_AGENT: return "remote_agent";
        case TASK_TYPE_IN_PROCESS_TEAMMATE: return "in_process_teammate";
        case TASK_TYPE_LOCAL_WORKFLOW: return "local_workflow";
        case TASK_TYPE_MONITOR_MCP: return "monitor_mcp";
        case TASK_TYPE_DREAM: return "dream";
        default: return "unknown";
    }
}

const char* task_status_to_string(TaskStatus status) {
    switch (status) {
        case TASK_STATUS_PENDING: return "pending";
        case TASK_STATUS_RUNNING: return "running";
        case TASK_STATUS_COMPLETED: return "completed";
        case TASK_STATUS_FAILED: return "failed";
        case TASK_STATUS_KILLED: return "killed";
        default: return "unknown";
    }
}

/* String to enum conversion */
PermissionMode string_to_permission_mode(const char* str) {
    if (strcmp(str, "auto") == 0) return PERMISSION_MODE_AUTO;
    if (strcmp(str, "bypass") == 0) return PERMISSION_MODE_BYPASS;
    return PERMISSION_MODE_DEFAULT;
}

HyperAutoMode string_to_hyperauto_mode(const char* str) {
    if (strcmp(str, "full_auto") == 0) return HYPERAUTO_MODE_FULL_AUTO;
    if (strcmp(str, "hyper_auto") == 0) return HYPERAUTO_MODE_HYPER_AUTO;
    return HYPERAUTO_MODE_SEMI_AUTO;
}

PermissionResult string_to_permission_result(const char* str) {
    if (strcmp(str, "allow") == 0) return PERMISSION_RESULT_ALLOW;
    if (strcmp(str, "deny") == 0) return PERMISSION_RESULT_DENY;
    return PERMISSION_RESULT_ASK;
}

TaskType string_to_task_type(const char* str) {
    if (strcmp(str, "local_bash") == 0) return TASK_TYPE_LOCAL_BASH;
    if (strcmp(str, "local_agent") == 0) return TASK_TYPE_LOCAL_AGENT;
    if (strcmp(str, "remote_agent") == 0) return TASK_TYPE_REMOTE_AGENT;
    if (strcmp(str, "in_process_teammate") == 0) return TASK_TYPE_IN_PROCESS_TEAMMATE;
    if (strcmp(str, "local_workflow") == 0) return TASK_TYPE_LOCAL_WORKFLOW;
    if (strcmp(str, "monitor_mcp") == 0) return TASK_TYPE_MONITOR_MCP;
    if (strcmp(str, "dream") == 0) return TASK_TYPE_DREAM;
    return TASK_TYPE_LOCAL_BASH;
}

TaskStatus string_to_task_status(const char* str) {
    if (strcmp(str, "pending") == 0) return TASK_STATUS_PENDING;
    if (strcmp(str, "running") == 0) return TASK_STATUS_RUNNING;
    if (strcmp(str, "completed") == 0) return TASK_STATUS_COMPLETED;
    if (strcmp(str, "failed") == 0) return TASK_STATUS_FAILED;
    if (strcmp(str, "killed") == 0) return TASK_STATUS_KILLED;
    return TASK_STATUS_PENDING;
}

/* Memory management */
ToolResultBlock* tool_result_block_create(const char* tool_use_id, const char* content, bool is_error) {
    ToolResultBlock* block = (ToolResultBlock*)malloc(sizeof(ToolResultBlock));
    if (!block) return NULL;
    
    block->tool_use_id = strdup(tool_use_id);
    block->content = strdup(content);
    block->is_error = is_error;
    block->error_message = NULL;
    
    return block;
}

void tool_result_block_destroy(ToolResultBlock* block) {
    if (!block) return;
    free(block->tool_use_id);
    free(block->content);
    free(block->error_message);
    free(block);
}

Message* message_create(MessageRole role, const char* content) {
    Message* msg = (Message*)malloc(sizeof(Message));
    if (!msg) return NULL;
    
    msg->role = role;
    msg->content = strdup(content);
    msg->tool_use_id = NULL;
    msg->tool_name = NULL;
    
    return msg;
}

void message_destroy(Message* msg) {
    if (!msg) return;
    free(msg->content);
    free(msg->tool_use_id);
    free(msg->tool_name);
    free(msg);
}

char* message_to_json(const Message* msg) {
    if (!msg) return NULL;
    
    const char* role_str;
    switch (msg->role) {
        case MESSAGE_ROLE_USER: role_str = "user"; break;
        case MESSAGE_ROLE_ASSISTANT: role_str = "assistant"; break;
        case MESSAGE_ROLE_SYSTEM: role_str = "system"; break;
        default: role_str = "unknown";
    }
    
    char* json = (char*)malloc(strlen(role_str) + strlen(msg->content) + 50);
    if (!json) return NULL;
    
    sprintf(json, "{\"role\":\"%s\",\"content\":\"%s\"}", role_str, msg->content);
    return json;
}

TaskState* task_state_create(TaskType type, const char* task_id) {
    TaskState* state = (TaskState*)malloc(sizeof(TaskState));
    if (!state) return NULL;
    
    state->type = type;
    state->status = TASK_STATUS_PENDING;
    state->task_id = strdup(task_id);
    state->description = NULL;
    state->data = NULL;
    
    return state;
}

void task_state_destroy(TaskState* state) {
    if (!state) return;
    free(state->task_id);
    free(state->description);
    free(state);
}