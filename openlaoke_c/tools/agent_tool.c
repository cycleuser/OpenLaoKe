#include "../include/tool_registry.h"
#include "../include/types.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <pthread.h>

typedef struct {
    char* prompt;
    char* description;
    char* subagent_type;
} AgentInput;

static AgentInput* agent_input_parse(const char* json) {
    AgentInput* input = calloc(1, sizeof(AgentInput));
    if (!input) return NULL;
    
    input->prompt = NULL;
    input->description = strdup("");
    input->subagent_type = strdup("general-purpose");
    
    char* prompt_start = strstr(json, "\"prompt\"");
    if (prompt_start) {
        char* value_start = strchr(prompt_start + 8, ':');
        if (value_start) {
            value_start = strchr(value_start + 1, '"');
            if (value_start) {
                value_start++;
                char* value_end = strchr(value_start, '"');
                if (value_end) {
                    size_t len = value_end - value_start;
                    input->prompt = malloc(len + 1);
                    strncpy(input->prompt, value_start, len);
                    input->prompt[len] = '\0';
                }
            }
        }
    }
    
    char* desc_start = strstr(json, "\"description\"");
    if (desc_start) {
        char* value_start = strchr(desc_start + 13, ':');
        if (value_start) {
            value_start = strchr(value_start + 1, '"');
            if (value_start) {
                value_start++;
                char* value_end = strchr(value_start, '"');
                if (value_end) {
                    size_t len = value_end - value_start;
                    free(input->description);
                    input->description = malloc(len + 1);
                    strncpy(input->description, value_start, len);
                    input->description[len] = '\0';
                }
            }
        }
    }
    
    char* type_start = strstr(json, "\"subagent_type\"");
    if (type_start) {
        char* value_start = strchr(type_start + 15, ':');
        if (value_start) {
            value_start = strchr(value_start + 1, '"');
            if (value_start) {
                value_start++;
                char* value_end = strchr(value_start, '"');
                if (value_end) {
                    size_t len = value_end - value_start;
                    free(input->subagent_type);
                    input->subagent_type = malloc(len + 1);
                    strncpy(input->subagent_type, value_start, len);
                    input->subagent_type[len] = '\0';
                }
            }
        }
    }
    
    return input;
}

static void agent_input_free(AgentInput* input) {
    if (input) {
        free(input->prompt);
        free(input->description);
        free(input->subagent_type);
        free(input);
    }
}

static char* run_subagent_simulation(const char* prompt, const char* subagent_type) {
    char* result = malloc(1024);
    snprintf(result, 1024, 
        "Sub-agent execution (%s):\n"
        "Prompt: %s\n\n"
        "Simulated agent response:\n"
        "- Analyzed the task requirements\n"
        "- Executed necessary operations\n"
        "- Completed task successfully\n\n"
        "Note: Full implementation requires API integration",
        subagent_type, prompt);
    return result;
}

ToolResultBlock* agent_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    (void)tool;
    (void)ctx;
    
    AgentInput* input = agent_input_parse(input_json);
    if (!input) {
        return tool_result_block_create("agent_error", 
            "Error: Failed to parse input JSON", true);
    }
    
    if (!input->prompt || strlen(input->prompt) == 0) {
        agent_input_free(input);
        return tool_result_block_create("agent_error", 
            "Error: prompt is required", true);
    }
    
    char description[256];
    if (strlen(input->description) > 0) {
        strncpy(description, input->description, 255);
    } else {
        size_t prompt_len = strlen(input->prompt);
        size_t desc_len = prompt_len < 100 ? prompt_len : 100;
        strncpy(description, input->prompt, desc_len);
        description[desc_len] = '\0';
    }
    
    char* result = run_subagent_simulation(input->prompt, input->subagent_type);
    
    const size_t max_output = 20000;
    if (strlen(result) > max_output) {
        char* truncated = malloc(max_output + 100);
        strncpy(truncated, result, max_output);
        snprintf(truncated + max_output, 100, 
            "\n\n... (output truncated, %zu chars omitted)", 
            strlen(result) - max_output);
        free(result);
        result = truncated;
    }
    
    agent_input_free(input);
    
    ToolResultBlock* block = tool_result_block_create("agent_result", result, false);
    free(result);
    return block;
}

Tool* agent_tool_create(void) {
    Tool* tool = calloc(1, sizeof(Tool));
    tool->name = strdup("Agent");
    tool->description = strdup(
        "Launch a sub-agent to work on a task in parallel. "
        "Use this for independent work that can be done concurrently. "
        "The sub-agent has access to all the same tools.");
    tool->execute = agent_tool_execute;
    tool->is_read_only = false;
    tool->is_destructive = false;
    tool->is_concurrency_safe = true;
    tool->requires_approval = true;
    return tool;
}