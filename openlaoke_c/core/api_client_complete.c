#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>
#include "../include/tool_registry.h"

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

char* api_call(const char* url, const char* api_key, const char* model, 
               const char* system_prompt, const char* user_message) {
    CURL* curl = curl_easy_init();
    if (!curl) return NULL;
    
    /* Build request body */
    char* body = malloc(65536);
    snprintf(body, 65536,
        "{\"model\":\"%s\",\"messages\":["
        "{\"role\":\"system\",\"content\":\"%s\"},"
        "{\"role\":\"user\",\"content\":\"%s\"}"
        "],\"max_tokens\":4096,\"temperature\":0.7}",
        model, system_prompt, user_message);
    
    MemoryBuffer chunk;
    chunk.data = malloc(1);
    chunk.size = 0;
    
    struct curl_slist* headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    
    char auth[256];
    snprintf(auth, sizeof(auth), "Authorization: Bearer %s", api_key);
    headers = curl_slist_append(headers, auth);
    
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void*)&chunk);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 60L);
    
    CURLcode res = curl_easy_perform(curl);
    
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    free(body);
    
    if (res != CURLE_OK) {
        free(chunk.data);
        return NULL;
    }
    
    return chunk.data;
}

char* extract_content(const char* json_response) {
    const char* content_start = strstr(json_response, "\"content\"");
    if (!content_start) return NULL;
    
    content_start = strchr(content_start, ':');
    if (!content_start) return NULL;
    
    content_start = strchr(content_start, '"');
    if (!content_start) return NULL;
    
    content_start++;
    const char* content_end = strchr(content_start, '"');
    if (!content_end) return NULL;
    
    size_t len = content_end - content_start;
    char* content = malloc(len + 1);
    strncpy(content, content_start, len);
    content[len] = '\0';
    
    return content;
}
