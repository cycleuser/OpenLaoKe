/* OpenLaoKe C - Config wizard */

#ifndef OPENLAOKE_CONFIG_WIZARD_H
#define OPENLAOKE_CONFIG_WIZARD_H

#include "types.h"
#include "types_extended.h"
#include "api_client.h"

/* Config wizard state */
typedef enum {
    CONFIG_WIZARD_INIT,
    CONFIG_WIZARD_PROVIDER,
    CONFIG_WIZARD_API_KEY,
    CONFIG_WIZARD_MODEL,
    CONFIG_WIZARD_PERMISSIONS,
    CONFIG_WIZARD_COMPLETE
} ConfigWizardState;

/* Config wizard */
typedef struct {
    ConfigWizardState state;
    ProviderConfig* provider_config;
    PermissionConfig* permission_config;
    char** available_providers;
    int provider_count;
    char** available_models;
    int model_count;
    bool interactive;
} ConfigWizard;

/* Wizard functions */
ConfigWizard* config_wizard_create(void);
void config_wizard_destroy(ConfigWizard* wizard);

/* Run wizard */
int config_wizard_run(ConfigWizard* wizard);
int config_wizard_run_interactive(ConfigWizard* wizard);
int config_wizard_run_non_interactive(ConfigWizard* wizard);

/* Provider detection */
char** config_wizard_detect_providers(int* count);
char** config_wizard_get_available_models(ProviderType provider, const char* api_key, int* count);

/* Validation */
bool config_wizard_validate_api_key(ProviderType provider, const char* api_key);
bool config_wizard_validate_model(ProviderType provider, const char* model);

/* Save/Load */
int config_wizard_save_config(ConfigWizard* wizard, const char* filepath);
int config_wizard_load_config(ConfigWizard* wizard, const char* filepath);

#endif /* OPENLAOKE_CONFIG_WIZARD_H */