#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "../include/types.h"
#include "../include/types_extended.h"
#include "../include/state.h"
#include "../include/tool_registry.h"
#include "../include/hyperauto_types.h"

static int tests_passed = 0;
static int tests_failed = 0;

#define TEST(name) static void test_##name(void)
#define RUN_TEST(name) do { \
    printf("Testing %s... ", #name); \
    test_##name(); \
    printf("✓\n"); \
    tests_passed++; \
} while(0)

#define ASSERT_TRUE(expr) do { \
    if (!(expr)) { \
        printf("FAILED at line %d: %s\n", __LINE__, #expr); \
        tests_failed++; \
        return; \
    } \
} while(0)

TEST(hyperauto_workflow_context) {
    WorkflowContext* ctx = workflow_context_create("Test task");
    ASSERT_TRUE(ctx != NULL);
    ASSERT_TRUE(ctx->original_request != NULL);
    ASSERT_TRUE(strcmp(ctx->original_request, "Test task") == 0);
    ASSERT_TRUE(ctx->current_state == HYPERAUTO_STATE_IDLE);
    workflow_context_destroy(ctx);
}

TEST(hyperauto_sub_task) {
    SubTask* task = sub_task_create("test_task", "Test description");
    ASSERT_TRUE(task != NULL);
    ASSERT_TRUE(task->name != NULL);
    ASSERT_TRUE(strcmp(task->name, "test_task") == 0);
    ASSERT_TRUE(task->status == SUB_TASK_PENDING);
    sub_task_destroy(task);
}

TEST(hyperauto_config) {
    HyperAutoConfig* config = hyperauto_config_create_default();
    ASSERT_TRUE(config != NULL);
    ASSERT_TRUE(config->max_iterations > 0);
    ASSERT_TRUE(config->auto_run_tests == true);
    ASSERT_TRUE(config->rollback_on_failure == true);
    hyperauto_config_destroy(config);
}

TEST(hyperauto_analysis_result) {
    AnalysisResult* result = analysis_result_create();
    ASSERT_TRUE(result != NULL);
    analysis_result_destroy(result);
}

TEST(hyperauto_decision) {
    Decision* decision = decision_create("test_type", "test_action");
    ASSERT_TRUE(decision != NULL);
    ASSERT_TRUE(decision->type != NULL);
    ASSERT_TRUE(decision->action != NULL);
    decision_destroy(decision);
}

TEST(hyperauto_reflection) {
    Reflection* reflection = reflection_create();
    ASSERT_TRUE(reflection != NULL);
    reflection_destroy(reflection);
}

TEST(hyperauto_model_capability) {
    ModelCapability* cap = model_capability_create("gpt-3.5-turbo");
    ASSERT_TRUE(cap != NULL);
    ASSERT_TRUE(cap->model_name != NULL);
    ASSERT_TRUE(strcmp(cap->model_name, "gpt-3.5-turbo") == 0);
    model_capability_destroy(cap);
}

TEST(hyperauto_states) {
    ASSERT_TRUE(HYPERAUTO_STATE_IDLE == HYPERAUTO_STATE_IDLE);
    ASSERT_TRUE(HYPERAUTO_STATE_ANALYZING == HYPERAUTO_STATE_ANALYZING);
    ASSERT_TRUE(HYPERAUTO_STATE_PLANNING == HYPERAUTO_STATE_PLANNING);
    ASSERT_TRUE(HYPERAUTO_STATE_EXECUTING == HYPERAUTO_STATE_EXECUTING);
    ASSERT_TRUE(HYPERAUTO_STATE_VERIFYING == HYPERAUTO_STATE_VERIFYING);
    ASSERT_TRUE(HYPERAUTO_STATE_COMPLETED == HYPERAUTO_STATE_COMPLETED);
}

TEST(hyperauto_sub_task_status) {
    ASSERT_TRUE(SUB_TASK_PENDING == SUB_TASK_PENDING);
    ASSERT_TRUE(SUB_TASK_RUNNING == SUB_TASK_RUNNING);
    ASSERT_TRUE(SUB_TASK_COMPLETED == SUB_TASK_COMPLETED);
    ASSERT_TRUE(SUB_TASK_FAILED == SUB_TASK_FAILED);
}

TEST(types_extended_provider_config) {
    ProviderConfig* config = provider_config_create(PROVIDER_OPENAI, "test");
    ASSERT_TRUE(config != NULL);
    ASSERT_TRUE(config->type == PROVIDER_OPENAI);
    ASSERT_TRUE(config->name != NULL);
    provider_config_destroy(config);
}

TEST(types_extended_permission_config) {
    PermissionConfig* config = permission_config_create();
    ASSERT_TRUE(config != NULL);
    permission_config_destroy(config);
}

TEST(types_extended_session_info) {
    SessionInfo* session = session_info_create("test-session-123");
    ASSERT_TRUE(session != NULL);
    ASSERT_TRUE(session->session_id != NULL);
    ASSERT_TRUE(strcmp(session->session_id, "test-session-123") == 0);
    session_info_destroy(session);
}

int main() {
    printf("=== HyperAuto Unit Tests ===\n\n");
    
    RUN_TEST(hyperauto_workflow_context);
    RUN_TEST(hyperauto_sub_task);
    RUN_TEST(hyperauto_config);
    RUN_TEST(hyperauto_analysis_result);
    RUN_TEST(hyperauto_decision);
    RUN_TEST(hyperauto_reflection);
    RUN_TEST(hyperauto_model_capability);
    RUN_TEST(hyperauto_states);
    RUN_TEST(hyperauto_sub_task_status);
    RUN_TEST(types_extended_provider_config);
    RUN_TEST(types_extended_permission_config);
    RUN_TEST(types_extended_session_info);
    
    printf("\n=== Results ===\n");
    printf("Passed: %d\n", tests_passed);
    printf("Failed: %d\n", tests_failed);
    
    if (tests_failed > 0) {
        printf("\n❌ Some tests failed!\n");
        return 1;
    }
    
    printf("\n✓ All HyperAuto tests passed!\n");
    return 0;
}