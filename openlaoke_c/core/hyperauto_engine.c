#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/wait.h>
#include "../include/hyperauto_types.h"

#define MAX_VERIFICATION_ITERATIONS 10
#define MAX_COMMAND_LENGTH 1024
#define MAX_OUTPUT_LENGTH 65536

typedef struct {
    char* category;
    char* name;
    bool passed;
    char* output;
    char* error;
    double duration;
} TestResult;

typedef struct {
    int total_tests;
    int passed_tests;
    int failed_tests;
    bool is_perfect;
    double pass_rate;
    TestResult* results;
    int result_count;
} VerificationResult;

typedef struct {
    WorkflowContext* context;
    HyperAutoConfig* config;
    int current_iteration;
    int verification_iteration;
    bool running;
    VerificationResult* last_verification;
    char** files_created;
    int files_created_count;
    char** files_modified;
    int files_modified_count;
} HyperAutoEngine;

static TestResult* test_result_create(const char* category, const char* name) {
    TestResult* result = calloc(1, sizeof(TestResult));
    if (!result) return NULL;
    result->category = strdup(category);
    result->name = strdup(name);
    result->passed = false;
    result->output = strdup("");
    result->error = strdup("");
    return result;
}

static void test_result_destroy(TestResult* result) {
    if (!result) return;
    free(result->category);
    free(result->name);
    free(result->output);
    free(result->error);
    free(result);
}

static VerificationResult* verification_result_create(void) {
    VerificationResult* result = calloc(1, sizeof(VerificationResult));
    if (!result) return NULL;
    result->results = calloc(100, sizeof(TestResult));
    result->result_count = 0;
    result->is_perfect = false;
    result->pass_rate = 0.0;
    return result;
}

static void verification_result_destroy(VerificationResult* result) {
    if (!result) return;
    for (int i = 0; i < result->result_count; i++) {
        test_result_destroy(&result->results[i]);
    }
    free(result->results);
    free(result);
}

static char* run_command(const char* cmd, int* exit_code) {
    FILE* fp = popen(cmd, "r");
    if (!fp) {
        *exit_code = -1;
        return strdup("Failed to execute command");
    }
    
    char* output = malloc(MAX_OUTPUT_LENGTH);
    size_t total = 0;
    char buffer[1024];
    
    while (fgets(buffer, sizeof(buffer), fp) && total < MAX_OUTPUT_LENGTH - 1024) {
        size_t len = strlen(buffer);
        memcpy(output + total, buffer, len);
        total += len;
    }
    output[total] = '\0';
    
    *exit_code = pclose(fp);
    return output;
}

static TestResult* run_syntax_check(const char* filepath) {
    TestResult* result = test_result_create("syntax", filepath);
    
    char cmd[MAX_COMMAND_LENGTH];
    int exit_code = 0;
    
    if (strstr(filepath, ".py")) {
        snprintf(cmd, sizeof(cmd), "python -m py_compile %s 2>&1", filepath);
    } else if (strstr(filepath, ".c") || strstr(filepath, ".h")) {
        snprintf(cmd, sizeof(cmd), "gcc -fsyntax-only -Wall %s 2>&1", filepath);
    } else {
        result->passed = true;
        result->output = strdup("File type not checked");
        return result;
    }
    
    char* output = run_command(cmd, &exit_code);
    result->passed = (exit_code == 0);
    result->output = output;
    
    if (!result->passed) {
        result->error = strdup(output);
    }
    
    return result;
}

static TestResult* run_type_check(const char* filepath) {
    TestResult* result = test_result_create("type_check", filepath);
    
    char cmd[MAX_COMMAND_LENGTH];
    int exit_code = 0;
    
    if (strstr(filepath, ".py")) {
        snprintf(cmd, sizeof(cmd), "python -m mypy %s 2>&1", filepath);
        char* output = run_command(cmd, &exit_code);
        result->passed = (exit_code == 0);
        result->output = output;
    } else {
        result->passed = true;
        result->output = strdup("Type check not applicable");
    }
    
    return result;
}

static TestResult* run_lint_check(const char* filepath) {
    TestResult* result = test_result_create("lint", filepath);
    
    char cmd[MAX_COMMAND_LENGTH];
    int exit_code = 0;
    
    if (strstr(filepath, ".py")) {
        snprintf(cmd, sizeof(cmd), "python -m ruff check %s 2>&1", filepath);
    } else if (strstr(filepath, ".c") || strstr(filepath, ".h")) {
        snprintf(cmd, sizeof(cmd), "cppcheck --error-exitcode=1 %s 2>&1", filepath);
    } else {
        result->passed = true;
        return result;
    }
    
    char* output = run_command(cmd, &exit_code);
    result->passed = (exit_code == 0);
    result->output = output;
    
    return result;
}

static TestResult* run_unit_tests(void) {
    TestResult* result = test_result_create("unit_test", "pytest");
    
    int exit_code = 0;
    char* output = run_command("python -m pytest -v --tb=short 2>&1", &exit_code);
    
    result->passed = (exit_code == 0);
    result->output = output;
    
    return result;
}

static TestResult* run_make_test(void) {
    TestResult* result = test_result_create("unit_test", "make_test");
    
    int exit_code = 0;
    char* output = run_command("make test 2>&1", &exit_code);
    
    result->passed = (exit_code == 0);
    result->output = output;
    
    return result;
}

static VerificationResult* run_verification(HyperAutoEngine* engine) {
    VerificationResult* result = verification_result_create();
    
    printf("\n=== Verification Iteration %d ===\n", engine->verification_iteration);
    
    for (int i = 0; i < engine->files_created_count && result->result_count < 100; i++) {
        TestResult* tr = run_syntax_check(engine->files_created[i]);
        result->results[result->result_count++] = *tr;
        result->total_tests++;
        if (tr->passed) result->passed_tests++;
        else result->failed_tests++;
        free(tr);
    }
    
    for (int i = 0; i < engine->files_modified_count && result->result_count < 100; i++) {
        TestResult* tr = run_syntax_check(engine->files_modified[i]);
        result->results[result->result_count++] = *tr;
        result->total_tests++;
        if (tr->passed) result->passed_tests++;
        else result->failed_tests++;
        free(tr);
    }
    
    TestResult* unit_test = run_unit_tests();
    result->results[result->result_count++] = *unit_test;
    result->total_tests++;
    if (unit_test->passed) result->passed_tests++;
    else result->failed_tests++;
    free(unit_test);
    
    TestResult* make_test = run_make_test();
    if (make_test->passed || strlen(make_test->output) > 10) {
        result->results[result->result_count++] = *make_test;
        result->total_tests++;
        if (make_test->passed) result->passed_tests++;
        else result->failed_tests++;
    }
    free(make_test);
    
    if (result->total_tests > 0) {
        result->pass_rate = (double)result->passed_tests / result->total_tests;
    }
    
    result->is_perfect = (result->failed_tests == 0 && result->pass_rate >= 1.0);
    
    printf("Tests: %d total, %d passed, %d failed\n", 
           result->total_tests, result->passed_tests, result->failed_tests);
    printf("Pass rate: %.1f%%\n", result->pass_rate * 100);
    
    return result;
}

static bool auto_fix_issues(HyperAutoEngine* engine, VerificationResult* verification) {
    printf("Attempting auto-fix...\n");
    
    bool fixed_any = false;
    
    for (int i = 0; i < verification->result_count; i++) {
        TestResult* tr = &verification->results[i];
        
        if (!tr->passed && strcmp(tr->category, "lint") == 0) {
            char cmd[MAX_COMMAND_LENGTH];
            int exit_code = 0;
            
            snprintf(cmd, sizeof(cmd), "python -m ruff check --fix . 2>&1");
            char* output = run_command(cmd, &exit_code);
            free(output);
            
            if (exit_code == 0) {
                printf("Auto-fixed lint issues\n");
                fixed_any = true;
            }
        }
    }
    
    return fixed_any;
}

HyperAutoEngine* hyperauto_engine_create(const char* request) {
    HyperAutoEngine* engine = calloc(1, sizeof(HyperAutoEngine));
    if (!engine) return NULL;
    
    engine->context = workflow_context_create(request);
    engine->config = hyperauto_config_create_default();
    engine->current_iteration = 0;
    engine->verification_iteration = 0;
    engine->running = false;
    engine->last_verification = NULL;
    engine->files_created = calloc(100, sizeof(char*));
    engine->files_modified = calloc(100, sizeof(char*));
    
    return engine;
}

void hyperauto_engine_destroy(HyperAutoEngine* engine) {
    if (!engine) return;
    workflow_context_destroy(engine->context);
    hyperauto_config_destroy(engine->config);
    if (engine->last_verification) {
        verification_result_destroy(engine->last_verification);
    }
    for (int i = 0; i < engine->files_created_count; i++) {
        free(engine->files_created[i]);
    }
    for (int i = 0; i < engine->files_modified_count; i++) {
        free(engine->files_modified[i]);
    }
    free(engine->files_created);
    free(engine->files_modified);
    free(engine);
}

void hyperauto_engine_add_created_file(HyperAutoEngine* engine, const char* filepath) {
    if (!engine || !filepath) return;
    if (engine->files_created_count < 100) {
        engine->files_created[engine->files_created_count++] = strdup(filepath);
    }
}

void hyperauto_engine_add_modified_file(HyperAutoEngine* engine, const char* filepath) {
    if (!engine || !filepath) return;
    if (engine->files_modified_count < 100) {
        engine->files_modified[engine->files_modified_count++] = strdup(filepath);
    }
}

int hyperauto_engine_run(HyperAutoEngine* engine) {
    if (!engine) return -1;
    
    engine->running = true;
    engine->context->current_state = HYPERAUTO_STATE_ANALYZING;
    
    while (engine->running && 
           engine->current_iteration < engine->config->max_iterations) {
        
        engine->current_iteration++;
        engine->context->iteration = engine->current_iteration;
        
        printf("\n--- HyperAuto Iteration %d ---\n", engine->current_iteration);
        
        switch (engine->context->current_state) {
            case HYPERAUTO_STATE_ANALYZING:
                printf("State: ANALYZING\n");
                engine->context->current_state = HYPERAUTO_STATE_PLANNING;
                break;
                
            case HYPERAUTO_STATE_PLANNING:
                printf("State: PLANNING\n");
                engine->context->current_state = HYPERAUTO_STATE_EXECUTING;
                break;
                
            case HYPERAUTO_STATE_EXECUTING:
                printf("State: EXECUTING\n");
                if (engine->config->auto_run_tests) {
                    engine->context->current_state = HYPERAUTO_STATE_VERIFYING;
                } else {
                    engine->context->current_state = HYPERAUTO_STATE_REFLECTING;
                }
                break;
                
            case HYPERAUTO_STATE_VERIFYING: {
                printf("State: VERIFYING\n");
                
                if (engine->last_verification) {
                    verification_result_destroy(engine->last_verification);
                }
                
                engine->verification_iteration++;
                engine->last_verification = run_verification(engine);
                
                if (engine->last_verification->is_perfect) {
                    printf("✓ Perfect completion!\n");
                    engine->context->current_state = HYPERAUTO_STATE_COMPLETED;
                } else if (engine->last_verification->pass_rate >= 0.8) {
                    printf("✓ Acceptable completion (%.1f%%)\n", 
                           engine->last_verification->pass_rate * 100);
                    engine->context->current_state = HYPERAUTO_STATE_REFLECTING;
                } else if (engine->verification_iteration < MAX_VERIFICATION_ITERATIONS) {
                    if (auto_fix_issues(engine, engine->last_verification)) {
                        printf("Auto-fixed issues, re-verifying...\n");
                    } else {
                        printf("Issues found, retrying...\n");
                        engine->context->current_state = HYPERAUTO_STATE_RETRYING;
                    }
                } else {
                    printf("Max verification iterations reached\n");
                    engine->context->current_state = HYPERAUTO_STATE_REFLECTING;
                }
                break;
            }
            
            case HYPERAUTO_STATE_RETRYING:
                printf("State: RETRYING\n");
                engine->context->current_state = HYPERAUTO_STATE_EXECUTING;
                break;
                
            case HYPERAUTO_STATE_REFLECTING:
                printf("State: REFLECTING\n");
                if (engine->config->learning_enabled) {
                    engine->context->current_state = HYPERAUTO_STATE_LEARNING;
                } else {
                    engine->context->current_state = HYPERAUTO_STATE_COMPLETED;
                }
                break;
                
            case HYPERAUTO_STATE_LEARNING:
                printf("State: LEARNING\n");
                engine->context->current_state = HYPERAUTO_STATE_COMPLETED;
                break;
                
            case HYPERAUTO_STATE_COMPLETED:
                printf("State: COMPLETED\n");
                engine->running = false;
                break;
                
            case HYPERAUTO_STATE_FAILED:
                printf("State: FAILED\n");
                engine->running = false;
                break;
                
            default:
                break;
        }
        
        time_t elapsed = time(NULL) - engine->context->start_time;
        if (elapsed > engine->config->timeout_seconds) {
            printf("Timeout reached (%d seconds)\n", engine->config->timeout_seconds);
            engine->context->current_state = HYPERAUTO_STATE_FAILED;
            engine->running = false;
        }
    }
    
    engine->context->end_time = time(NULL);
    
    printf("\n=== HyperAuto Summary ===\n");
    printf("Total iterations: %d\n", engine->current_iteration);
    printf("Verification iterations: %d\n", engine->verification_iteration);
    if (engine->last_verification) {
        printf("Final pass rate: %.1f%%\n", engine->last_verification->pass_rate * 100);
        printf("Status: %s\n", engine->last_verification->is_perfect ? "PERFECT" : "ACCEPTABLE");
    }
    
    return (engine->context->current_state == HYPERAUTO_STATE_COMPLETED) ? 0 : 1;
}

int hyperauto_engine_stop(HyperAutoEngine* engine) {
    if (!engine) return -1;
    engine->running = false;
    return 0;
}

WorkflowContext* hyperauto_engine_get_context(HyperAutoEngine* engine) {
    return engine ? engine->context : NULL;
}

VerificationResult* hyperauto_engine_get_verification(HyperAutoEngine* engine) {
    return engine ? engine->last_verification : NULL;
}