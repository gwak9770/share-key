#ifndef VEHICLE_APP_H
#define VEHICLE_APP_H
#include "control.h"
#include "vehicle_platform.h"
#include <stdbool.h>
bool vehicle_app_init(void);
void vehicle_app_step(void);
const Controller *vehicle_app_controller(void);
const VehicleDisplay *vehicle_app_display(void);
char vehicle_app_mode(void);            /* A/C chosen at boot (see VC_DEMO_MODE_SELECT) */
/* Local control hooks: never bind to unauthenticated network commands. */
Result vehicle_app_request_lock(void);
void vehicle_app_stop(void);
Result vehicle_app_clear_fault(void);
/* Override this weak hook only after selecting a return KID in the team design.
 * The default logs the physical press and does not alter any key state. */
void vehicle_on_return_button(void);
/* Compatible with the previously generated main.c call; does not return. */
void sk_app_run(void);
#endif
