#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "../include/types.h"
#include "../include/state.h"
#include "../include/tool_registry.h"

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

#define ASSERT_EQ(a, b) ASSERT_TRUE((a) == (b))
#define ASSERT_NE(a, b) ASSERT_TRUE((a) != (b))
#define ASSERT_NOT_NULL(p) ASSERT_TRUE((p) != NULL)

TEST(types_permission_mode) {
    const char* str = permission_mode_to_string(PERMISSION_MODE_AUTO);
    ASSERT_NOT_NULL(str);
    ASSERT_EQ(strcmp(str, "auto"), 0);
    
    str = permission_mode_to_string(PERMISSION_MODE_DEFAULT);
    ASSERT_NOT_NULL(str);
    ASSERT_EQ(strcmp(str, "default"), 0);
    
    str = permission_mode_to_string(PERMISSION_MODE_BYPASS);
    ASSERT_NOT_NULL(str);
    ASSERT_EQ(strcmp(str, "bypass"), 0);
}

TEST(types_message_role) {
    ASSERT_EQ(MESSAGE_ROLE_USER, MESSAGE_ROLE_USER);
    ASSERT_EQ(MESSAGE_ROLE_ASSISTANT, MESSAGE_ROLE_ASSISTANT);
    ASSERT_EQ(MESSAGE_ROLE_SYSTEM, MESSAGE_ROLE_SYSTEM);
    ASSERT_NE(MESSAGE_ROLE_USER, MESSAGE_ROLE_ASSISTANT);
}

TEST(types_message_create) {
    Message* msg = message_create(MESSAGE_ROLE_USER, "Hello, world!");
    ASSERT_NOT_NULL(msg);
    ASSERT_EQ(msg->role, MESSAGE_ROLE_USER);
    ASSERT_NOT_NULL(msg->content);
    ASSERT_EQ(strcmp(msg->content, "Hello, world!"), 0);
    message_destroy(msg);
}

TEST(types_tool_result) {
    ToolResultBlock* result = tool_result_block_create("test_id", "test content", false);
    ASSERT_NOT_NULL(result);
    ASSERT_NOT_NULL(result->tool_use_id);
    ASSERT_EQ(strcmp(result->tool_use_id, "test_id"), 0);
    ASSERT_NOT_NULL(result->content);
    ASSERT_EQ(strcmp(result->content, "test content"), 0);
    ASSERT_EQ(result->is_error, false);
    tool_result_block_destroy(result);
}

TEST(types_tool_result_error) {
    ToolResultBlock* result = tool_result_block_create("err_id", "error message", true);
    ASSERT_NOT_NULL(result);
    ASSERT_EQ(result->is_error, true);
    tool_result_block_destroy(result);
}

TEST(state_create) {
    AppState* state = app_state_create("/tmp/test");
    ASSERT_NOT_NULL(state);
    ASSERT_EQ(state->message_count, 0);
    app_state_destroy(state);
}

TEST(state_add_message) {
    AppState* state = app_state_create("/tmp/test");
    ASSERT_NOT_NULL(state);
    
    Message* msg = message_create(MESSAGE_ROLE_USER, "test message");
    ASSERT_NOT_NULL(msg);
    
    int result = app_state_add_message(state, msg);
    ASSERT_EQ(result, 0);
    ASSERT_EQ(state->message_count, 1);
    
    app_state_destroy(state);
}

TEST(state_get_message) {
    AppState* state = app_state_create("/tmp/test");
    ASSERT_NOT_NULL(state);
    
    Message* msg = message_create(MESSAGE_ROLE_USER, "test message");
    app_state_add_message(state, msg);
    
    Message* retrieved = app_state_get_message(state, 0);
    ASSERT_NOT_NULL(retrieved);
    ASSERT_EQ(retrieved->role, MESSAGE_ROLE_USER);
    ASSERT_EQ(strcmp(retrieved->content, "test message"), 0);
    
    app_state_destroy(state);
}

TEST(tool_registry_create) {
    ToolRegistry* registry = tool_registry_create();
    ASSERT_NOT_NULL(registry);
    ASSERT_EQ(registry->count, 0);
    tool_registry_destroy(registry);
}

TEST(tool_registry_register) {
    ToolRegistry* registry = tool_registry_create();
    ASSERT_NOT_NULL(registry);
    
    Tool* tool = tool_create("TestTool", "A test tool", NULL);
    ASSERT_NOT_NULL(tool);
    
    int result = tool_registry_register(registry, tool);
    ASSERT_EQ(result, 0);
    ASSERT_EQ(registry->count, 1);
    
    tool_registry_destroy(registry);
}

TEST(tool_registry_get) {
    ToolRegistry* registry = tool_registry_create();
    ASSERT_NOT_NULL(registry);
    
    Tool* tool = tool_create("TestTool", "A test tool", NULL);
    tool_registry_register(registry, tool);
    
    Tool* retrieved = tool_registry_get(registry, "TestTool");
    ASSERT_NOT_NULL(retrieved);
    ASSERT_EQ(strcmp(retrieved->name, "TestTool"), 0);
    
    tool_registry_destroy(registry);
}

TEST(tool_create) {
    Tool* tool = tool_create("MyTool", "Description of my tool", NULL);
    ASSERT_NOT_NULL(tool);
    ASSERT_NOT_NULL(tool->name);
    ASSERT_EQ(strcmp(tool->name, "MyTool"), 0);
    ASSERT_NOT_NULL(tool->description);
    ASSERT_EQ(strcmp(tool->description, "Description of my tool"), 0);
    tool_destroy(tool);
}

int main() {
    printf("=== Unit Tests ===\n\n");
    
    // Types tests
    RUN_TEST(types_permission_mode);
    RUN_TEST(types_message_role);
    RUN_TEST(types_message_create);
    RUN_TEST(types_tool_result);
    RUN_TEST(types_tool_result_error);
    
    // State tests
    RUN_TEST(state_create);
    RUN_TEST(state_add_message);
    RUN_TEST(state_get_message);
    
    // Tool registry tests
    RUN_TEST(tool_registry_create);
    RUN_TEST(tool_registry_register);
    RUN_TEST(tool_registry_get);
    RUN_TEST(tool_create);
    
    printf("\n=== Results ===\n");
    printf("Passed: %d\n", tests_passed);
    printf("Failed: %d\n", tests_failed);
    
    if (tests_failed > 0) {
        printf("\n❌ Some tests failed!\n");
        return 1;
    }
    
    printf("\n✓ All tests passed!\n");
    return 0;
}