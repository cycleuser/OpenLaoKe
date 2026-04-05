#include "../include/hyperauto_types.h"
#include <stdlib.h>
#include <string.h>
#include <time.h>

SubTask* sub_task_create(const char* name, const char* description) {
    SubTask* task = (SubTask*)calloc(1, sizeof(SubTask));
    if (!task) return NULL;
    task->name = name ? strdup(name) : NULL;
    task->description = description ? strdup(description) : NULL;
    task->status = SUB_TASK_PENDING;
    task->priority = 0;
    return task;
}

void sub_task_destroy(SubTask* task) {
    if (!task) return;
    free(task->id);
    free(task->name);
    free(task->description);
    free(task->error);
    free(task);
}

WorkflowContext* workflow_context_create(const char* request) {
    WorkflowContext* ctx = (WorkflowContext*)calloc(1, sizeof(WorkflowContext));
    if (!ctx) return NULL;
    ctx->original_request = request ? strdup(request) : NULL;
    ctx->current_state = HYPERAUTO_STATE_IDLE;
    ctx->start_time = time(NULL);
    return ctx;
}

void workflow_context_destroy(WorkflowContext* ctx) {
    if (!ctx) return;
    free(ctx->original_request);
    if (ctx->sub_tasks) {
        for (int i = 0; i < ctx->task_count; i++) {
            sub_task_destroy(ctx->sub_tasks[i]);
        }
        free(ctx->sub_tasks);
    }
    free(ctx);
}

AnalysisResult* analysis_result_create(void) {
    return (AnalysisResult*)calloc(1, sizeof(AnalysisResult));
}

void analysis_result_destroy(AnalysisResult* result) {
    if (!result) return;
    free(result->task_type);
    free(result->description);
    free(result);
}

Decision* decision_create(const char* type, const char* action) {
    Decision* d = (Decision*)calloc(1, sizeof(Decision));
    if (!d) return NULL;
    d->type = type ? strdup(type) : NULL;
    d->action = action ? strdup(action) : NULL;
    d->timestamp = time(NULL);
    return d;
}

void decision_destroy(Decision* decision) {
    if (!decision) return;
    free(decision->type);
    free(decision->reasoning);
    free(decision->action);
    free(decision);
}

Reflection* reflection_create(void) {
    return (Reflection*)calloc(1, sizeof(Reflection));
}

void reflection_destroy(Reflection* reflection) {
    if (!reflection) return;
    free(reflection->summary);
    free(reflection);
}

HyperAutoConfig* hyperauto_config_create_default(void) {
    HyperAutoConfig* config = (HyperAutoConfig*)calloc(1, sizeof(HyperAutoConfig));
    if (!config) return NULL;
    config->mode = HYPERAUTO_MODE_SEMI_AUTO;
    config->max_iterations = 100;
    config->max_parallel_tasks = 5;
    config->auto_run_tests = true;
    config->rollback_on_failure = true;
    config->reflection_enabled = true;
    config->learning_enabled = true;
    config->dry_run = false;
    config->timeout_seconds = 300;
    return config;
}

void hyperauto_config_destroy(HyperAutoConfig* config) {
    free(config);
}
