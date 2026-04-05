#include "../include/tool_registry.h"
#include "../include/types.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <curl/curl.h>

#define MAX_RESPONSE_SIZE 1048576

typedef struct {
    char* url;
    char* format;
    int timeout;
} WebFetchInput;

typedef struct {
    char* data;
    size_t size;
} CurlResponse;

static size_t webfetch_curl_callback(void* contents, size_t size, size_t nmemb, void* userp) {
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

static WebFetchInput* webfetch_input_parse(const char* json) {
    WebFetchInput* input = calloc(1, sizeof(WebFetchInput));
    if (!input) return NULL;
    
    input->url = extract_json_string_value(json, "\"url\"");
    input->format = extract_json_string_value(json, "\"format\"");
    input->timeout = 30;
    
    char* timeout_str = extract_json_string_value(json, "\"timeout\"");
    if (timeout_str) {
        input->timeout = atoi(timeout_str);
        free(timeout_str);
    }
    
    if (!input->format) {
        input->format = strdup("markdown");
    }
    
    return input;
}

static void webfetch_input_free(WebFetchInput* input) {
    if (input) {
        free(input->url);
        free(input->format);
        free(input);
    }
}

static char* convert_to_format(const char* html, const char* format) {
    if (strcmp(format, "text") == 0 || strcmp(format, "markdown") == 0) {
        char* result = malloc(strlen(html) + 1);
        strcpy(result, html);
        return result;
    }
    
    return strdup(html);
}

ToolResultBlock* webfetch_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    (void)tool;
    (void)ctx;
    
    WebFetchInput* input = webfetch_input_parse(input_json);
    if (!input) {
        return tool_result_block_create("webfetch_error", 
            "Error: Failed to parse input JSON", true);
    }
    
    if (!input->url || strlen(input->url) == 0) {
        webfetch_input_free(input);
        return tool_result_block_create("webfetch_error", 
            "Error: url is required", true);
    }
    
    if (strncmp(input->url, "http://", 7) != 0 && strncmp(input->url, "https://", 8) != 0) {
        char* fixed_url = malloc(strlen(input->url) + 9);
        sprintf(fixed_url, "https://%s", input->url);
        free(input->url);
        input->url = fixed_url;
    }
    
    CURL* curl = curl_easy_init();
    if (!curl) {
        webfetch_input_free(input);
        return tool_result_block_create("webfetch_error", 
            "Error: Failed to initialize curl", true);
    }
    
    CurlResponse response;
    response.data = malloc(MAX_RESPONSE_SIZE);
    response.size = 0;
    response.data[0] = '\0';
    
    curl_easy_setopt(curl, CURLOPT_URL, input->url);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, webfetch_curl_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, input->timeout);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "OpenLaoKe/0.1.14");
    
    CURLcode res = curl_easy_perform(curl);
    curl_easy_cleanup(curl);
    
    if (res != CURLE_OK) {
        char error[512];
        snprintf(error, sizeof(error), "Error: Failed to fetch URL: %s (%s)", 
                 input->url, curl_easy_strerror(res));
        free(response.data);
        webfetch_input_free(input);
        return tool_result_block_create("webfetch_error", error, true);
    }
    
    char* formatted = convert_to_format(response.data, input->format);
    free(response.data);
    
    char* output = malloc(strlen(formatted) + strlen(input->url) + 100);
    snprintf(output, strlen(formatted) + strlen(input->url) + 100, 
             "Fetched from: %s\nFormat: %s\n\n%s", 
             input->url, input->format, formatted);
    free(formatted);
    webfetch_input_free(input);
    
    ToolResultBlock* block = tool_result_block_create("webfetch_result", output, false);
    free(output);
    return block;
}

Tool* webfetch_tool_create(void) {
    Tool* tool = calloc(1, sizeof(Tool));
    tool->name = strdup("WebFetch");
    tool->description = strdup(
        "Fetch content from a URL and return in specified format. "
        "Supports markdown, text, and html formats.");
    tool->execute = webfetch_tool_execute;
    tool->is_read_only = true;
    tool->is_destructive = false;
    tool->is_concurrency_safe = true;
    tool->requires_approval = false;
    return tool;
}