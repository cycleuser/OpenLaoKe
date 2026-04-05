#include "../include/config_wizard.h"
#include <stdlib.h>

ConfigWizard* config_wizard_create(void) {
    return (ConfigWizard*)calloc(1, sizeof(ConfigWizard));
}

void config_wizard_destroy(ConfigWizard* wizard) {
    if (!wizard) return;
    free(wizard);
}

int config_wizard_run(ConfigWizard* wizard __attribute__((unused))) {
    return 0;
}
