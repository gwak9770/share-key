#include "rtc_time.h"
#include <stdio.h>

bool rtc_valid_date(const RtcTime *t) {
    static const unsigned days[]={31,28,31,30,31,30,31,31,30,31,30,31};
    if(t->year<2000||t->year>2099||t->month<1||t->month>12||
       t->hour>23||t->minute>59||t->second>59) return false;
    unsigned max=days[t->month-1]+(t->month==2 && t->year%4==0);
    return t->day>=1 && t->day<=max;
}

uint32_t rtc_to_unix(const RtcTime *t, int32_t offset_s) {
    if (!t || !t->valid || !rtc_valid_date(t)) return 0u;
    /* Days since 1970-01-01 for 2000..2099 (every 4th year is leap in this range). */
    static const unsigned before[]={0,31,59,90,120,151,181,212,243,273,304,334};
    unsigned y=t->year;
    uint64_t days=10957u;                                    /* 1970-01-01 .. 2000-01-01 */
    days+=(uint64_t)(y-2000u)*365u+(y-2000u+3u)/4u;          /* leap days before year y */
    days+=before[t->month-1]+(t->month>2 && y%4u==0u)+(t->day-1u);
    int64_t s=(int64_t)(days*86400u+t->hour*3600u+t->minute*60u+t->second)-(int64_t)offset_s;
    return (s<=0 || s>=0xFFFFFFFFll) ? 0u : (uint32_t)s;
}

static bool digits(const char *s, unsigned n, unsigned *v) {
    unsigned x=0;
    for (unsigned i=0;i<n;++i) { if (s[i]<'0'||s[i]>'9') return false; x=x*10u+(unsigned)(s[i]-'0'); }
    *v=x; return true;
}
bool rtc_parse(const char *s, RtcTime *t) {
    RtcTime r={0};
    if (!s || !t) return false;
    for (unsigned i=0;i<19u;++i) if (!s[i]) return false;
    if (s[19] || s[4]!='-' || s[7]!='-' || s[10]!=' ' || s[13]!=':' || s[16]!=':') return false;
    if (!digits(s,4,&r.year) || !digits(s+5,2,&r.month) || !digits(s+8,2,&r.day) ||
        !digits(s+11,2,&r.hour) || !digits(s+14,2,&r.minute) || !digits(s+17,2,&r.second)) return false;
    if (!rtc_valid_date(&r)) return false;
    r.valid=true; *t=r; return true;
}
bool rtc_format(const RtcTime *t, char *out, size_t n) {
    if (!t || !out || n<20u || !t->valid || !rtc_valid_date(t)) return false;
    snprintf(out,n,"%04u-%02u-%02u %02u:%02u:%02u",t->year,t->month,t->day,t->hour,t->minute,t->second);
    return true;
}
