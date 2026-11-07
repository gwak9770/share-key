/* Exercise the production renderer and page transfers through a fake I2C bus.
 * This is not a HAL/peripheral/electrical compatibility test. */
#include "peripherals.h"
#include "config.h"
#include "stm32f4xx_hal.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

I2C_HandleTypeDef vc_hi2c1;
#if VC_ENABLE_OLED
static uint8_t screen[1024];
static unsigned page,column,calls,data_chunks;
static bool fail_next;
static const uint8_t original_init[]={0x00,0xAE,0xD5,0x80,0xA8,0x3F,0xD3,0x00,0x40,
    0x8D,0x14,0x20,0x02,0xA1,0xC8,0xDA,0x12,0x81,0x7F,
    0xD9,0xF1,0xDB,0x40,0xA4,0xA6,0xAF};

HAL_StatusTypeDef HAL_I2C_Master_Transmit(I2C_HandleTypeDef *h,uint16_t address,
    uint8_t *b,uint16_t n,uint32_t timeout) {
    ++calls;
    assert(h==&vc_hi2c1 && address==0x78u && timeout==10u);
    if(fail_next) { fail_next=false; return HAL_ERROR; }
    if(n==sizeof(original_init)) {
        assert(!memcmp(b,original_init,sizeof(original_init)));
    } else if(b[0]==0x00) {
        assert(n==4u && (b[1]&0xf8u)==0xb0u && (b[2]&0xf0u)==0 && (b[3]&0xf0u)==0x10u);
        page=b[1]&7u; column=(b[2]&15u)|((b[3]&15u)<<4);
    } else {
        assert(b[0]==0x40 && n==17u && page<8u && column+16u<=128u);
        memcpy(screen+page*128u+column,b+1,16u); ++data_chunks;
    }
    return HAL_OK;
}

static void flush(void) {
    unsigned before=data_chunks;
    for(unsigned i=0;i<64u;++i) oled_service();
    assert(data_chunks==before || data_chunks==before+64u);
    unsigned after=calls;
    oled_service(); assert(calls==after);
}

#if VC_OLED_LARGE_TEXT
static bool pixel(unsigned x,unsigned y) {
    assert(x<128u && y<64u);
    return (screen[(y/8u)*128u+x] & (1u<<(y%8u)))!=0;
}
/* Golden glyph checks are separate from the renderer and operate on bytes
 * captured on the bus, after page/column addressing has been applied. */
static void glyph_at(unsigned character,unsigned row,uint16_t glyph) {
    for(unsigned y=0;y<15u;++y) for(unsigned x=0;x<12u;++x) {
        bool expected=x<9u && (glyph & (1u<<(14u-(y/3u)*3u-x/3u)))!=0;
        assert(pixel(character*12u+x,row*16u+y)==expected);
    }
}
static void blank_row_tail(unsigned row,unsigned first) {
    for(unsigned y=row*16u;y<row*16u+16u;++y)
        for(unsigned x=first;x<128u;++x) assert(!pixel(x,y));
}
static void snapshot(const char *name) {
    char path[80];
    snprintf(path,sizeof(path),"oled_%c_%s.pbm",APP_POLICY_MODE,name);
    FILE *f=fopen(path,"w"); assert(f);
    fputs("P1\n128 64\n",f);
    for(unsigned y=0;y<64u;++y) {
        for(unsigned x=0;x<128u;++x) fprintf(f,"%d ",pixel(x,y)?1:0);
        fputc('\n',f);
    }
    assert(!fclose(f));
}
#endif
#else
HAL_StatusTypeDef HAL_I2C_Master_Transmit(I2C_HandleTypeDef *h,uint16_t a,
    uint8_t *b,uint16_t n,uint32_t t) {
    (void)h;(void)a;(void)b;(void)n;(void)t;
    assert(!"OLED disabled must not transmit"); return HAL_ERROR;
}
#endif

int main(void) {
    Controller c; control_init(&c,0);
    RtcTime time={0};
    VehicleDisplay d={0}; d.policy='-'; d.remaining=-1; strcpy(d.reason,"--");
    oled_init();
#if VC_ENABLE_OLED
    assert(oled_online()); flush();
    oled_status(&c,&time,&d); flush();
#if VC_OLED_LARGE_TEXT
    glyph_at(0,0,APP_POLICY_MODE=='C'?0x3923u:0x2bedu); /* Mode C/A, not auth result. */
    glyph_at(0,1,0x5bfdu); /* WAIT */
    glyph_at(5,2,0x01c0u); /* LEFT -- */
    glyph_at(0,3,0x5b6fu); /* UNKNOWN */
    glyph_at(2,0,0x6b6eu); glyph_at(7,0,0x01c0u); glyph_at(8,0,0x01c0u); /* DOOR -- before debounce */
    snapshot("wait");
    c.qualified[0]=true; c.stable.door_closed=true;
    oled_status(&c,&time,&d); flush();
    glyph_at(7,0,0x3923u); glyph_at(8,0,0x4927u); blank_row_tail(0,108u); /* DOOR CL */
    c.stable.door_closed=false;
    oled_status(&c,&time,&d); flush();
    glyph_at(7,0,0x2b6au); glyph_at(8,0,0x6ba4u); /* DOOR OP */
    c.stable.door_closed=true;
#endif
    d.policy='A'; d.remaining=APP_POLICY_MODE=='C'?3:-1; strcpy(d.reason,"00");
    d.actuation_attempted=true; d.actuation=RES_OK; c.position=LOCK_UNLOCKED;
    oled_status(&c,&time,&d);
    d.policy='D'; strcpy(d.reason,"05"); d.remaining=0;
    unsigned before=calls;
    oled_status(&c,&time,&d); /* Rendering while busy must not tear the ALLOW frame. */
    assert(calls==before); flush();
#if VC_OLED_LARGE_TEXT
    glyph_at(0,1,0x2bedu); /* ALLOW */
    glyph_at(5,2,APP_POLICY_MODE=='C'?0x628eu:0x7497u); /* 3 / INF */
    glyph_at(0,3,0x5b6fu); /* UNLOCK */
#if !CONTROL_USE_ENDPOINTS
    glyph_at(7,3,0x79a7u); /* EST, not a measured state. */
#endif
    snapshot("allow");
#endif
    /* SYNC refill raster (no authentication request), then revoked zero. */
    d.policy='A'; d.remaining=4; strcpy(d.reason,"00");
    oled_status(&c,&time,&d); flush();
#if VC_OLED_LARGE_TEXT
    glyph_at(5,2,0x5bc9u); /* LEFT 4 */
#endif
    unsigned stable_calls=calls;
    for(unsigned i=0;i<100u;++i) { oled_status(&c,&time,&d); oled_service(); }
    assert(calls==stable_calls);
    d.policy='D'; d.remaining=0; strcpy(d.reason,"03");
    oled_status(&c,&time,&d); flush();
#if VC_OLED_LARGE_TEXT
    glyph_at(0,1,0x6b6eu); glyph_at(6,1,0x628eu); /* DENY 03 */
    glyph_at(5,2,0x7b6fu); /* LEFT 0 */
#endif
    strcpy(d.reason,"05");
    c.position=LOCK_LOCKED; d.actuation_attempted=false;
    oled_status(&c,&time,&d); flush();
#if VC_OLED_LARGE_TEXT
    glyph_at(0,1,0x6b6eu); glyph_at(5,1,0x7b6fu); glyph_at(6,1,0x798eu); /* DENY 05 */
    glyph_at(5,2,0x7b6fu); /* LEFT 0 */
    glyph_at(0,3,0x4927u); /* LOCK */
    snapshot("deny");
    d.policy='H'; strcpy(d.reason,"07");
    oled_status(&c,&time,&d); flush(); glyph_at(0,1,0x5bedu); /* HOLD */
    c.moving=true; oled_status(&c,&time,&d); flush();
    glyph_at(0,3,0x5fedu); /* MOVING */
    c.moving=false; c.fault=FAULT_LINK;
    oled_status(&c,&time,&d); flush();
    glyph_at(2,0,0x79a4u); /* C/A FAULT */
    glyph_at(0,3,0x4927u); /* LINK LOST */
    snapshot("fault");
    c.fault=FAULT_NONE; d.policy='A'; d.actuation_attempted=true; d.actuation=RES_LINK_STALE;
    oled_status(&c,&time,&d); flush(); glyph_at(0,3,0x5ffdu); /* NO HB despite ALLOW */
    d.actuation=RES_OK; d.remaining=255; /* Longest supported finite display value. */
    oled_status(&c,&time,&d); flush();
    for(unsigned row=0;row<4u;++row) blank_row_tail(row,120u);
    for(unsigned y=15;y<64u;y+=16u) for(unsigned x=0;x<128u;++x) assert(!pixel(x,y));
    d.policy='K'; strcpy(d.reason,"00"); strcpy(d.kid,"00000007"); d.actuation_attempted=false;
    oled_status(&c,&time,&d); flush();
    glyph_at(0,1,0x5badu); glyph_at(4,1,0x2b6au); /* KEY OK */
    glyph_at(0,2,0x5badu); glyph_at(4,2,0x7292u); blank_row_tail(2,60u); /* KEY 7 */
    snapshot("keyok");
    d.policy='N'; strcpy(d.reason,"01");
    oled_status(&c,&time,&d); flush();
    glyph_at(4,1,0x5ffdu); glyph_at(8,1,0x2c97u); /* KEY NG 01 */
    strcpy(d.kid,"1234ABCD"); oled_status(&c,&time,&d); flush();
    glyph_at(0,2,0x2c97u); glyph_at(7,2,0x6b6eu); /* long KID shown without prefix */
#endif
    /* Stable status must not transmit again; changed status must transmit. */
    before=calls; oled_status(&c,&time,&d); oled_service(); assert(calls==before);
    d.policy='D'; strcpy(d.reason,"03"); d.remaining=0;
    oled_status(&c,&time,&d); fail_next=true; oled_service();
    assert(!oled_online()); before=calls;
    oled_service(); oled_status(&c,&time,&d); assert(calls==before);
    oled_init(); assert(oled_online()); flush();
    oled_status(&c,&time,&d); flush();
    printf("PASS OLED mode=%c large=%d: init bytes, 64 bounded chunks, busy frame, error/reinit",
           APP_POLICY_MODE,VC_OLED_LARGE_TEXT);
#if VC_OLED_LARGE_TEXT
    puts(", WAIT/ALLOW/DENY/HOLD, remaining, estimated/unknown/moving/fault/NO HB raster");
#else
    puts(", legacy diagnostic view");
#endif
#else
    oled_status(&c,&time,&d); oled_service(); assert(!oled_online());
    puts("PASS OLED disabled: no I2C");
#endif
    return 0;
}
