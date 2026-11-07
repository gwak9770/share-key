#include "peripherals.h"
#include "config.h"
#if VC_ENABLE_OLED
#include "board.h"
#include <string.h>
#include <stdio.h>
static uint8_t frame[1024], submitted[1024];
static bool submitted_valid;
static bool online,busy;
static unsigned offset;
static const struct { char c; uint16_t rows; } glyphs[]={
{'0',0x7b6f},
{'1',0x2c97},
{'2',0x62a7},
{'3',0x628e},
{'4',0x5bc9},
{'5',0x798e},
{'6',0x39ef},
{'7',0x7292},
{'8',0x7bef},
{'9',0x7bce},
{'A',0x2bed},
{'B',0x6bae},
{'C',0x3923},
{'D',0x6b6e},
{'E',0x79a7},
{'F',0x79a4},
{'G',0x396b},
{'H',0x5bed},
{'I',0x7497},
{'J',0x126a},
{'K',0x5bad},
{'L',0x4927},
{'M',0x5fed},
{'N',0x5ffd},
{'O',0x2b6a},
{'P',0x6ba4},
{'Q',0x2b7b},
{'R',0x6bad},
{'S',0x388e},
{'T',0x7492},
{'U',0x5b6f},
{'V',0x5b6a},
{'W',0x5bfd},
{'X',0x5aad},
{'Y',0x5a92},
{'Z',0x72a7},
{':',0x410},
{'-',0x1c0},
{'_',0x7},
{'/',0x12a4}
};
static bool send(uint8_t *b,uint16_t len) {
    if(HAL_I2C_Master_Transmit(&vc_hi2c1,OLED_ADDRESS<<1,b,len,10)!=HAL_OK) {
        online=false; busy=false; return false;
    }
    return true;
}
void oled_init(void) {
    /* Original SSD1306 init, also reported working on the team's SSD1309
     * JMD2.42 IIC (2026-11-02, one hardware trial). Keep these bytes unchanged. */
    uint8_t cmd[]={0x00,0xAE,0xD5,0x80,0xA8,0x3F,0xD3,0x00,0x40,
        0x8D,0x14,0x20,0x02,0xA1,0xC8,0xDA,0x12,0x81,0x7F,
        0xD9,0xF1,0xDB,0x40,0xA4,0xA6,0xAF};
    submitted_valid=false;
    online=send(cmd,sizeof(cmd));
    memset(frame,0,sizeof(frame)); offset=0; busy=online;
}
#if !VC_OLED_LARGE_TEXT
static void text(unsigned row,const char *s) {
    unsigned x=0;
    while(*s && x+3<128) {
        uint16_t bits=0;
        for(unsigned i=0;i<sizeof(glyphs)/sizeof(glyphs[0]);i++)
            if(glyphs[i].c==*s) { bits=glyphs[i].rows; break; }
        for(unsigned col=0;col<3;col++) {
            uint8_t pixels=0;
            for(unsigned y=0;y<5;y++)
                if(bits&(1u<<(14u-y*3u-col))) pixels|=(uint8_t)(1u<<y);
            frame[row*128+x+col]=pixels;
        }
        x+=4; s++;
    }
}
#else
/* Scale the existing 3x5 glyphs to 9x15 pixels (12-pixel character pitch).
 * Four 16-pixel rows fit in 128x64. No heap allocation or new I2C mode. */
static void large_text(unsigned y0,const char *s) {
    unsigned x0=0;
    while(*s && x0+9u<=128u) {
        uint16_t bits=0;
        for(unsigned i=0;i<sizeof(glyphs)/sizeof(glyphs[0]);i++)
            if(glyphs[i].c==*s) { bits=glyphs[i].rows; break; }
        for(unsigned y=0;y<5u;y++) for(unsigned x=0;x<3u;x++) {
            if(!(bits&(1u<<(14u-y*3u-x)))) continue;
            for(unsigned dy=0;dy<3u;dy++) for(unsigned dx=0;dx<3u;dx++) {
                unsigned px=x0+x*3u+dx, py=y0+y*3u+dy;
                if(py<64u) frame[(py/8u)*128u+px]|=(uint8_t)(1u<<(py%8u));
            }
        }
        x0+=12u; s++;
    }
}
static const char *large_fault(Fault fault) {
    switch(fault) {
    case FAULT_SENSOR: return "SENSOR ERR";
    case FAULT_LINK: return "LINK LOST";
    case FAULT_ESTOP: return "STOP";
    case FAULT_DOOR: return "DOOR OPEN";
    case FAULT_LOCK: return "LOCK LOST";
    case FAULT_SERVO: return "SERVO TIME";
    case FAULT_IO: return "IO ERROR";
    default: return "FAULT";
    }
}
static const char *large_actuation(Result result) {
    switch(result) {
    case RES_NOT_READY: return "NOT READY";
    case RES_NOT_ARMED: return "NOT ARMED";
    case RES_BUSY: return "ACT BUSY";
    case RES_DOOR_OPEN: return "DOOR OPEN";
    case RES_NOT_LOCKED: return "NOT LOCKED";
    case RES_RANGE: return "ACT RANGE";
    case RES_LINK_STALE: return "NO HB";
    default: return "ACT FAULT";
    }
}
#endif
void oled_status(const Controller *c,const RtcTime *t,const VehicleDisplay *d) {
    if(!online||busy) return;
    char s[48]; memset(frame,0,sizeof(frame));
#if VC_OLED_LARGE_TEXT
    (void)t;
    /* 1104: line 1 also shows the debounced door switch so a demo can see
     * why relock did or did not happen: "C DOOR CL" / "C DOOR OP" / "C DOOR --"
     * (not yet qualified). FAULT keeps the old "C FAULT"; the cause is line 4. */
    char m=d->mode?d->mode:APP_POLICY_MODE;
    if(c->fault!=FAULT_NONE) snprintf(s,sizeof(s),"%c FAULT",m);
    else snprintf(s,sizeof(s),"%c%s DOOR %s",m,TEST_BUILD?"T":"",
                  !c->qualified[0]?"--":c->stable.door_closed?"CL":"OP");
    large_text(0,s);
    if(d->policy=='K') large_text(16,"KEY OK");
    else if(d->policy=='N') { snprintf(s,sizeof(s),"KEY NG %.2s",d->reason); large_text(16,s); }
    else if(d->policy=='A') large_text(16,"ALLOW");
    else if(d->policy=='D'||d->policy=='H') {
        snprintf(s,sizeof(s),"%s %.2s",d->policy=='D'?"DENY":"HOLD",d->reason);
        large_text(16,s);
    } else large_text(16,"WAIT");
    if(d->policy=='K'||d->policy=='N') {
        const char *k=d->kid; while(k[0]=='0'&&k[1]) ++k;   /* 00000007 -> 7 */
        if(strlen(k)<=6u) snprintf(s,sizeof(s),"KEY %s",k); else snprintf(s,sizeof(s),"%s",k);
        large_text(32,s);
    }
    else if(d->policy=='-') large_text(32,"LEFT --");
    else if(d->remaining<0) large_text(32,"LEFT INF");
    else { snprintf(s,sizeof(s),"LEFT %d",d->remaining); large_text(32,s); }
    if(c->fault!=FAULT_NONE) large_text(48,large_fault(c->fault));
    else if(c->moving) large_text(48,"MOVING");
    else if(d->actuation_attempted && d->actuation!=RES_OK) large_text(48,large_actuation(d->actuation));
    else if(!control_lock_known(c)) large_text(48,"UNKNOWN");
    else {
        snprintf(s,sizeof(s),"%s%s",control_is_locked(c)?"LOCK":"UNLOCK",
                 control_position_estimated(c)?" EST":"");
        large_text(48,s);
    }
#else
    text(0,TEST_BUILD?"F429 CONTROL / TEST":"F429 CONTROL / AUTH");
    snprintf(s,sizeof(s),"ARM %u READY %u",c->armed,c->ready); text(1,s);
    snprintf(s,sizeof(s),"DOOR %s",c->stable.door_closed?"CLOSED":"OPEN"); text(2,s);
    snprintf(s,sizeof(s),"POS %s %s",control_lock_known(c)?(control_is_locked(c)?"LOCK":"UNLOCK"):"UNKNOWN",control_position_estimated(c)?"EST":"SENSOR"); text(3,s);
    snprintf(s,sizeof(s),"MOTOR %d MOVE %u",c->output.motor,c->moving); text(4,s);
    text(5,control_fault(c->fault));
    snprintf(s,sizeof(s),"AUTH %c WHY %s LEFT %d",d->policy,d->reason,d->remaining); text(6,s);
    if(d->actuation_attempted) { snprintf(s,sizeof(s),"ACT %s",control_result(d->actuation)); text(7,s); }
    else if(t->valid) { snprintf(s,sizeof(s),"%02u:%02u:%02u",t->hour,t->minute,t->second); text(7,s); }
    else text(7,"ACT NONE / RTC INVALID");
#endif
    /* No redundant I2C traffic for unchanged pixels. While busy we keep the
     * in-flight frame intact; the next foreground call renders latest state. */
    if(submitted_valid && !memcmp(frame,submitted,sizeof(frame))) return;
    memcpy(submitted,frame,sizeof(frame)); submitted_valid=true;
    offset=0; busy=true;
}
void oled_service(void) {
    if(!online||!busy) return;
    unsigned page=offset/128, col=offset%128;
    uint8_t cmd[]={0x00,(uint8_t)(0xB0|page),(uint8_t)(col&15),(uint8_t)(0x10|(col>>4))};
    uint8_t data[17]; data[0]=0x40; memcpy(data+1,frame+offset,16);
    if(!send(cmd,sizeof(cmd))||!send(data,sizeof(data))) return;
    offset+=16; if(offset==sizeof(frame)) busy=false;
}
bool oled_online(void) { return online; }


#else
void oled_init(void) {}
void oled_status(const Controller *c,const RtcTime *t,const VehicleDisplay *d) { (void)c; (void)t; (void)d; }
void oled_service(void) {}
bool oled_online(void) { return false; }
#endif
