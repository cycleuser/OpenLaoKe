/* OpenLaoKe C - Multi-provider API client implementation */

#include "../include/api_client.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

/* Memory buffer for HTTP response */
typedef struct {
    char* data;
    size_t size;
} MemoryBuffer;

static size_t write_callback(void* contents, size_t size, size_t nmemb, void* userp) {
    size_t realsize = size * nmemb;
    MemoryBuffer* mem = (MemoryBuffer*)userp;
    
    char* ptr = realloc(mem->data, mem->size + realsize + 1);
    if (!ptr) return 0;
    
    mem->data = ptr;
    memcpy(&(mem->data[mem->size]), contents, realsize);
    mem->size += realsize;
    mem->data[mem->size] = '\0';
    
    return realsize;
}

APIClient* api_client_create(APIConfig* config) {
    if (!config) return NULL;
    
    APIClient* client = (APIClient*)calloc(1, sizeof(APIClient));
    if (!client) return NULL;
    
    client->config = config;
    
    /* Initialize curl */
    curl_global_init(CURL_GLOBAL_DEFAULT);
    
    return client;
}

void api_client_destroy(APIClient* client) {
    if (!client) return;
    
    curl_global_cleanup();
    api_config_destroy(client->config);
    free(client);
}

APIConfig* api_config_create(APIProvider provider, const char* api_key, const char* model) {
    APIConfig* config = (APIConfig*)calloc(1, sizeof(APIConfig));
    if (!config) return NULL;
    
    config->provider = provider;
    config->api_key = api_key ? strdup(api_key) : NULL;
    config->model = model ? strdup(model) : NULL;
    config->max_tokens = 4096;
    config->temperature = 0.7;
    
    /* Set base URL based on provider */
    switch (provider) {
        case PROVIDER_OPENAI:
            config->base_url = strdup("https://api.openai.com/v1");
            break;
        case PROVIDER_ANTHROPIC:
            config->base_url = strdup("https://api.anthropic.com/v1");
            break;
        case PROVIDER_OLLAMA:
            config->base_url = strdup("http://localhost:11434/api");
            break;
        case PROVIDER_MINIMAX:
            config->base_url = strdup("https://api.minimax.chat/v1");
            break;
        default:
            config->base_url = strdup("http://localhost:8000/v1");
            break;
    }
    
    return config;
}

void api_config_destroy(APIConfig* config) {
    if (!config) return;
    free(config->api_key);
    free(config->base_url);
    free(config->model);
    free(config);
}

APIResponse* api_response_create(void) {
    return (APIResponse*)calloc(1, sizeof(APIResponse));
}

void api_response_destroy(APIResponse* response) {
    if (!response) return;
    free(response->content);
    free(response->error_message);
    free(response);
}

APIResponse* api_client_send_message(
    APIClient* client,
    const char* system_prompt,
    Message** messages,
    int message_count
) {
    if (!client || !messages || message_count == 0) {
        return NULL;
    }
    
    CURL* curl = curl_easy_init();
    if (!curl) return NULL;
    
    APIResponse* response = api_response_create();
    if (!response) {
        curl_easy_cleanup(curl);
        return NULL;
    }
    
    /* Build JSON request body */
    char* body = (char*)malloc(65536);
    if (!body) {
        api_response_destroy(response);
        curl_easy_cleanup(curl);
        return NULL;
    }
    
    char* p = body;
    p += sprintf(p, "{\"model\":\"%s\",\"messages\":[", 
                 client->config->model ? client->config->model : "gpt-3.5-turbo");
    
    /* Add system prompt */
    if (system_prompt) {
        p += sprintf(p, "{\"role\":\"system\",\"content\":\"%s\"}", system_prompt);
        if (message_count > 0) p += sprintf(p, ",");
    }
    
    /* Add messages */
    for (int i = 0; i < message_count; i++) {
        if (i > 0) p += sprintf(p, ",");
        
        const char* role;
        switch (messages[i]->role) {
            case MESSAGE_ROLE_USER: role = "user"; break;
            case MESSAGE_ROLE_ASSISTANT: role = "assistant"; break;
            case MESSAGE_ROLE_SYSTEM: role = "system"; break;
            default: role = "user";
        }
        
        p += sprintf(p, "{\"role\":\"%s\",\"content\":\"%s\"}", 
                     role, messages[i]->content ? messages[i]->content : "");
    }
    
    p += sprintf(p, "],\"max_tokens\":%d,\"temperature\":%.2f}", 
                 client->config->max_tokens, client->config->temperature);
    
    /* Setup curl request */
    MemoryBuffer chunk;
    chunk.data = malloc(1);
    chunk.size = 0;
    
    struct curl_slist* headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    
    char auth_header[256];
    if (client->config->provider == PROVIDER_ANTHROPIC) {
        snprintf(auth_header, sizeof(auth_header), "x-api-key: %s", 
                 client->config->api_key ? client->config->api_key : "");
        headers = curl_slist_append(headers, auth_header);
        headers = curl_slist_append(headers, "anthropic-version: 2023-06-01");
    } else {
        snprintf(auth_header, sizeof(auth_header), "Authorization: Bearer %s", 
                 client->config->api_key ? client->config->api_key : "");
        headers = curl_slist_append(headers, auth_header);
    }
    
    /* Build URL */
    char url[512];
    if (client->config->provider == PROVIDER_ANTHROPIC) {
        snprintf(url, sizeof(url), "%s/messages", client->config->base_url);
    } else {
        snprintf(url, sizeof(url), "%s/chat/completions", client->config->base_url);
    }
    
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void*)&chunk);
    
    /* Perform request */
    CURLcode res = curl_easy_perform(curl);
    
    if (res != CURLE_OK) {
        response->is_error = true;
        response->error_message = strdup(curl_easy_strerror(res));
    } else {
        response->content = chunk.data;
        response->is_error = false;
    }
    
    /* Cleanup */
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    free(body);
    
    return response;
}

APIResponse* api_client_send_message_with_tools(
    APIClient* client,
    const char* system_prompt,
    Message** messages,
    int message_count,
    Tool** tools,
    int tool_count
) {
    /* For now, same as regular message but add tools to request */
    /* This is a simplified version */
    return api_client_send_message(client, system_prompt, messages, message_count);
}

const char* provider_type_to_string(ProviderType type) {
    switch (type) {
        case PROVIDER_OPENAI: return "openai";
        case PROVIDER_ANTHROPIC: return "anthropic";
        case PROVIDER_AZURE: return "azure";
        case PROVIDER_OLLAMA: return "ollama";
        case PROVIDER_MINIMAX: return "minimax";
        case PROVIDER_GEMINI: return "gemini";
        case PROVIDER_CUSTOM: return "custom";
        default: return "unknown";
    }
}

ProviderType string_to_provider_type(const char* str) {
    if (!str) return PROVIDER_CUSTOM;
    
    if (strcmp(str, "openai") == 0) return PROVIDER_OPENAI;
    if (strcmp(str, "anthropic") == 0) return PROVIDER_ANTHROPIC;
    if (strcmp(str, "azure") == 0) return PROVIDER_AZURE;
    if (strcmp(str, "ollama") == 0) return PROVIDER_OLLAMA;
    if (strcmp(str, "minimax") == 0) return PROVIDER_MINIMAX;
    if (strcmp(str, "gemini") == 0) return PROVIDER_GEMINI;
    
    return PROVIDER_CUSTOM;
}