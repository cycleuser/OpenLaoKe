#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

typedef enum {
    ERROR_NONE = 0,
    ERROR_MEMORY,
    ERROR_FILE_NOT_FOUND,
    ERROR_PERMISSION_DENIED,
    ERROR_INVALID_INPUT,
    ERROR_TIMEOUT,
    ERROR_NETWORK,
    ERROR_API,
    ERROR_TOOL_EXECUTION,
    ERROR_UNKNOWN
} ErrorCode;

typedef struct {
    ErrorCode code;
    char* message;
    char* file;
    int line;
    char* function;
} Error;

static Error* current_error = NULL;

void error_set(ErrorCode code, const char* message, const char* file, int line, const char* function) {
    if (current_error) {
        free(current_error->message);
        free(current_error->file);
        free(current_error->function);
    } else {
        current_error = calloc(1, sizeof(Error));
    }
    
    if (current_error) {
        current_error->code = code;
        current_error->message = message ? strdup(message) : NULL;
        current_error->file = file ? strdup(file) : NULL;
        current_error->line = line;
        current_error->function = function ? strdup(function) : NULL;
    }
}

#define ERROR(code, msg) error_set(code, msg, __FILE__, __LINE__, __func__)

Error* error_get(void) {
    return current_error;
}

void error_clear(void) {
    if (current_error) {
        free(current_error->message);
        free(current_error->file);
        free(current_error->function);
        free(current_error);
        current_error = NULL;
    }
}

const char* error_code_to_string(ErrorCode code) {
    switch (code) {
        case ERROR_NONE: return "No error";
        case ERROR_MEMORY: return "Memory error";
        case ERROR_FILE_NOT_FOUND: return "File not found";
        case ERROR_PERMISSION_DENIED: return "Permission denied";
        case ERROR_INVALID_INPUT: return "Invalid input";
        case ERROR_TIMEOUT: return "Timeout";
        case ERROR_NETWORK: return "Network error";
        case ERROR_API: return "API error";
        case ERROR_TOOL_EXECUTION: return "Tool execution error";
        default: return "Unknown error";
    }
}

void error_print(void) {
    if (current_error) {
        fprintf(stderr, "Error: %s\n", error_code_to_string(current_error->code));
        if (current_error->message) {
            fprintf(stderr, "Message: %s\n", current_error->message);
        }
        if (current_error->file && current_error->function) {
            fprintf(stderr, "At: %s:%d in %s()\n", 
                    current_error->file, current_error->line, current_error->function);
        }
    }
}

int check_null(void* ptr, const char* msg) {
    if (!ptr) {
        ERROR(ERROR_MEMORY, msg ? msg : "Null pointer");
        return 0;
    }
    return 1;
}

int check_file_exists(const char* path) {
    FILE* f = fopen(path, "r");
    if (!f) {
        ERROR(ERROR_FILE_NOT_FOUND, path);
        return 0;
    }
    fclose(f);
    return 1;
}
