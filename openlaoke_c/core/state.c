/* OpenLaoKe C - State management implementation */

#include "../include/state.h"
#include "../include/tool_registry.h"
#include <stdio.h>
#include <unistd.h>
#include <sys/stat.h>

AppState* app_state_create(const char* working_dir) {
    AppState* state = (AppState*)malloc(sizeof(AppState));
    if (!state) return NULL;
    
    state->session_id = NULL;
    state->cwd = strdup(working_dir);
    
    state->multi_provider_config = NULL;
    state->active_provider = NULL;
    state->active_model = NULL;
    
    state->tool_registry = tool_registry_create();
    state->tools_available = 0;
    
    state->permission_mode = PERMISSION_MODE_DEFAULT;
    state->hyperauto_mode = HYPERAUTO_MODE_SEMI_AUTO;
    state->hyperauto_enabled = false;
    
    state->message_history = NULL;
    state->message_count = 0;
    state->message_capacity = 0;
    
    state->start_time = time(NULL);
    state->last_activity = time(NULL);
    state->total_tokens = 0;
    state->total_cost = 0.0;
    
    return state;
}

void app_state_destroy(AppState* state) {
    if (!state) return;
    
    free(state->session_id);
    free(state->cwd);
    free(state->active_provider);
    free(state->active_model);
    
    if (state->tool_registry) {
        tool_registry_destroy(state->tool_registry);
    }
    
    app_state_clear_messages(state);
    free(state->message_history);
    
    free(state);
}

void app_state_set_cwd(AppState* state, const char* cwd) {
    if (!state || !cwd) return;
    free(state->cwd);
    state->cwd = strdup(cwd);
    chdir(cwd);
}

const char* app_state_get_cwd(AppState* state) {
    return state ? state->cwd : NULL;
}

void app_state_set_model(AppState* state, const char* provider, const char* model) {
    if (!state) return;
    
    if (provider) {
        free(state->active_provider);
        state->active_provider = strdup(provider);
    }
    
    if (model) {
        free(state->active_model);
        state->active_model = strdup(model);
    }
}

const char* app_state_get_active_model(AppState* state) {
    return state ? state->active_model : NULL;
}

int app_state_add_message(AppState* state, Message* msg) {
    if (!state || !msg) return -1;
    
    if (state->message_count >= state->message_capacity) {
        int new_capacity = state->message_capacity == 0 ? 10 : state->message_capacity * 2;
        Message** new_history = (Message**)realloc(state->message_history, new_capacity * sizeof(Message*));
        if (!new_history) return -1;
        
        state->message_history = new_history;
        state->message_capacity = new_capacity;
    }
    
    state->message_history[state->message_count++] = msg;
    state->last_activity = time(NULL);
    
    return state->message_count - 1;
}

Message* app_state_get_message(AppState* state, int index) {
    if (!state || index < 0 || index >= state->message_count) return NULL;
    return state->message_history[index];
}

void app_state_clear_messages(AppState* state) {
    if (!state) return;
    
    for (int i = 0; i < state->message_count; i++) {
        message_destroy(state->message_history[i]);
    }
    state->message_count = 0;
}

char* app_state_to_json(AppState* state) {
    if (!state) return NULL;
    
    char* json = (char*)malloc(4096);
    if (!json) return NULL;
    
    snprintf(json, 4096,
        "{"
        "\"session_id\":\"%s\","
        "\"cwd\":\"%s\","
        "\"active_provider\":\"%s\","
        "\"active_model\":\"%s\","
        "\"permission_mode\":\"%s\","
        "\"hyperauto_mode\":\"%s\","
        "\"hyperauto_enabled\":%s,"
        "\"total_tokens\":%d,"
        "\"total_cost\":%.4f"
        "}",
        state->session_id ? state->session_id : "",
        state->cwd ? state->cwd : "",
        state->active_provider ? state->active_provider : "",
        state->active_model ? state->active_model : "",
        permission_mode_to_string(state->permission_mode),
        hyperauto_mode_to_string(state->hyperauto_mode),
        state->hyperauto_enabled ? "true" : "false",
        state->total_tokens,
        state->total_cost
    );
    
    return json;
}

AppState* app_state_load(const char* filepath) {
    (void)filepath;
    /* TODO: Implement state loading from JSON file */
    return NULL;
}

int app_state_save(AppState* state, const char* filepath) {
    if (!state || !filepath) return -1;
    
    char* json = app_state_to_json(state);
    if (!json) return -1;
    
    FILE* f = fopen(filepath, "w");
    if (!f) {
        free(json);
        return -1;
    }
    
    fprintf(f, "%s\n", json);
    fclose(f);
    free(json);
    
    return 0;
}