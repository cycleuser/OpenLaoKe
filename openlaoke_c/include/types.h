/* OpenLaoKe C - Core type definitions */

#ifndef OPENLAOKE_TYPES_H
#define OPENLAOKE_TYPES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* Permission modes */
typedef enum {
    PERMISSION_MODE_DEFAULT,
    PERMISSION_MODE_AUTO,
    PERMISSION_MODE_BYPASS
} PermissionMode;

/* HyperAuto operation modes */
typedef enum {
    HYPERAUTO_MODE_SEMI_AUTO,
    HYPERAUTO_MODE_FULL_AUTO,
    HYPERAUTO_MODE_HYPER_AUTO
} HyperAutoMode;

/* Permission check results */
typedef enum {
    PERMISSION_RESULT_ALLOW,
    PERMISSION_RESULT_DENY,
    PERMISSION_RESULT_ASK
} PermissionResult;

/* Task types */
typedef enum {
    TASK_TYPE_LOCAL_BASH,
    TASK_TYPE_LOCAL_AGENT,
    TASK_TYPE_REMOTE_AGENT,
    TASK_TYPE_IN_PROCESS_TEAMMATE,
    TASK_TYPE_LOCAL_WORKFLOW,
    TASK_TYPE_MONITOR_MCP,
    TASK_TYPE_DREAM
} TaskType;

/* Task lifecycle states */
typedef enum {
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_KILLED
} TaskStatus;

static inline bool is_terminal_task_status(TaskStatus status) {
    return status == TASK_STATUS_COMPLETED || 
           status == TASK_STATUS_FAILED || 
           status == TASK_STATUS_KILLED;
}

/* String conversion helpers */
const char* permission_mode_to_string(PermissionMode mode);
const char* hyperauto_mode_to_string(HyperAutoMode mode);
const char* permission_result_to_string(PermissionResult result);
const char* task_type_to_string(TaskType type);
const char* task_status_to_string(TaskStatus status);

PermissionMode string_to_permission_mode(const char* str);
HyperAutoMode string_to_hyperauto_mode(const char* str);
PermissionResult string_to_permission_result(const char* str);
TaskType string_to_task_type(const char* str);
TaskStatus string_to_task_status(const char* str);

/* Token usage tracking */
typedef struct {
    int prompt_tokens;
    int completion_tokens;
    int total_tokens;
} TokenUsage;

/* Cost information */
typedef struct {
    double prompt_cost;
    double completion_cost;
    double total_cost;
} CostInfo;

/* Tool progress callback */
typedef void (*ProgressCallback)(const char* message, void* user_data);

/* Validation result */
typedef struct {
    bool result;
    char* message;
    char* error_code;
} ValidationResult;

/* Tool result block */
typedef struct {
    char* tool_use_id;
    char* content;
    bool is_error;
    char* error_message;
} ToolResultBlock;

ToolResultBlock* tool_result_block_create(const char* tool_use_id, const char* content, bool is_error);
void tool_result_block_destroy(ToolResultBlock* block);

/* Message structure */
typedef enum {
    MESSAGE_ROLE_USER,
    MESSAGE_ROLE_ASSISTANT,
    MESSAGE_ROLE_SYSTEM
} MessageRole;

typedef struct {
    MessageRole role;
    char* content;
    char* tool_use_id;
    char* tool_name;
} Message;

Message* message_create(MessageRole role, const char* content);
void message_destroy(Message* msg);
char* message_to_json(const Message* msg);

/* Task state */
typedef struct {
    TaskType type;
    TaskStatus status;
    char* task_id;
    char* description;
    void* data;
} TaskState;

TaskState* task_state_create(TaskType type, const char* task_id);
void task_state_destroy(TaskState* state);

#endif /* OPENLAOKE_TYPES_H */
