#ifndef VEHICLE_RTC_TIME_H
#define VEHICLE_RTC_TIME_H
/* 1128 (김채희): pure RTC date helpers (no HAL), testable on a PC.
 * RtcTime holds the DS3231 calendar in local time (Korea for this project). */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct { unsigned year, month, day, hour, minute, second; bool valid; } RtcTime;
bool rtc_valid_date(const RtcTime *t);
/* Local calendar -> UTC Unix seconds (local - offset_s). 0 = invalid or out of range. */
uint32_t rtc_to_unix(const RtcTime *t, int32_t offset_s);
/* "YYYY-MM-DD HH:MM:SS" (2000..2099) -> RtcTime. false on any format/range error. */
bool rtc_parse(const char *s, RtcTime *t);
/* RtcTime -> "YYYY-MM-DD HH:MM:SS". false if invalid or n < 20. */
bool rtc_format(const RtcTime *t, char *out, size_t n);
#endif
