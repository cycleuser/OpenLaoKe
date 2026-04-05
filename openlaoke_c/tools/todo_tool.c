#include "../include/tool_registry.h"
#include "../include/types.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#define MAX_TODO_ITEMS 100
#define MAX_TODO_CONTENT 512

typedef enum {
    TODO_PENDING,
    TODO_IN_PROGRESS,
    TODO_COMPLETED,
    TODO_CANCELLED
} TodoStatus;

typedef enum {
    TODO_PRIORITY_LOW,
    TODO_PRIORITY_MEDIUM,
    TODO_PRIORITY_HIGH
} TodoPriority;

typedef struct {
    char* content;
    TodoStatus status;
    TodoPriority priority;
    int id;
} TodoItem;

typedef struct {
    TodoItem* items;
    int count;
    int capacity;
    int next_id;
} TodoList;

static TodoList* global_todo_list = NULL;

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

static TodoList* todo_list_get(void) {
    if (!global_todo_list) {
        global_todo_list = calloc(1, sizeof(TodoList));
        global_todo_list->capacity = MAX_TODO_ITEMS;
        global_todo_list->items = calloc(MAX_TODO_ITEMS, sizeof(TodoItem));
        global_todo_list->next_id = 1;
    }
    return global_todo_list;
}

static void todo_item_free(TodoItem* item) {
    if (item) {
        free(item->content);
    }
}

static TodoStatus parse_status(const char* status_str) {
    if (!status_str) return TODO_PENDING;
    
    if (strcmp(status_str, "pending") == 0) return TODO_PENDING;
    if (strcmp(status_str, "in_progress") == 0) return TODO_IN_PROGRESS;
    if (strcmp(status_str, "completed") == 0) return TODO_COMPLETED;
    if (strcmp(status_str, "cancelled") == 0) return TODO_CANCELLED;
    
    return TODO_PENDING;
}

static TodoPriority parse_priority(const char* priority_str) {
    if (!priority_str) return TODO_PRIORITY_MEDIUM;
    
    if (strcmp(priority_str, "low") == 0) return TODO_PRIORITY_LOW;
    if (strcmp(priority_str, "medium") == 0) return TODO_PRIORITY_MEDIUM;
    if (strcmp(priority_str, "high") == 0) return TODO_PRIORITY_HIGH;
    
    return TODO_PRIORITY_MEDIUM;
}

static const char* status_to_string(TodoStatus status) {
    switch (status) {
        case TODO_PENDING: return "pending";
        case TODO_IN_PROGRESS: return "in_progress";
        case TODO_COMPLETED: return "completed";
        case TODO_CANCELLED: return "cancelled";
        default: return "unknown";
    }
}

static const char* priority_to_string(TodoPriority priority) {
    switch (priority) {
        case TODO_PRIORITY_LOW: return "low";
        case TODO_PRIORITY_MEDIUM: return "medium";
        case TODO_PRIORITY_HIGH: return "high";
        default: return "unknown";
    }
}

static char* todo_list_to_json(TodoList* list) {
    char* json = malloc(list->count * 256 + 100);
    size_t offset = 0;
    
    offset += snprintf(json + offset, 256, "{\"todos\": [");
    
    for (int i = 0; i < list->count; i++) {
        if (i > 0) {
            offset += snprintf(json + offset, 10, ", ");
        }
        offset += snprintf(json + offset, 256, 
                          "{\"id\": %d, \"content\": \"%s\", \"status\": \"%s\", \"priority\": \"%s\"}",
                          list->items[i].id,
                          list->items[i].content,
                          status_to_string(list->items[i].status),
                          priority_to_string(list->items[i].priority));
    }
    
    offset += snprintf(json + offset, 100, "], \"count\": %d}", list->count);
    
    return json;
}

static int add_todo_item(TodoList* list, const char* content, const char* status, const char* priority) {
    if (list->count >= list->capacity) return -1;
    
    TodoItem* item = &list->items[list->count];
    item->id = list->next_id++;
    item->content = strdup(content);
    item->status = parse_status(status);
    item->priority = parse_priority(priority);
    
    list->count++;
    return item->id;
}

static bool update_todo_item(TodoList* list, int id, const char* status, const char* priority) {
    for (int i = 0; i < list->count; i++) {
        if (list->items[i].id == id) {
            if (status) {
                list->items[i].status = parse_status(status);
            }
            if (priority) {
                list->items[i].priority = parse_priority(priority);
            }
            return true;
        }
    }
    return false;
}

static bool remove_todo_item(TodoList* list, int id) {
    for (int i = 0; i < list->count; i++) {
        if (list->items[i].id == id) {
            todo_item_free(&list->items[i]);
            for (int j = i; j < list->count - 1; j++) {
                list->items[j] = list->items[j + 1];
            }
            list->count--;
            return true;
        }
    }
    return false;
}

ToolResultBlock* todo_tool_execute(Tool* tool, void* ctx, const char* input_json) {
    (void)tool;
    (void)ctx;
    
    TodoList* list = todo_list_get();
    
    char* action = extract_json_string_value(input_json, "\"action\"");
    if (!action) {
        action = strdup("list");
    }
    
    char* result = NULL;
    
    if (strcmp(action, "list") == 0) {
        result = todo_list_to_json(list);
    }
    else if (strcmp(action, "add") == 0) {
        char* content = extract_json_string_value(input_json, "\"content\"");
        if (!content) {
            result = strdup("{\"error\": \"content is required for add action\"}");
        } else {
            char* status = extract_json_string_value(input_json, "\"status\"");
            char* priority = extract_json_string_value(input_json, "\"priority\"");
            
            int id = add_todo_item(list, content, status, priority);
            
            result = malloc(256);
            snprintf(result, 256, "{\"success\": true, \"id\": %d, \"message\": \"Todo item added\"}", id);
            
            free(content);
            free(status);
            free(priority);
        }
    }
    else if (strcmp(action, "update") == 0) {
        char* id_str = extract_json_string_value(input_json, "\"id\"");
        if (!id_str) {
            result = strdup("{\"error\": \"id is required for update action\"}");
        } else {
            int id = atoi(id_str);
            char* status = extract_json_string_value(input_json, "\"status\"");
            char* priority = extract_json_string_value(input_json, "\"priority\"");
            
            bool updated = update_todo_item(list, id, status, priority);
            
            result = malloc(256);
            snprintf(result, 256, "{\"success\": %s, \"id\": %d}", 
                     updated ? "true" : "false", id);
            
            free(id_str);
            free(status);
            free(priority);
        }
    }
    else if (strcmp(action, "remove") == 0 || strcmp(action, "delete") == 0) {
        char* id_str = extract_json_string_value(input_json, "\"id\"");
        if (!id_str) {
            result = strdup("{\"error\": \"id is required for remove action\"}");
        } else {
            int id = atoi(id_str);
            bool removed = remove_todo_item(list, id);
            
            result = malloc(256);
            snprintf(result, 256, "{\"success\": %s, \"id\": %d}", 
                     removed ? "true" : "false", id);
            
            free(id_str);
        }
    }
    else if (strcmp(action, "clear") == 0) {
        for (int i = 0; i < list->count; i++) {
            todo_item_free(&list->items[i]);
        }
        list->count = 0;
        result = strdup("{\"success\": true, \"message\": \"All todos cleared\"}");
    }
    else {
        result = malloc(256);
        snprintf(result, 256, "{\"error\": \"Unknown action: %s\"}", action);
    }
    
    free(action);
    
    ToolResultBlock* block = tool_result_block_create("todo_result", result, false);
    free(result);
    return block;
}

Tool* todo_tool_create(void) {
    Tool* tool = calloc(1, sizeof(Tool));
    tool->name = strdup("TodoWrite");
    tool->description = strdup(
        "Manage a todo list for tracking progress. "
        "Actions: list, add, update, remove, clear.");
    tool->execute = todo_tool_execute;
    tool->is_read_only = false;
    tool->is_destructive = false;
    tool->is_concurrency_safe = true;
    tool->requires_approval = false;
    return tool;
}