#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <sys/stat.h>
#include <unistd.h>
#include "../include/types.h"
#include "../include/types_extended.h"
#include "../include/state.h"
#include "../include/tool_registry.h"
#include "../include/error_handler.h"

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

#define ASSERT_FALSE(expr) ASSERT_TRUE(!(expr))
#define ASSERT_EQ(a, b) ASSERT_TRUE((a) == (b))
#define ASSERT_NE(a, b) ASSERT_TRUE((a) != (b))
#define ASSERT_NOT_NULL(p) ASSERT_TRUE((p) != NULL)
#define ASSERT_NULL(p) ASSERT_TRUE((p) == NULL)
#define ASSERT_STR_EQ(a, b) ASSERT_TRUE(strcmp((a), (b)) == 0)

/* ==================== 工具功能测试 ==================== */

TEST(tool_bash_create_and_destroy) {
    Tool* tool = tool_create("Bash", "Execute bash commands", NULL);
    ASSERT_NOT_NULL(tool);
    ASSERT_NOT_NULL(tool->name);
    ASSERT_STR_EQ(tool->name, "Bash");
    tool_destroy(tool);
}

TEST(tool_registry_multiple_registration) {
    ToolRegistry* registry = tool_registry_create();
    ASSERT_NOT_NULL(registry);
    
    Tool* tool1 = tool_create("Tool1", "First tool", NULL);
    Tool* tool2 = tool_create("Tool2", "Second tool", NULL);
    Tool* tool3 = tool_create("Tool3", "Third tool", NULL);
    
    ASSERT_EQ(tool_registry_register(registry, tool1), 0);  // Returns index
    ASSERT_EQ(tool_registry_register(registry, tool2), 1);  // Returns index
    ASSERT_EQ(tool_registry_register(registry, tool3), 2);  // Returns index
    
    ASSERT_EQ(registry->count, 3);
    
    Tool* retrieved = tool_registry_get(registry, "Tool2");
    ASSERT_NOT_NULL(retrieved);
    ASSERT_STR_EQ(retrieved->name, "Tool2");
    
    tool_registry_destroy(registry);
}

TEST(tool_result_block_with_error) {
    ToolResultBlock* result = tool_result_block_create("test_id", "Error message", true);
    ASSERT_NOT_NULL(result);
    ASSERT_TRUE(result->is_error);
    ASSERT_NOT_NULL(result->content);
    ASSERT_STR_EQ(result->content, "Error message");
    tool_result_block_destroy(result);
}

TEST(tool_result_block_without_error) {
    ToolResultBlock* result = tool_result_block_create("test_id", "Success message", false);
    ASSERT_NOT_NULL(result);
    ASSERT_FALSE(result->is_error);
    ASSERT_STR_EQ(result->content, "Success message");
    tool_result_block_destroy(result);
}

/* ==================== 状态管理测试 ==================== */

TEST(state_multiple_messages) {
    AppState* state = app_state_create("/tmp");
    ASSERT_NOT_NULL(state);
    
    Message* msg1 = message_create(MESSAGE_ROLE_USER, "Hello");
    Message* msg2 = message_create(MESSAGE_ROLE_ASSISTANT, "Hi there");
    Message* msg3 = message_create(MESSAGE_ROLE_USER, "How are you?");
    
    ASSERT_EQ(app_state_add_message(state, msg1), 0);
    ASSERT_EQ(app_state_add_message(state, msg2), 1);
    ASSERT_EQ(app_state_add_message(state, msg3), 2);
    
    ASSERT_EQ(state->message_count, 3);
    
    Message* retrieved = app_state_get_message(state, 1);
    ASSERT_NOT_NULL(retrieved);
    ASSERT_EQ(retrieved->role, MESSAGE_ROLE_ASSISTANT);
    ASSERT_STR_EQ(retrieved->content, "Hi there");
    
    app_state_destroy(state);
}

TEST(state_clear_messages) {
    AppState* state = app_state_create("/tmp");
    ASSERT_NOT_NULL(state);
    
    Message* msg1 = message_create(MESSAGE_ROLE_USER, "Test 1");
    Message* msg2 = message_create(MESSAGE_ROLE_USER, "Test 2");
    
    app_state_add_message(state, msg1);
    app_state_add_message(state, msg2);
    
    ASSERT_EQ(state->message_count, 2);
    
    app_state_clear_messages(state);
    
    ASSERT_EQ(state->message_count, 0);
    
    app_state_destroy(state);
}

TEST(state_to_json) {
    AppState* state = app_state_create("/tmp/test");
    app_state_set_model(state, "openai", "gpt-4");
    
    char* json = app_state_to_json(state);
    ASSERT_NOT_NULL(json);
    ASSERT_TRUE(strstr(json, "\"cwd\":\"/tmp/test\"") != NULL);
    ASSERT_TRUE(strstr(json, "\"active_provider\":\"openai\"") != NULL);
    ASSERT_TRUE(strstr(json, "\"active_model\":\"gpt-4\"") != NULL);
    
    free(json);
    app_state_destroy(state);
}

TEST(state_set_and_get_cwd) {
    AppState* state = app_state_create("/tmp");
    
    app_state_set_cwd(state, "/usr/local");
    const char* cwd = app_state_get_cwd(state);
    
    ASSERT_NOT_NULL(cwd);
    ASSERT_STR_EQ(cwd, "/usr/local");
    
    app_state_destroy(state);
}

/* ==================== 消息类型测试 ==================== */

TEST(message_all_roles) {
    Message* user_msg = message_create(MESSAGE_ROLE_USER, "User message");
    Message* assistant_msg = message_create(MESSAGE_ROLE_ASSISTANT, "Assistant message");
    Message* system_msg = message_create(MESSAGE_ROLE_SYSTEM, "System message");
    
    ASSERT_EQ(user_msg->role, MESSAGE_ROLE_USER);
    ASSERT_EQ(assistant_msg->role, MESSAGE_ROLE_ASSISTANT);
    ASSERT_EQ(system_msg->role, MESSAGE_ROLE_SYSTEM);
    
    message_destroy(user_msg);
    message_destroy(assistant_msg);
    message_destroy(system_msg);
}

TEST(message_with_tool_info) {
    Message* msg = message_create(MESSAGE_ROLE_USER, "Test");
    ASSERT_NOT_NULL(msg);
    
    msg->tool_use_id = strdup("tool_123");
    msg->tool_name = strdup("Bash");
    
    ASSERT_STR_EQ(msg->tool_use_id, "tool_123");
    ASSERT_STR_EQ(msg->tool_name, "Bash");
    
    message_destroy(msg);
}

/* ==================== 类型转换测试 ==================== */

TEST(permission_mode_conversion) {
    ASSERT_STR_EQ(permission_mode_to_string(PERMISSION_MODE_DEFAULT), "default");
    ASSERT_STR_EQ(permission_mode_to_string(PERMISSION_MODE_AUTO), "auto");
    ASSERT_STR_EQ(permission_mode_to_string(PERMISSION_MODE_BYPASS), "bypass");
}

TEST(hyperauto_mode_conversion) {
    ASSERT_STR_EQ(hyperauto_mode_to_string(HYPERAUTO_MODE_SEMI_AUTO), "semi_auto");
    ASSERT_STR_EQ(hyperauto_mode_to_string(HYPERAUTO_MODE_FULL_AUTO), "full_auto");
    ASSERT_STR_EQ(hyperauto_mode_to_string(HYPERAUTO_MODE_HYPER_AUTO), "hyper_auto");
}

TEST(provider_type_conversion) {
    ASSERT_STR_EQ(provider_type_to_string(PROVIDER_OPENAI), "openai");
    ASSERT_STR_EQ(provider_type_to_string(PROVIDER_ANTHROPIC), "anthropic");
    ASSERT_STR_EQ(provider_type_to_string(PROVIDER_OLLAMA), "ollama");
    ASSERT_STR_EQ(provider_type_to_string(PROVIDER_GEMINI), "gemini");
    ASSERT_STR_EQ(provider_type_to_string(PROVIDER_MINIMAX), "minimax");
}

/* ==================== 错误处理测试 ==================== */

TEST(error_handler_basic) {
    error_clear();
    
    Error* err = error_get();
    ASSERT_NULL(err);
}

TEST(error_code_strings) {
    ASSERT_STR_EQ(error_code_to_string(ERROR_NONE), "No error");
    ASSERT_STR_EQ(error_code_to_string(ERROR_MEMORY), "Memory error");
    ASSERT_STR_EQ(error_code_to_string(ERROR_FILE_NOT_FOUND), "File not found");
    ASSERT_STR_EQ(error_code_to_string(ERROR_INVALID_INPUT), "Invalid input");
}

/* ==================== 扩展类型测试 ==================== */

TEST(provider_config_full) {
    ProviderConfig* config = provider_config_create(PROVIDER_OPENAI, "test_provider");
    ASSERT_NOT_NULL(config);
    
    config->api_key = strdup("test_key");
    config->base_url = strdup("https://api.openai.com");
    config->default_model = strdup("gpt-4");
    config->max_tokens = 4096;
    config->temperature = 0.7;
    config->supports_streaming = true;
    config->supports_tools = true;
    config->supports_vision = true;
    
    ASSERT_EQ(config->type, PROVIDER_OPENAI);
    ASSERT_STR_EQ(config->name, "test_provider");
    ASSERT_EQ(config->max_tokens, 4096);
    ASSERT_TRUE(config->supports_streaming);
    ASSERT_TRUE(config->supports_tools);
    ASSERT_TRUE(config->supports_vision);
    
    provider_config_destroy(config);
}

TEST(permission_config_default) {
    PermissionConfig* config = permission_config_create();
    ASSERT_NOT_NULL(config);
    
    config->mode = PERMISSION_MODE_AUTO;
    config->auto_approve_safe = true;
    config->auto_approve_all = false;
    
    ASSERT_EQ(config->mode, PERMISSION_MODE_AUTO);
    ASSERT_TRUE(config->auto_approve_safe);
    ASSERT_FALSE(config->auto_approve_all);
    
    permission_config_destroy(config);
}

TEST(session_info_basic) {
    SessionInfo* session = session_info_create("session_123");
    ASSERT_NOT_NULL(session);
    
    session->working_directory = strdup("/tmp/work");
    session->start_time = time(NULL);
    
    ASSERT_STR_EQ(session->session_id, "session_123");
    ASSERT_NOT_NULL(session->working_directory);
    
    session_info_destroy(session);
}

int main() {
    printf("=== OpenLaoKe 功能完整性测试 ===\n\n");
    
    printf("--- 工具功能测试 ---\n");
    RUN_TEST(tool_bash_create_and_destroy);
    RUN_TEST(tool_registry_multiple_registration);
    RUN_TEST(tool_result_block_with_error);
    RUN_TEST(tool_result_block_without_error);
    
    printf("\n--- 状态管理测试 ---\n");
    RUN_TEST(state_multiple_messages);
    RUN_TEST(state_clear_messages);
    RUN_TEST(state_to_json);
    RUN_TEST(state_set_and_get_cwd);
    
    printf("\n--- 消息类型测试 ---\n");
    RUN_TEST(message_all_roles);
    RUN_TEST(message_with_tool_info);
    
    printf("\n--- 类型转换测试 ---\n");
    RUN_TEST(permission_mode_conversion);
    RUN_TEST(hyperauto_mode_conversion);
    RUN_TEST(provider_type_conversion);
    
    printf("\n--- 错误处理测试 ---\n");
    RUN_TEST(error_handler_basic);
    RUN_TEST(error_code_strings);
    
    printf("\n--- 扩展类型测试 ---\n");
    RUN_TEST(provider_config_full);
    RUN_TEST(permission_config_default);
    RUN_TEST(session_info_basic);
    
    printf("\n=== 测试结果 ===\n");
    printf("总计: %d\n", tests_passed + tests_failed);
    printf("通过: %d\n", tests_passed);
    printf("失败: %d\n", tests_failed);
    
    if (tests_failed > 0) {
        printf("\n✗ 有 %d 个测试失败\n", tests_failed);
        return 1;
    }
    
    printf("\n✓ 所有功能完整性测试通过！\n");
    return 0;
}