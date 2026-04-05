#include "../include/types_extended.h"
#include <string.h>

const char* provider_type_to_string(ProviderType type) {
    switch (type) {
        case PROVIDER_OPENAI: return "openai";
        case PROVIDER_ANTHROPIC: return "anthropic";
        case PROVIDER_AZURE: return "azure";
        case PROVIDER_OLLAMA: return "ollama";
        case PROVIDER_MINIMAX: return "minimax";
        case PROVIDER_GEMINI: return "gemini";
        default: return "custom";
    }
}

ProviderType string_to_provider_type(const char* str) {
    if (!str) return PROVIDER_CUSTOM;
    if (strcmp(str, "openai") == 0) return PROVIDER_OPENAI;
    if (strcmp(str, "anthropic") == 0) return PROVIDER_ANTHROPIC;
    if (strcmp(str, "azure") == 0) return PROVIDER_AZURE;
    if (strcmp(str, "ollama") == 0) return PROVIDER_OLLAMA;
    if (strcmp(str, "minimax") == 0) return PROVIDER_MINIMAX;
    if (strcmp(str, "gemini") == 0) return PROVIDER_GEMINI;
    return PROVIDER_CUSTOM;
}

const char* permission_level_to_string(PermissionLevel level) {
    switch (level) {
        case PERMISSION_LEVEL_SAFE: return "safe";
        case PERMISSION_LEVEL_MODERATE: return "moderate";
        case PERMISSION_LEVEL_DANGEROUS: return "dangerous";
        default: return "unknown";
    }
}

PermissionLevel string_to_permission_level(const char* str) {
    if (!str) return PERMISSION_LEVEL_UNKNOWN;
    if (strcmp(str, "safe") == 0) return PERMISSION_LEVEL_SAFE;
    if (strcmp(str, "moderate") == 0) return PERMISSION_LEVEL_MODERATE;
    if (strcmp(str, "dangerous") == 0) return PERMISSION_LEVEL_DANGEROUS;
    return PERMISSION_LEVEL_UNKNOWN;
}

ProviderConfig* provider_config_create(ProviderType type, const char* name) {
    ProviderConfig* config = (ProviderConfig*)calloc(1, sizeof(ProviderConfig));
    if (!config) return NULL;
    config->type = type;
    config->name = name ? strdup(name) : NULL;
    return config;
}

void provider_config_destroy(ProviderConfig* config) {
    if (!config) return;
    free(config->name);
    free(config->api_key);
    free(config->base_url);
    free(config->default_model);
    free(config);
}

PermissionConfig* permission_config_create(void) {
    return (PermissionConfig*)calloc(1, sizeof(PermissionConfig));
}

void permission_config_destroy(PermissionConfig* config) {
    if (!config) return;
    if (config->always_approve_tools) {
        for (int i = 0; i < config->always_approve_count; i++) {
            free(config->always_approve_tools[i]);
        }
        free(config->always_approve_tools);
    }
    if (config->always_deny_tools) {
        for (int i = 0; i < config->always_deny_count; i++) {
            free(config->always_deny_tools[i]);
        }
        free(config->always_deny_tools);
    }
    free(config);
}

MultiProviderConfig* multi_provider_config_create(void) {
    return (MultiProviderConfig*)calloc(1, sizeof(MultiProviderConfig));
}

void multi_provider_config_destroy(MultiProviderConfig* config) {
    if (!config) return;
    if (config->providers) {
        for (int i = 0; i < config->provider_count; i++) {
            provider_config_destroy(config->providers[i]);
        }
        free(config->providers);
    }
    free(config->active_provider);
    free(config->active_model);
    free(config);
}

SessionInfo* session_info_create(const char* session_id) {
    SessionInfo* info = (SessionInfo*)calloc(1, sizeof(SessionInfo));
    if (!info) return NULL;
    info->session_id = session_id ? strdup(session_id) : NULL;
    return info;
}

void session_info_destroy(SessionInfo* session) {
    if (!session) return;
    free(session->session_id);
    free(session->working_directory);
    free(session);
}

ModelCapability* model_capability_create(const char* model_name) {
    ModelCapability* cap = (ModelCapability*)calloc(1, sizeof(ModelCapability));
    if (!cap) return NULL;
    cap->model_name = model_name ? strdup(model_name) : NULL;
    return cap;
}

void model_capability_destroy(ModelCapability* cap) {
    if (!cap) return;
    free(cap->model_name);
    free(cap);
}
