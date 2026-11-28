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
    char mode;                   /* comparison mode chosen at boot (A/B/C/D); 0 = APP_POLICY_MODE. */
    bool rtc_bad;                /* B/D and the RTC is unreadable: period keys denied (04). */
    int remaining, command;
    Result actuation;
    bool actuation_attempted;
    bool engine_running, reauth_warning, stopped;
    uint32_t reauth_left_s;
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
void vc_platform_tone(uint16_t hz);   /* passive buzzer pitch, 0 = silent; no-op when disabled */
bool vc_platform_return_pressed(void);
bool vc_platform_mode_button(void);   /* demo mode select (USER button), false if disabled */
void vc_platform_service(const Controller *c, const VehicleDisplay *display);
void vc_platform_panic(void);   /* Stops all outputs; hardware implementation never returns. */
/* 1128: used only when VC_ENABLE_RTC=1. UTC Unix seconds from the RTC, 0 = unknown. */
uint32_t vc_platform_unix_time(void);
bool vc_platform_rtc_text(char *out, size_t n);       /* local "YYYY-MM-DD HH:MM:SS" */
bool vc_platform_rtc_set_text(const char *local);     /* TEST_BUILD bench console only */
#endif
