/* OpenLaoKe C - HyperAuto types */

#ifndef OPENLAOKE_HYPERAUTO_TYPES_H
#define OPENLAOKE_HYPERAUTO_TYPES_H

#include "types.h"
#include <time.h>

/* HyperAuto state */
typedef enum {
    HYPERAUTO_STATE_IDLE,
    HYPERAUTO_STATE_ANALYZING,
    HYPERAUTO_STATE_PLANNING,
    HYPERAUTO_STATE_EXECUTING,
    HYPERAUTO_STATE_VERIFYING,
    HYPERAUTO_STATE_RETRYING,
    HYPERAUTO_STATE_REFLECTING,
    HYPERAUTO_STATE_LEARNING,
    HYPERAUTO_STATE_COMPLETED,
    HYPERAUTO_STATE_FAILED
} HyperAutoState;

/* Sub-task status */
typedef enum {
    SUB_TASK_PENDING,
    SUB_TASK_RUNNING,
    SUB_TASK_COMPLETED,
    SUB_TASK_FAILED,
    SUB_TASK_SKIPPED
} SubTaskStatus;

/* Sub-task */
typedef struct {
    char* id;
    char* name;
    char* description;
    SubTaskStatus status;
    int priority;
    char** dependencies;
    int dependency_count;
    void* result;
    char* error;
    time_t start_time;
    time_t end_time;
    void* metadata;
} SubTask;

/* Workflow context */
typedef struct {
    char* original_request;
    HyperAutoState current_state;
    int iteration;
    int max_iterations;
    time_t start_time;
    time_t end_time;
    SubTask** sub_tasks;
    int task_count;
    int total_tokens;
    double total_cost;
    void* decisions;
    void* reflections;
} WorkflowContext;

/* Analysis result */
typedef struct {
    char* task_type;
    char* description;
    SubTask** sub_tasks;
    int task_count;
    char** required_skills;
    int skill_count;
    char** required_tools;
    int tool_count;
    char* estimated_complexity;
    double confidence;
} AnalysisResult;

/* Decision */
typedef struct {
    char* type;
    double confidence;
    char* reasoning;
    char* action;
    void* parameters;
    bool executed;
    time_t timestamp;
} Decision;

/* Reflection */
typedef struct {
    char* summary;
    char** successes;
    int success_count;
    char** failures;
    int failure_count;
    char** improvements;
    int improvement_count;
    double quality_score;
} Reflection;

/* HyperAuto config */
typedef struct {
    HyperAutoMode mode;
    int max_iterations;
    int max_parallel_tasks;
    bool auto_run_tests;
    bool rollback_on_failure;
    bool reflection_enabled;
    bool learning_enabled;
    bool dry_run;
    int timeout_seconds;
} HyperAutoConfig;

/* Functions */
SubTask* sub_task_create(const char* name, const char* description);
void sub_task_destroy(SubTask* task);

WorkflowContext* workflow_context_create(const char* request);
void workflow_context_destroy(WorkflowContext* ctx);

AnalysisResult* analysis_result_create(void);
void analysis_result_destroy(AnalysisResult* result);

Decision* decision_create(const char* type, const char* action);
void decision_destroy(Decision* decision);

Reflection* reflection_create(void);
void reflection_destroy(Reflection* reflection);

HyperAutoConfig* hyperauto_config_create_default(void);
void hyperauto_config_destroy(HyperAutoConfig* config);

#endif /* OPENLAOKE_HYPERAUTO_TYPES_H */