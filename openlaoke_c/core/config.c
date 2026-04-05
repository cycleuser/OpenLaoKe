#include "../include/config.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

Configuration* config_create_default(void) {
    Configuration* config = (Configuration*)calloc(1, sizeof(Configuration));
    if (!config) return NULL;
    
    config->active_provider = strdup("ollama");
    config->active_model = strdup("gemma3:1b");
    config->permission_mode = PERMISSION_MODE_DEFAULT;
    config->auto_approve_safe = true;
    config->auto_approve_all = false;
    config->hyperauto_mode = HYPERAUTO_MODE_SEMI_AUTO;
    config->hyperauto_max_iterations = 100;
    config->theme = strdup("default");
    config->color_output = true;
    config->verbose = false;
    config->max_history = 1000;
    config->save_history = true;
    
    return config;
}

void config_destroy(Configuration* config) {
    if (!config) return;
    free(config->active_provider);
    free(config->active_model);
    free(config->theme);
    if (config->always_approve_tools) {
        for (int i = 0; i < config->approve_tool_count; i++) {
            free(config->always_approve_tools[i]);
        }
        free(config->always_approve_tools);
    }
    if (config->always_deny_tools) {
        for (int i = 0; i < config->deny_tool_count; i++) {
            free(config->always_deny_tools[i]);
        }
        free(config->always_deny_tools);
    }
    free(config);
}

Configuration* config_load(const char* filepath) {
    (void)filepath;
    return config_create_default();
}

int config_save(Configuration* config, const char* filepath) {
    (void)config;
    (void)filepath;
    return 0;
}

char* config_get_path(void) {
    return strdup("~/.openlaoke/config.json");
}

char* config_get_sessions_path(void) {
    return strdup("~/.openlaoke/sessions/");
}

bool config_validate(Configuration* config) {
    return config != NULL;
}

Configuration* config_merge(Configuration* base, Configuration* override) {
    (void)override;
    return base;
}
