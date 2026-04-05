/* OpenLaoKe C - Error handler */

#ifndef OPENLAOKE_ERROR_HANDLER_H
#define OPENLAOKE_ERROR_HANDLER_H

/* Error codes */
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

/* Error structure */
typedef struct {
    ErrorCode code;
    char* message;
    char* file;
    int line;
    char* function;
} Error;

/* Error management */
void error_set(ErrorCode code, const char* message, const char* file, int line, const char* function);
Error* error_get(void);
void error_clear(void);
const char* error_code_to_string(ErrorCode code);
void error_print(void);

/* Convenience macros */
#define ERROR(code, msg) error_set(code, msg, __FILE__, __LINE__, __func__)
#define CHECK_NULL(ptr, msg) check_null(ptr, msg)
#define CHECK_FILE_EXISTS(path) check_file_exists(path)

/* Helper functions */
int check_null(void* ptr, const char* msg);
int check_file_exists(const char* path);

#endif /* OPENLAOKE_ERROR_HANDLER_H */