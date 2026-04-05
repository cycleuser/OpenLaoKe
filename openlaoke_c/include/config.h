/* OpenLaoKe C - Configuration management */

#ifndef OPENLAOKE_CONFIG_H
#define OPENLAOKE_CONFIG_H

#include "types.h"

/* Configuration file path */
#define DEFAULT_CONFIG_PATH "~/.openlaoke/config.json"
#define DEFAULT_SESSIONS_PATH "~/.openlaoke/sessions/"

/* Configuration structure */
typedef struct {
    /* Provider settings */
    char* active_provider;
    char* active_model;
    
    /* Permission settings */
    PermissionMode permission_mode;
    bool auto_approve_safe;
    bool auto_approve_all;
    
    /* HyperAuto settings */
    HyperAutoMode hyperauto_mode;
    int hyperauto_max_iterations;
    
    /* Display settings */
    char* theme;
    bool color_output;
    bool verbose;
    
    /* History settings */
    int max_history;
    bool save_history;
    
    /* Tool settings */
    char** always_approve_tools;
    int approve_tool_count;
    char** always_deny_tools;
    int deny_tool_count;
} Configuration;

/* Config functions */
Configuration* config_create_default(void);
void config_destroy(Configuration* config);

/* Load/Save */
Configuration* config_load(const char* filepath);
int config_save(Configuration* config, const char* filepath);

/* Get config path */
char* config_get_path(void);
char* config_get_sessions_path(void);

/* Validate config */
bool config_validate(Configuration* config);

/* Merge configs */
Configuration* config_merge(Configuration* base, Configuration* override);

#endif /* OPENLAOKE_CONFIG_H */