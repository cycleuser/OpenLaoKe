#include "../include/tool_registry.h"
#include "../include/types.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <curl/curl.h>

#define MAX_RESPONSE_SIZE 1048576

typedef struct {
    char* query;
    char* engine;
    int max_results;
} WebSearchInput;

typedef struct {
    char* data;
    size_t size;
} CurlResponse;

static size_t websearch_curl_callback(void* contents, size_t size, size_t nmemb, void* userp) {
    size_t total_size = size * nmemb;
    CurlResponse* response = (CurlResponse*)userp;
    
    if (response->size + total_size >= MAX_RESPONSE_SIZE) {
        total_size = MAX_RESPONSE_SIZE - response->size - 1;
    }
    
    if (total_size > 0) {
        memcpy(response->data + response->size, contents, total_size);
        response->size += total_size;
        response->data[response->size] = '\0';
    }
    
    return size * nmemb;
}

static char* extract_json_string_value(const char* json, const char* key) {
    char* key_start = strstr(json, key);
    if (!key_start) return NULL;
    
    char* value_start = strchr(key_start + strlen(key), ':');
    if (!value_start) return NULL;
    
    while (*value_start == ' ' || *value_start == ':') value_start++;
    
    if (*value_start == '"') {
        value_start++;
        char* value_end = strchr(value_start, '"');
        if (!value_end) return NULL;
        size_t len = value_end - value_start;
        char* result = malloc(len + 1);
        strncpy(result, value_start, len);
        result[len] = '\0';
        return result;
    }
    
    return NULL;
}

static WebSearchInput* websearch_input_parse(const char* json) {
    WebSearchInput* input = calloc(1, sizeof(WebSearchInput));
    if (!input) return NULL;
    
    input->query = extract_json_string_value(json, "\"query\"");
    input->engine = extract_json_string_value(json, "\"engine\"");
    input->max_results = 5;
    
    char* max_str = extract_json_string_value(json, "\"max_results\"");
    if (max_str) {
        input->max_results = atoi(max_str);
        free(max_str);
    }
    
    if (!input->engine) {
        input->engine = strdup("duckduckgo");
    }
    
    return input;
}

static void websearch_input_free(WebSearchInput* input) {
    if (input) {
        free(input->query);
        free(input->engine);
        free(input);
    }
}

static char* build_search_url(const char* engine, const char* query) {
    char* url = malloc(512);
    
    if (strcmp(engine, "duckduckgo") == 0) {
        snprintf(url, 512, "https://duckduckgo.com/html/?q=%s", query);
    } else if (strcmp(engine, "google") == 0) {
        snprintf(url, 512, "https://www.google.com/search?q=%s", query);
    } else {
        snprintf(url, 512, "https://duckduckgo.com/html/?q=%s", query);
    }
    
    return url;
}

ToolResultBlock* websearch_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    (void)tool;
    (void)ctx;
    
    WebSearchInput* input = websearch_input_parse(input_json);
    if (!input) {
        return tool_result_block_create("websearch_error", 
            "Error: Failed to parse input JSON", true);
    }
    
    if (!input->query || strlen(input->query) == 0) {
        websearch_input_free(input);
        return tool_result_block_create("websearch_error", 
            "Error: query is required", true);
    }
    
    char* url = build_search_url(input->engine, input->query);
    
    CURL* curl = curl_easy_init();
    if (!curl) {
        free(url);
        websearch_input_free(input);
        return tool_result_block_create("websearch_error", 
            "Error: Failed to initialize curl", true);
    }
    
    CurlResponse response;
    response.data = malloc(MAX_RESPONSE_SIZE);
    response.size = 0;
    response.data[0] = '\0';
    
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, websearch_curl_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "OpenLaoKe/0.1.14");
    
    CURLcode res = curl_easy_perform(curl);
    curl_easy_cleanup(curl);
    free(url);
    
    if (res != CURLE_OK) {
        char error[512];
        snprintf(error, sizeof(error), "Error: Search failed: %s", 
                 curl_easy_strerror(res));
        free(response.data);
        websearch_input_free(input);
        return tool_result_block_create("websearch_error", error, true);
    }
    
    char* output = malloc(strlen(response.data) + strlen(input->query) + 256);
    snprintf(output, strlen(response.data) + strlen(input->query) + 256,
             "Search results for '%s' (engine: %s, max: %d):\n\n%s",
             input->query, input->engine, input->max_results, response.data);
    
    free(response.data);
    websearch_input_free(input);
    
    ToolResultBlock* block = tool_result_block_create("websearch_result", output, false);
    free(output);
    return block;
}

Tool* websearch_tool_create(void) {
    Tool* tool = calloc(1, sizeof(Tool));
    tool->name = strdup("WebSearch");
    tool->description = strdup(
        "Search the web for information. "
        "Supports multiple search engines (duckduckgo, google).");
    tool->execute = websearch_tool_execute;
    tool->is_read_only = true;
    tool->is_destructive = false;
    tool->is_concurrency_safe = true;
    tool->requires_approval = false;
    return tool;
}