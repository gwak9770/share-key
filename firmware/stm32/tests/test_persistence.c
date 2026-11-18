/* Production C policy/journal with 1->0 fake Flash; shared with Python ctypes tests. */
#include "sharekey.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API
#endif
#define SECTOR 1024u
static uint8_t media[2][SECTOR];
static char reply[600];
static int budget=-1, actions, reads_fail;
static unsigned offline_logs;
static uint32_t now_ms, rng=1;
static int step(void) { if (budget==0) return 0; if (budget>0) --budget; return 1; }
static int rd(void *c,unsigned b,uint32_t o,uint8_t *p,size_t n) {
    (void)c;
    if (reads_fail || b>1 || o>SECTOR || n>SECTOR-o) return 0;
    memcpy(p,media[b]+o,n); return 1;
}
static int wr(void *c,unsigned b,uint32_t o,const uint8_t *p,size_t n) {
    (void)c;
    if (b>1 || o>SECTOR || n>SECTOR-o || (o&3u) || (n&3u)) return 0;
    for (size_t i=0;i<n;i+=4) {
        if (!step()) return 0;
        for (size_t j=0;j<4;++j) {
            if ((media[b][o+i+j]&p[i+j])!=p[i+j]) return 0;
            media[b][o+i+j]&=p[i+j];
        }
    }
    return 1;
}
static int er(void *c,unsigned b) {
    (void)c; if (b>1) return 0;
    for (unsigned i=0;i<SECTOR;i+=4) {
        if (!step()) return 0;
        memset(media[b]+i,255,4);
    }
    return 1;
}
static const sk_store_io_t io={NULL,SECTOR,rd,wr,er};
void sk_port_send_line(const char *s) { assert(strlen(s)<sizeof reply); strcpy(reply,s); }
void sk_port_log(const char *s) { if (!strcmp(s,"no server response -> OFFLINE")) ++offline_logs; }
uint32_t sk_port_millis(void) { return now_ms; }
uint32_t sk_port_unix_time(void) { return 100u; }
void sk_port_random(uint8_t *p,size_t n) {
    while (n--) { rng=rng*1664525u+1013904223u; *p++=(uint8_t)(rng>>24); }
}
void sk_port_actuate(int cmd,int remaining) {
    sk_store_t check; uint8_t image[SK_STORE_IMAGE_SIZE];
    assert(sk_store_open(&check,&io,image));
    if (cmd!=3 && remaining>=0) {
        int match=0;
        for (unsigned i=0;i<8;++i) if (image[4+16*i+13] && image[4+16*i+9]==remaining) match=1;
        assert(match);
    }
    ++actions;
}
void sk_port_deny(int cmd,const char *why) { (void)cmd; (void)why; }
API void bridge_boot(void) { sk_use_storage(&io); sk_init('C'); reply[0]=0; }
API void bridge_reset(void) {
    memset(media,255,sizeof media); budget=-1; reads_fail=actions=0; offline_logs=0; now_ms=0; bridge_boot();
}
API const char *bridge_send(const char *s) {
    char line[600]; assert(strlen(s)<sizeof line); strcpy(line,s); reply[0]=0;
    sk_handle_line(line); return reply;
}
API const char *bridge_sync(void) { reply[0]=0; now_ms+=2000; sk_poll(); return reply; }
API uint8_t *bridge_media(void) { return &media[0][0]; }
API void bridge_cut(int n) { budget=n; }
API void bridge_read_fail(int n) { reads_fail=n; }
API int bridge_actions(void) { return actions; }
API int bridge_locked(void) { return sk_recovery_needed(); }
API int bridge_online(void) { return sk_online_state(); }
API unsigned bridge_misses(void) { return sk_sync_misses(); }
API unsigned bridge_offline_logs(void) { return offline_logs; }
API const char *bridge_advance(uint32_t delta) { reply[0]=0; now_ms+=delta; sk_poll(); return reply; }
API void bridge_clock(uint32_t value) { now_ms=value; }

#ifndef SK_BRIDGE_LIBRARY
static void hex(const uint8_t *p,size_t n,char *s) {
    for (size_t i=0;i<n;++i) sprintf(s+2*i,"%02X",p[i]);
}
int main(void) {
    char noncehex[33],taghex[65],line[512]; uint8_t nonce[16],tag[32],ki[32];
    bridge_reset(); assert(bridge_locked());
    const char *r=bridge_send("00|RBEGIN"); assert(!strncmp(r,"00|RCHAL|0000CAFE|",18));
    strcpy(noncehex,r+18);
    for (unsigned i=0;i<16;++i) { unsigned v; sscanf(noncehex+2*i,"%2x",&v); nonce[i]=(uint8_t)v; }
    sk_recovery_tag(1,nonce,7,0xFFFFFFFFu,4,2,3,tag); hex(tag,32,taghex);
    snprintf(line,sizeof line,"00|RECOVER|0000CAFE|%s|00000001|00000007|FFFFFFFF|04|02|03|%s",noncehex,taghex);
    assert(!strcmp(bridge_send(line),"00|RECOVERED|00000007"));
    sk_derive(7,ki);
    for (unsigned attempt=0;attempt<4;++attempt) {
        r=bridge_send("00|REQ|00000007|01"); assert(!strncmp(r,"00|CHAL|00000007|",17));
        strcpy(noncehex,r+17);
        for (unsigned i=0;i<16;++i) { unsigned v; sscanf(noncehex+2*i,"%2x",&v); nonce[i]=(uint8_t)v; }
        sk_auth_tag(ki,7,1,nonce,tag); hex(tag,32,taghex);
        snprintf(line,sizeof line,"00|RESP|00000007|01|%s|%s",noncehex,taghex);
        assert(strstr(bridge_send(line),"|A|00|"));
        bridge_boot(); assert(!bridge_locked());
    }
    for (unsigned reboot=0;reboot<30;++reboot) {
        sk_key_view_t v; bridge_boot(); assert(sk_get_key_view(7,&v)); assert(v.remaining==0);
    }
    assert(actions==4);
    puts("PASS persistence: 30 reboot restores, count never increased; save verified before actuation");
    return 0;
}
#endif
