#include "peripherals.h"
#include "config.h"
#include <string.h>
#if VC_ENABLE_RTC
#include "board.h"
#include <string.h>
static unsigned dec(uint8_t b) { return (b>>4)*10u+(b&15u); }
static bool bcd(uint8_t b) { return (b&15u)<10u && (b>>4)<10u; }
static uint8_t enc(unsigned n) { return (uint8_t)(((n/10u)<<4)|(n%10u)); }
bool rtc_valid_date(const RtcTime *t) {
    static const unsigned days[]={31,28,31,30,31,30,31,31,30,31,30,31};
    if(t->year<2000||t->year>2099||t->month<1||t->month>12||
       t->hour>23||t->minute>59||t->second>59) return false;
    unsigned max=days[t->month-1]+(t->month==2 && t->year%4==0);
    return t->day>=1 && t->day<=max;
}
bool rtc_read(RtcTime *t) {
    uint8_t r[7],status;
    memset(t,0,sizeof(*t));
    if(HAL_I2C_Mem_Read(&vc_hi2c1,RTC_ADDRESS<<1,0,I2C_MEMADD_SIZE_8BIT,r,7,10)!=HAL_OK ||
       HAL_I2C_Mem_Read(&vc_hi2c1,RTC_ADDRESS<<1,0x0F,I2C_MEMADD_SIZE_8BIT,&status,1,10)!=HAL_OK)
        return false;
    if((status&0x80)||(r[5]&0x80)||!bcd(r[0])||!bcd(r[1])||
       !bcd(r[4])||!bcd(r[5]&0x1F)||!bcd(r[6])) return false;
    t->second=dec(r[0]); t->minute=dec(r[1]);
    if(r[2]&0x40) {
        uint8_t h=r[2]&0x1F;
        if(!bcd(h)||dec(h)<1||dec(h)>12) return false;
        t->hour=dec(h)%12+((r[2]&0x20)?12u:0u);
    } else {
        if(!bcd(r[2]&0x3F)) return false;
        t->hour=dec(r[2]&0x3F);
    }
    t->day=dec(r[4]); t->month=dec(r[5]&0x1F); t->year=2000+dec(r[6]);
    t->valid=rtc_valid_date(t); return t->valid;
}
bool rtc_set(const RtcTime *t) {
    if(!rtc_valid_date(t)) return false;
    /* Compute weekday, DS3231 1=Sunday. Valid for 2000..2099. */
    unsigned days=0;
    for(unsigned y=2000;y<t->year;y++) days+=365+(y%4==0);
    static const unsigned md[]={31,28,31,30,31,30,31,31,30,31,30,31};
    for(unsigned m=1;m<t->month;m++) days+=md[m-1]+(m==2&&t->year%4==0);
    days+=t->day-1;
    uint8_t r[]={enc(t->second),enc(t->minute),enc(t->hour),
        (uint8_t)((days+6)%7+1),enc(t->day),enc(t->month),enc(t->year-2000)};
    uint8_t status;
    if(HAL_I2C_Mem_Write(&vc_hi2c1,RTC_ADDRESS<<1,0,I2C_MEMADD_SIZE_8BIT,r,7,10)!=HAL_OK)
        return false;
    if(HAL_I2C_Mem_Read(&vc_hi2c1,RTC_ADDRESS<<1,0x0F,I2C_MEMADD_SIZE_8BIT,&status,1,10)!=HAL_OK)
        return false;
    status&=0x7Fu;
    return HAL_I2C_Mem_Write(&vc_hi2c1,RTC_ADDRESS<<1,0x0F,I2C_MEMADD_SIZE_8BIT,&status,1,10)==HAL_OK;
}



#else
bool rtc_valid_date(const RtcTime *t) { (void)t; return false; }
bool rtc_read(RtcTime *t) { memset(t,0,sizeof(*t)); return false; }
bool rtc_set(const RtcTime *t) { (void)t; return false; }
#endif
