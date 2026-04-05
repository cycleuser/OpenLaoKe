/* OpenLaoKe C - Git tool */

#ifndef OPENLAOKE_TOOL_GIT_H
#define OPENLAOKE_TOOL_GIT_H

#include "../types.h"
#include "../tool_registry.h"
#include <time.h>

/* Git operation type */
typedef enum {
    GIT_STATUS,
    GIT_DIFF,
    GIT_LOG,
    GIT_ADD,
    GIT_COMMIT,
    GIT_PUSH,
    GIT_PULL,
    GIT_BRANCH,
    GIT_CHECKOUT,
    GIT_MERGE,
    GIT_REBASE,
    GIT_STASH,
    GIT_RESET,
    GIT_REVERT,
    GIT_CHERRY_PICK
} GitOperation;

/* Git tool input */
typedef struct {
    GitOperation operation;
    char** args;
    int arg_count;
    char* repo_path;
    bool porcelain;
    int count;
    char* message;
    char* branch;
    bool force;
} GitToolInput;

/* Git tool result */
typedef struct {
    char* stdout_output;
    char* stderr_output;
    int exit_code;
    bool success;
    char* error_message;
    char** files_changed;
    int file_count;
} GitToolResult;

/* Git status info */
typedef struct {
    char* file_path;
    char status;  /* 'M' modified, 'A' added, 'D' deleted, '?' untracked */
    bool staged;
    bool conflicts;
} GitStatusInfo;

/* Git commit info */
typedef struct {
    char* hash;
    char* message;
    char* author;
    char* email;
    time_t timestamp;
    char** files_changed;
    int file_count;
} GitCommitInfo;

/* Git tool functions */
ToolResultBlock* git_tool_execute(Tool* tool, void* ctx, const char* input_json);
GitToolInput* git_tool_input_from_json(const char* json);
void git_tool_input_destroy(GitToolInput* input);
GitToolResult* git_tool_result_create(void);
void git_tool_result_destroy(GitToolResult* result);
char* git_tool_result_to_json(GitToolResult* result);

/* Git utilities */
bool is_git_repo(const char* path);
GitStatusInfo** git_get_status(const char* repo_path, int* count);
GitCommitInfo** git_get_log(const char* repo_path, int count, int* actual_count);
char* git_get_current_branch(const char* repo_path);
char** git_get_branches(const char* repo_path, int* count);

#endif /* OPENLAOKE_TOOL_GIT_H */