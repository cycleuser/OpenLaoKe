/* OpenLaoKe C - REPL (Read-Eval-Print Loop) */

#ifndef OPENLAOKE_REPL_H
#define OPENLAOKE_REPL_H

#include "types.h"
#include "state.h"

/* REPL state */
typedef enum {
    REPL_STATE_IDLE,
    REPL_STATE_THINKING,
    REPL_STATE_EXECUTING_TOOL,
    REPL_STATE_WAITING_INPUT,
    REPL_STATE_EXITING
} REPLState;

/* REPL context */
typedef struct {
    AppState* app_state;
    REPLState state;
    char* current_input;
    char* last_output;
    bool running;
    int iteration_count;
    int max_iterations;
} REPLContext;

/* REPL functions */
REPLContext* repl_create(AppState* app_state);
void repl_destroy(REPLContext* repl);

/* Main loop */
int repl_run(REPLContext* repl);
int repl_step(REPLContext* repl);

/* Input/Output */
char* repl_read_input(REPLContext* repl);
int repl_process_input(REPLContext* repl, const char* input);
int repl_display_output(REPLContext* repl, const char* output);

/* Commands */
int repl_execute_command(REPLContext* repl, const char* command);
int repl_execute_skill(REPLContext* repl, const char* skill_name, const char* args);

/* State management */
void repl_set_state(REPLContext* repl, REPLState state);
REPLState repl_get_state(REPLContext* repl);

/* Utility */
bool repl_should_exit(REPLContext* repl);
void repl_signal_exit(REPLContext* repl);

#endif /* OPENLAOKE_REPL_H */