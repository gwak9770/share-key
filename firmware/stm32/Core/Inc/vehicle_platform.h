#ifndef VEHICLE_PLATFORM_H
#define VEHICLE_PLATFORM_H
#include "control.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct {
    char policy;                 /* '-' boot / 'W' ready after refill / 'A' / 'D' / 'H' result; 'K' KEYOK / 'N' KEYNG (registration). Not mode or movement. */
    char reason[3];
    char kid[9];                 /* KID of the last KEYOK/KEYNG/RES, for display only. */
    char mode;                   /* comparison mode chosen at boot (A/C); 0 = APP_POLICY_MODE. */
    int remaining, command;
    Result actuation;
    bool actuation_attempted;
} VehicleDisplay;
bool vc_platform_init(void);
uint32_t vc_platform_millis(void);
Inputs vc_platform_inputs(void);
void vc_platform_apply(Outputs out);
int vc_platform_rx_get(void);
bool vc_platform_take_io_fault(void);
void vc_platform_send_line(const char *line);
void vc_platform_log(const char *line);
void vc_platform_random(uint8_t *out, size_t n);
void vc_platform_indicators(bool allow, bool online, bool deny);
bool vc_platform_return_pressed(void);
bool vc_platform_mode_button(void);   /* demo mode select (USER button), false if disabled */
void vc_platform_service(const Controller *c, const VehicleDisplay *display);
void vc_platform_panic(void);   /* Stops all outputs; hardware implementation never returns. */
#endif
