/* OpenLaoKe C - Main entry point */

#include "include/types.h"
#include "include/state.h"
#include "include/tool_registry.h"
#include "include/tools.h"
#include "include/repl.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>

#define VERSION "0.1.14"
#define MAX_INPUT_LENGTH 4096

/* Global state for signal handling */
static REPLContext* global_repl = NULL;

void signal_handler(int sig) {
    if (sig == SIGINT || sig == SIGTERM) {
        printf("\n\nReceived interrupt signal. Exiting gracefully...\n");
        if (global_repl) {
            repl_signal_exit(global_repl);
        }
    }
}

void print_banner(void) {
    printf("╭─────────────────────────────────╮\n");
    printf("│ OpenLaoKe C v%-15s     │\n", VERSION);
    printf("│ Open-source AI coding assistant │\n");
    printf("╰─────────────────────────────────╯\n");
    printf("\n");
}

void print_help(void) {
    printf("Usage: openlaoke [OPTIONS]\n\n");
    printf("Options:\n");
    printf("  -d, --directory DIR   Set working directory\n");
    printf("  -m, --model MODEL     Set AI model to use\n");
    printf("  -p, --provider PROV   Set AI provider\n");
    printf("  -h, --help            Show this help message\n");
    printf("  -v, --version         Show version information\n");
    printf("\n");
    printf("Interactive commands:\n");
    printf("  /help                 Show help\n");
    printf("  /status               Show current status\n");
    printf("  /tools                List available tools\n");
    printf("  /exit                 Exit the program\n");
    printf("\n");
}

void print_version(void) {
    printf("OpenLaoKe C version %s\n", VERSION);
    printf("Build date: %s %s\n", __DATE__, __TIME__);
}

int process_interactive_command(REPLContext* repl, const char* input) {
    if (strcmp(input, "/help") == 0) {
        print_help();
        return 0;
    }
    
    if (strcmp(input, "/version") == 0 || strcmp(input, "/v") == 0) {
        print_version();
        return 0;
    }
    
    if (strcmp(input, "/exit") == 0 || strcmp(input, "/quit") == 0 || strcmp(input, "/q") == 0) {
        repl_signal_exit(repl);
        return 0;
    }
    
    if (strcmp(input, "/status") == 0) {
        AppState* state = repl->app_state;
        printf("Session ID: %s\n", state->session_id ? state->session_id : "N/A");
        printf("Working directory: %s\n", state->cwd);
        printf("Active model: %s\n", state->active_model ? state->active_model : "N/A");
        printf("Active provider: %s\n", state->active_provider ? state->active_provider : "N/A");
        printf("Tools available: %d\n", state->tools_available);
        printf("Total tokens: %d\n", state->total_tokens);
        printf("Total cost: $%.4f\n", state->total_cost);
        return 0;
    }
    
    if (strcmp(input, "/tools") == 0) {
        ToolRegistry* registry = repl->app_state->tool_registry;
        printf("Available tools (%d):\n", registry->count);
        for (int i = 0; i < registry->count; i++) {
            Tool* tool = registry->tools[i];
            printf("  - %s: %s\n", tool->name, tool->description);
        }
        return 0;
    }
    
    return -1;  /* Not a command, process as chat */
}

int main(int argc, char* argv[]) {
    char* working_dir = NULL;
    char* model = NULL;
    char* provider = NULL;
    
    /* Parse command line arguments */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            print_help();
            return 0;
        }
        
        if (strcmp(argv[i], "-v") == 0 || strcmp(argv[i], "--version") == 0) {
            print_version();
            return 0;
        }
        
        if (strcmp(argv[i], "-d") == 0 || strcmp(argv[i], "--directory") == 0) {
            if (i + 1 < argc) {
                working_dir = argv[++i];
            } else {
                fprintf(stderr, "Error: --directory requires an argument\n");
                return 1;
            }
        }
        
        if (strcmp(argv[i], "-m") == 0 || strcmp(argv[i], "--model") == 0) {
            if (i + 1 < argc) {
                model = argv[++i];
            } else {
                fprintf(stderr, "Error: --model requires an argument\n");
                return 1;
            }
        }
        
        if (strcmp(argv[i], "-p") == 0 || strcmp(argv[i], "--provider") == 0) {
            if (i + 1 < argc) {
                provider = argv[++i];
            } else {
                fprintf(stderr, "Error: --provider requires an argument\n");
                return 1;
            }
        }
    }
    
    /* Set working directory */
    if (!working_dir) {
        working_dir = getcwd(NULL, 0);
    }
    
    /* Print banner */
    print_banner();
    
    /* Create app state */
    AppState* app_state = app_state_create(working_dir);
    if (!app_state) {
        fprintf(stderr, "Failed to create application state\n");
        return 1;
    }
    
    /* Register tools */
    app_state->tools_available = tools_register_all(app_state->tool_registry);
    
    /* Set model and provider */
    if (model) {
        app_state_set_model(app_state, provider, model);
    }
    
    /* Create REPL */
    REPLContext* repl = repl_create(app_state);
    if (!repl) {
        fprintf(stderr, "Failed to create REPL context\n");
        app_state_destroy(app_state);
        return 1;
    }
    
    global_repl = repl;
    
    /* Setup signal handlers */
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    printf("Provider: %s\n", app_state->active_provider ? app_state->active_provider : "default");
    printf("Model: %s\n", app_state->active_model ? app_state->active_model : "default");
    printf("Working directory: %s\n", app_state->cwd);
    printf("Tools: %d available\n", app_state->tools_available);
    printf("\nType /help for commands, or just start chatting.\n\n");
    
    /* Main REPL loop */
    char input[MAX_INPUT_LENGTH];
    while (!repl_should_exit(repl)) {
        printf("OpenLaoKe: ");
        fflush(stdout);
        
        if (fgets(input, sizeof(input), stdin) == NULL) {
            break;  /* EOF */
        }
        
        /* Remove trailing newline */
        size_t len = strlen(input);
        if (len > 0 && input[len - 1] == '\n') {
            input[len - 1] = '\0';
        }
        
        /* Skip empty input */
        if (strlen(input) == 0) {
            continue;
        }
        
        /* Process command or chat */
        if (input[0] == '/') {
            process_interactive_command(repl, input);
        } else {
            /* Process as chat message */
            printf("Processing: %s\n", input);
            printf("(AI response would appear here)\n\n");
        }
    }
    
    /* Cleanup */
    printf("\nGoodbye!\n");
    repl_destroy(repl);
    app_state_destroy(app_state);
    
    return 0;
}