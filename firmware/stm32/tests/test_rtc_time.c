/* 1128 (김채희): RTC local calendar (KST) -> UTC Unix seconds, parse/format. PC only. */
#include "rtc_time.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint32_t kst(const char *s) {
    RtcTime t;
    assert(rtc_parse(s, &t));
    return rtc_to_unix(&t, 32400);
}

int main(void) {
    /* Reference values from Python calendar.timegm(UTC) for the same instants. */
    assert(kst("2026-11-28 15:00:00") == 1795845600u);
    assert(kst("2000-01-01 00:00:00") == 946652400u);
    assert(kst("2024-02-29 23:59:59") == 1709218799u);   /* leap day */
    assert(kst("2099-12-31 23:59:59") == 4102412399u);   /* last supported second */
    assert(kst("2026-03-01 00:00:00") - kst("2026-02-28 00:00:00") == 86400u);  /* non-leap */
    assert(kst("2028-03-01 00:00:00") - kst("2028-02-28 00:00:00") == 2u * 86400u);

    RtcTime t;
    const char *bad[] = {"2026-02-29 00:00:00", "2026-13-01 00:00:00", "2026-11-31 00:00:00",
                         "2026-11-28 24:00:00", "2026-11-28 15:60:00", "1999-12-31 23:59:59",
                         "2100-01-01 00:00:00", "2026-11-28 15:00", "2026-11-28 15:00:000",
                         "2026/11/28 15:00:00", "2026-11-28T15:00:00", "2026-1a-28 15:00:00", ""};
    for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i) assert(!rtc_parse(bad[i], &t));

    /* Invalid / not-read time is 0, which the policy treats as "unknown" (B/D -> 04). */
    RtcTime zero = {0};
    assert(rtc_to_unix(&zero, 32400) == 0u);
    assert(rtc_parse("2026-11-28 15:00:00", &t));
    t.valid = false;
    assert(rtc_to_unix(&t, 32400) == 0u);
    t.valid = true; t.day = 31; t.month = 11;              /* valid flag but impossible date */
    assert(rtc_to_unix(&t, 32400) == 0u);

    char text[24];
    assert(rtc_parse("2026-11-28 09:05:07", &t) && rtc_format(&t, text, sizeof(text)));
    assert(!strcmp(text, "2026-11-28 09:05:07"));
    assert(!rtc_format(&t, text, 19u));
    puts("PASS rtc_time: KST->UTC unix (leap/range), strict parse, invalid -> 0, format");
    return 0;
}
