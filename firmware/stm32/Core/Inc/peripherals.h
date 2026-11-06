#ifndef VEHICLE_PERIPHERALS_H
#define VEHICLE_PERIPHERALS_H
#include "control.h"
#include "vehicle_platform.h"
#include <stdbool.h>
typedef struct { unsigned year, month, day, hour, minute, second; bool valid; } RtcTime;
bool rtc_valid_date(const RtcTime *t);
bool rtc_read(RtcTime *t);
bool rtc_set(const RtcTime *t); /* Local trusted setup only; not wired to remote unauthenticated input. */
void oled_init(void);
void oled_status(const Controller *c, const RtcTime *t, const VehicleDisplay *d);
void oled_service(void);
bool oled_online(void);
#endif
