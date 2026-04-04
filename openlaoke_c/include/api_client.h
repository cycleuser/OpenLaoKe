/* OpenLaoKe C - Multi-provider API client */

#ifndef OPENLAOKE_API_CLIENT_H
#define OPENLAOKE_API_CLIENT_H

#include "types.h"

/* API provider types */
typedef enum {
    PROVIDER_OPENAI,
    PROVIDER_ANTHROPIC,
    PROVIDER_OLLAMA,
    PROVIDER_MINIMAX,
    PROVIDER_CUSTOM
} APIProvider;

/* API configuration */
typedef struct {
    APIProvider provider;
    char* api_key;
    char* base_url;
    char* model;
    int max_tokens;
    double temperature;
    void* user_data;
} APIConfig;

/* API response */
typedef struct {
    char* content;
    TokenUsage token_usage;
    CostInfo cost;
    bool is_error;
    char* error_message;
} APIResponse;

/* API client */
typedef struct {
    APIConfig* config;
    void* http_client;  /* HTTP client implementation */
} APIClient;

/* Client functions */
APIClient* api_client_create(APIConfig* config);
void api_client_destroy(APIClient* client);

/* API calls */
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
    Tool** tools,
    int tool_count
);

/* Configuration */
APIConfig* api_config_create(APIProvider provider, const char* api_key, const char* model);
void api_config_destroy(APIConfig* config);

/* Response management */
APIResponse* api_response_create(void);
void api_response_destroy(APIResponse* response);

#endif /* OPENLAOKE_API_CLIENT_H */