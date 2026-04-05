#include "../include/system_prompt.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char* system_prompt_generate(SystemPromptContext* ctx) {
    if (!ctx) return NULL;
    
    char* prompt = (char*)malloc(4096);
    if (!prompt) return NULL;
    
    snprintf(prompt, 4096,
        "You are OpenLaoKe C, an AI coding assistant.\n\n"
        "Working directory: %s\n"
        "Provider: %s\n"
        "Model: %s\n\n"
        "Available tools: 15\n\n"
        "Help the user with their coding tasks.",
        ctx->working_directory ? ctx->working_directory : ".",
        ctx->provider ? ctx->provider : "default",
        ctx->model ? ctx->model : "default"
    );
    
    return prompt;
}

SystemPromptContext* system_prompt_context_create(void) {
    return (SystemPromptContext*)calloc(1, sizeof(SystemPromptContext));
}

void system_prompt_context_destroy(SystemPromptContext* ctx) {
    if (!ctx) return;
    free(ctx->working_directory);
    free(ctx->provider);
    free(ctx->model);
    free(ctx);
}

char* detect_os(void) {
    return strdup("macOS");
}

char* detect_shell(void) {
    return strdup("/bin/zsh");
}
