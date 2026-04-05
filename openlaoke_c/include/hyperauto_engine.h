/* OpenLaoKe C - HyperAuto Engine */

#ifndef OPENLAOKE_HYPERAUTO_ENGINE_H
#define OPENLAOKE_HYPERAUTO_ENGINE_H

#include "hyperauto_types.h"
#include "types.h"

/* Forward declarations */
typedef struct HyperAutoEngine HyperAutoEngine;
typedef struct VerificationResult VerificationResult;

/* HyperAuto Engine functions */
HyperAutoEngine* hyperauto_engine_create(const char* request);
void hyperauto_engine_destroy(HyperAutoEngine* engine);

/* Engine execution */
int hyperauto_engine_run(HyperAutoEngine* engine);
int hyperauto_engine_stop(HyperAutoEngine* engine);

/* File tracking */
void hyperauto_engine_add_created_file(HyperAutoEngine* engine, const char* filepath);
void hyperauto_engine_add_modified_file(HyperAutoEngine* engine, const char* filepath);

/* Get context */
WorkflowContext* hyperauto_engine_get_context(HyperAutoEngine* engine);
VerificationResult* hyperauto_engine_get_verification(HyperAutoEngine* engine);

#endif /* OPENLAOKE_HYPERAUTO_ENGINE_H */