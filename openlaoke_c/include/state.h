/* OpenLaoKe C - State management */

#ifndef OPENLAOKE_STATE_H
#define OPENLAOKE_STATE_H

#include "types.h"
#include <time.h>

/* Forward declarations */
typedef struct ToolRegistry ToolRegistry;
typedef struct MultiProviderConfig MultiProviderConfig;

/* Application state */
typedef struct {
    /* Core identifiers */
    char* session_id;
    char* cwd;  /* Current working directory */
    
    /* Model configuration */
    MultiProviderConfig* multi_provider_config;
    char* active_provider;
    char* active_model;
    
    /* Tool registry */
    ToolRegistry* tool_registry;
    int tools_available;
    
    /* State management */
    PermissionMode permission_mode;
    HyperAutoMode hyperauto_mode;
    bool hyperauto_enabled;
    
    /* Session data */
    char** message_history;
    int message_count;
    int message_capacity;
    
    /* Metadata */
    time_t start_time;
    time_t last_activity;
    int total_tokens;
    double total_cost;
} AppState;

/* State functions */
AppState* app_state_create(const char* working_dir);
void app_state_destroy(AppState* state);

/* State management */
void app_state_set_cwd(AppState* state, const char* cwd);
const char* app_state_get_cwd(AppState* state);

void app_state_set_model(AppState* state, const char* provider, const char* model);
const char* app_state_get_active_model(AppState* state);

/* Message history */
int app_state_add_message(AppState* state, Message* msg);
Message* app_state_get_message(AppState* state, int index);
void app_state_clear_messages(AppState* state);

/* State persistence */
int app_state_save(AppState* state, const char* filepath);
AppState* app_state_load(const char* filepath);

/* State serialization */
char* app_state_to_json(AppState* state);
AppState* app_state_from_json(const char* json);

#endif /* OPENLAOKE_STATE_H */