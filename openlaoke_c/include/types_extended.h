/* OpenLaoKe C - Extended type definitions */

#ifndef OPENLAOKE_TYPES_EXTENDED_H
#define OPENLAOKE_TYPES_EXTENDED_H

#include "types.h"
#include <time.h>

/* Provider types */
typedef enum {
    PROVIDER_OPENAI,
    PROVIDER_ANTHROPIC,
    PROVIDER_AZURE,
    PROVIDER_OLLAMA,
    PROVIDER_MINIMAX,
    PROVIDER_GEMINI,
    PROVIDER_CUSTOM
} ProviderType;

/* Permission level */
typedef enum {
    PERMISSION_LEVEL_SAFE,
    PERMISSION_LEVEL_MODERATE,
    PERMISSION_LEVEL_DANGEROUS,
    PERMISSION_LEVEL_UNKNOWN
} PermissionLevel;

/* Permission action */
typedef enum {
    PERMISSION_ACTION_ALLOW,
    PERMISSION_ACTION_DENY,
    PERMISSION_ACTION_ASK
} PermissionAction;

/* Provider config */
typedef struct {
    ProviderType type;
    char* name;
    char* api_key;
    char* base_url;
    char* default_model;
    char** available_models;
    int model_count;
    int max_tokens;
    double temperature;
    bool supports_streaming;
    bool supports_tools;
    bool supports_vision;
} ProviderConfig;

/* Permission config */
typedef struct {
    PermissionMode mode;
    bool auto_approve_safe;
    bool auto_approve_all;
    char** always_approve_tools;
    int always_approve_count;
    char** always_deny_tools;
    int always_deny_count;
    int max_auto_approve_per_session;
    int auto_approve_count;
} PermissionConfig;

/* Model capability */
typedef struct {
    char* model_name;
    int context_window;
    int max_output_tokens;
    bool supports_tools;
    bool supports_vision;
    bool supports_streaming;
    double input_cost_per_1k;
    double output_cost_per_1k;
} ModelCapability;

/* Multi-provider config */
typedef struct {
    ProviderConfig** providers;
    int provider_count;
    char* active_provider;
    char* active_model;
    bool auto_switch;
    int timeout_seconds;
    int max_retries;
} MultiProviderConfig;

/* Session info */
typedef struct {
    char* session_id;
    time_t start_time;
    time_t end_time;
    char* working_directory;
    void** messages;  /* MessageExtended** */
    int message_count;
    TokenUsage total_tokens;
    CostInfo total_cost;
    char** created_files;
    int file_count;
} SessionInfo;

/* Function declarations */

/* Type conversion */
const char* provider_type_to_string(ProviderType type);
ProviderType string_to_provider_type(const char* str);
const char* permission_level_to_string(PermissionLevel level);
PermissionLevel string_to_permission_level(const char* str);

/* Creation functions */
ProviderConfig* provider_config_create(ProviderType type, const char* name);
void provider_config_destroy(ProviderConfig* config);

PermissionConfig* permission_config_create(void);
void permission_config_destroy(PermissionConfig* config);

MultiProviderConfig* multi_provider_config_create(void);
void multi_provider_config_destroy(MultiProviderConfig* config);

SessionInfo* session_info_create(const char* session_id);
void session_info_destroy(SessionInfo* session);

ModelCapability* model_capability_create(const char* model_name);
void model_capability_destroy(ModelCapability* cap);

#endif /* OPENLAOKE_TYPES_EXTENDED_H */