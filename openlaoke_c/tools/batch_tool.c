#include "../include/tool_registry.h"
#include "../include/types.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <pthread.h>

#define MAX_BATCH_CALLS 50
#define MAX_OUTPUT_SIZE 8192

typedef struct {
    char* tool_name;
    char* args_json;
} ToolCallSpec;

typedef struct {
    int call_index;
    ToolCallSpec* spec;
    char* result;
    bool is_error;
} BatchCallResult;

typedef struct {
    ToolCallSpec* calls;
    int call_count;
    bool parallel;
    bool stop_on_error;
} BatchInput;

typedef struct {
    ToolRegistry* registry;
    void* ctx;
    BatchCallResult* results;
    int current_index;
    pthread_mutex_t mutex;
    ToolCallSpec* calls;
    int call_count;
} BatchExecutionContext;

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
    
    char* value_end = value_start;
    while (*value_end && *value_end != ',' && *value_end != '}' && *value_end != ']') {
        value_end++;
    }
    size_t len = value_end - value_start;
    char* result = malloc(len + 1);
    strncpy(result, value_start, len);
    result[len] = '\0';
    return result;
}

static ToolCallSpec* parse_tool_call(const char* call_json) {
    ToolCallSpec* spec = calloc(1, sizeof(ToolCallSpec));
    if (!spec) return NULL;
    
    spec->tool_name = extract_json_string_value(call_json, "\"tool_name\"");
    spec->args_json = extract_json_string_value(call_json, "\"args\"");
    
    if (!spec->args_json) {
        spec->args_json = strdup("{}");
    }
    
    return spec;
}

static BatchInput* batch_input_parse(const char* json) {
    BatchInput* input = calloc(1, sizeof(BatchInput));
    if (!input) return NULL;
    
    input->parallel = true;
    input->stop_on_error = false;
    
    char* parallel_val = extract_json_string_value(json, "\"parallel\"");
    if (parallel_val) {
        if (strcmp(parallel_val, "false") == 0 || strcmp(parallel_val, "0") == 0) {
            input->parallel = false;
        }
        free(parallel_val);
    }
    
    char* stop_val = extract_json_string_value(json, "\"stop_on_error\"");
    if (stop_val) {
        if (strcmp(stop_val, "true") == 0 || strcmp(stop_val, "1") == 0) {
            input->stop_on_error = true;
        }
        free(stop_val);
    }
    
    char* calls_start = strstr(json, "\"calls\"");
    if (!calls_start) {
        return input;
    }
    
    char* array_start = strchr(calls_start + 7, '[');
    if (!array_start) {
        return input;
    }
    
    array_start++;
    
    int call_capacity = 10;
    input->calls = calloc(call_capacity, sizeof(ToolCallSpec));
    
    char* current = array_start;
    while (*current && *current != ']') {
        if (*current == '{') {
            char* obj_end = strchr(current, '}');
            if (!obj_end) break;
            
            size_t obj_len = obj_end - current + 1;
            char* obj_json = malloc(obj_len + 1);
            strncpy(obj_json, current, obj_len);
            obj_json[obj_len] = '\0';
            
            if (input->call_count >= call_capacity) {
                call_capacity *= 2;
                input->calls = realloc(input->calls, call_capacity * sizeof(ToolCallSpec));
            }
            
            ToolCallSpec* spec = parse_tool_call(obj_json);
            if (spec) {
                input->calls[input->call_count++] = *spec;
                free(spec);
            }
            free(obj_json);
            
            current = obj_end + 1;
        } else {
            current++;
        }
    }
    
    return input;
}

static void batch_input_free(BatchInput* input) {
    if (input) {
        for (int i = 0; i < input->call_count; i++) {
            free(input->calls[i].tool_name);
            free(input->calls[i].args_json);
        }
        free(input->calls);
        free(input);
    }
}

static void* batch_call_thread(void* arg) {
    BatchExecutionContext* exec_ctx = (BatchExecutionContext*)arg;
    
    pthread_mutex_lock(&exec_ctx->mutex);
    int index = exec_ctx->current_index++;
    BatchCallResult* result = &exec_ctx->results[index];
    ToolCallSpec* spec = &exec_ctx->calls[index];
    pthread_mutex_unlock(&exec_ctx->mutex);
    
    Tool* tool = tool_registry_get(exec_ctx->registry, spec->tool_name);
    
    if (!tool) {
        result->result = malloc(256);
        snprintf(result->result, 256, "Error: Tool '%s' not found", spec->tool_name);
        result->is_error = true;
        return NULL;
    }
    
    ToolResultBlock* block = tool->execute(tool, exec_ctx->ctx, spec->args_json);
    
    if (block) {
        result->result = strdup(block->content);
        result->is_error = block->is_error;
        tool_result_block_destroy(block);
    } else {
        result->result = strdup("Error: Tool execution failed");
        result->is_error = true;
    }
    
    return NULL;
}

ToolResultBlock* batch_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    (void)tool;
    
    BatchInput* input = batch_input_parse(input_json);
    if (!input) {
        return tool_result_block_create("batch_error", "Error: Failed to parse input JSON", true);
    }
    
    if (input->call_count == 0) {
        batch_input_free(input);
        return tool_result_block_create("batch_error", "Error: calls list is required", true);
    }
    
    if (input->call_count > MAX_BATCH_CALLS) {
        char error[128];
        snprintf(error, sizeof(error), "Error: Too many calls (%d). Maximum is %d.", 
                 input->call_count, MAX_BATCH_CALLS);
        batch_input_free(input);
        return tool_result_block_create("batch_error", error, true);
    }
    
    ToolRegistry* registry = tool_registry_create();
    BatchCallResult* results = calloc(input->call_count, sizeof(BatchCallResult));
    
    BatchExecutionContext exec_ctx = {
        .registry = registry,
        .ctx = ctx,
        .results = results,
        .current_index = 0,
        .calls = input->calls,
        .call_count = input->call_count
    };
    pthread_mutex_init(&exec_ctx.mutex, NULL);
    
    if (input->parallel) {
        pthread_t threads[input->call_count];
        
        for (int i = 0; i < input->call_count; i++) {
            pthread_create(&threads[i], NULL, batch_call_thread, &exec_ctx);
        }
        
        for (int i = 0; i < input->call_count; i++) {
            pthread_join(threads[i], NULL);
        }
    } else {
        for (int i = 0; i < input->call_count; i++) {
            exec_ctx.current_index = i;
            batch_call_thread(&exec_ctx);
            
            if (results[i].is_error && input->stop_on_error) {
                break;
            }
        }
    }
    
    pthread_mutex_destroy(&exec_ctx.mutex);
    tool_registry_destroy(registry);
    
    char* output = malloc(MAX_OUTPUT_SIZE);
    size_t offset = 0;
    offset += snprintf(output + offset, MAX_OUTPUT_SIZE - offset, "Batch results:\n\n");
    
    int success_count = 0;
    int error_count = 0;
    
    for (int i = 0; i < input->call_count; i++) {
        if (offset >= MAX_OUTPUT_SIZE - 100) break;
        
        if (results[i].is_error) {
            error_count++;
            offset += snprintf(output + offset, MAX_OUTPUT_SIZE - offset, 
                              "[%d] %s: ERROR\n%s\n\n", 
                              i, input->calls[i].tool_name, results[i].result);
        } else {
            success_count++;
            offset += snprintf(output + offset, MAX_OUTPUT_SIZE - offset, 
                              "[%d] %s: SUCCESS\n%s\n\n", 
                              i, input->calls[i].tool_name, results[i].result);
        }
        
        free(results[i].result);
    }
    
    if (offset < MAX_OUTPUT_SIZE - 100) {
        offset += snprintf(output + offset, MAX_OUTPUT_SIZE - offset, 
                          "Summary: %d successful, %d errors out of %d calls",
                          success_count, error_count, input->call_count);
    }
    
    free(results);
    batch_input_free(input);
    
    ToolResultBlock* block = tool_result_block_create("batch_result", output, false);
    free(output);
    return block;
}

Tool* batch_tool_create(void) {
    Tool* tool = calloc(1, sizeof(Tool));
    tool->name = strdup("Batch");
    tool->description = strdup(
        "Execute multiple tool calls in a single batch operation. "
        "Supports both parallel (default) and sequential execution.");
    tool->execute = batch_tool_execute;
    tool->is_read_only = false;
    tool->is_destructive = false;
    tool->is_concurrency_safe = true;
    tool->requires_approval = false;
    return tool;
}