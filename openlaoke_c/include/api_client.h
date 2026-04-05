#ifndef OPENLAOKE_API_CLIENT_H
#define OPENLAOKE_API_CLIENT_H

#include "types.h"
#include "types_extended.h"
#include "tool_registry.h"

typedef enum {
    API_PROVIDER_OPENAI,
    API_PROVIDER_ANTHROPIC,
    API_PROVIDER_OLLAMA,
    API_PROVIDER_AZURE,
    API_PROVIDER_GEMINI,
    API_PROVIDER_MINIMAX,
    API_PROVIDER_CUSTOM
} APIProvider;

typedef struct {
    APIProvider provider;
    char* api_key;
    char* base_url;
    char* model;
    int max_tokens;
    double temperature;
} APIConfig;

typedef struct {
    char* content;
    TokenUsage token_usage;
    CostInfo cost;
    bool is_error;
    char* error_message;
} APIResponse;

typedef struct {
    APIConfig* config;
    void* http_client;
} APIClient;

APIClient* api_client_create(APIConfig* config);
void api_client_destroy(APIClient* client);

APIResponse* api_client_send_message(
    APIClient* client,
    const char* system_prompt,
    Message** messages,
    int message_count
);

APIResponse* api_client_send_message_with_tools(
    APIClient* client,
    const char* system_prompt,
    Message** messages,
    int message_count,
    struct Tool** tools,
    int tool_count
);

APIConfig* api_config_create(APIProvider provider, const char* api_key, const char* model);
void api_config_destroy(APIConfig* config);

APIResponse* api_response_create(void);
void api_response_destroy(APIResponse* response);

#endif
