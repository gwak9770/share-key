#include "sk_store.h"
#include <string.h>
#include <limits.h>

static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3];
}
static void put32(uint8_t *p, uint32_t v) {
    p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v;
}
static uint32_t crc32(const uint8_t *p, size_t n) {
    uint32_t c=UINT32_MAX;
    while (n--) {
        c ^= *p++;
        for (unsigned i=0; i<8; ++i) c=(c>>1)^((0u-(c&1u))&0xEDB88320u);
    }
    return ~c;
}
static int blank(const uint8_t *p, size_t n) {
    while (n--) if (*p++ != 255u) return 0;
    return 1;
}
static int usable(const sk_store_io_t *io) {
    return io && io->read && io->program && io->erase &&
        io->sector_size >= 2u*SK_STORE_RECORD_SIZE && io->sector_size%SK_STORE_RECORD_SIZE==0;
}
/* Scan both banks; any committed damage is fail-closed, never silently rolled back.
 * Incomplete bodies with erased commit word have never authorized an action. */
static int scan(sk_store_t *s, unsigned *damaged_bank) {
    uint32_t best=0, barrier=0, highest=0;
    int bad=0, found=0;
    uint8_t r[SK_STORE_RECORD_SIZE];
    s->ready=0; s->next_offset=0; s->barrier_bank=-1;
    for (unsigned b=0; b<2; ++b) {
        uint32_t end=0;
        for (uint32_t off=0; off<s->io->sector_size; off+=sizeof r) {
            if (!s->io->read(s->io->context,b,off,r,sizeof r)) return -1;
            if (blank(r,sizeof r)) continue;
            end=off+sizeof r;
            uint32_t commit=get32(r+252);
            if (commit==UINT32_MAX) continue;
            if (commit!=0 || memcmp(r,"SKJ1",4) || r[4]!=1 || r[5]>1 ||
                get32(r+12)!=0x0000CAFEu || get32(r+248)!=crc32(r,248) || get32(r+8)==0) {
                bad=1; *damaged_bank=b; continue;
            }
            uint32_t seq=get32(r+8);
            if (seq>highest) highest=seq;
            if (r[5]==1) { if (seq>barrier) { barrier=seq; s->barrier_bank=(int)b; } continue; }
            if (found && seq==best) { bad=1; *damaged_bank=b; }
            if (seq>best) {
                best=seq; s->bank=b; found=1;
                memcpy(s->image,r+16,SK_STORE_IMAGE_SIZE);
            }
        }
        if (found && s->bank==b) s->next_offset=end;
    }
    s->sequence=highest;
    if (!bad) *damaged_bank=found ? s->bank : 0u;
    s->ready=!bad && found && best>barrier;
    return s->ready;
}
int sk_store_open(sk_store_t *s, const sk_store_io_t *io, uint8_t *image) {
    memset(s,0,sizeof *s); s->io=io;
    unsigned damaged=0;
    if (!usable(io) || scan(s,&damaged)!=1) return 0;
    memcpy(image,s->image,SK_STORE_IMAGE_SIZE); return 1;
}
static int erase_checked(sk_store_t *s, unsigned b) {
    uint8_t r[SK_STORE_RECORD_SIZE];
    if (!s->io->erase(s->io->context,b)) return 0;
    for (uint32_t off=0; off<s->io->sector_size; off+=sizeof r)
        if (!s->io->read(s->io->context,b,off,r,sizeof r) || !blank(r,sizeof r)) return 0;
    return 1;
}
static int write_record(sk_store_t *s,unsigned b,uint32_t off,const uint8_t *image,int barrier) {
    uint8_t r[SK_STORE_RECORD_SIZE], check[SK_STORE_RECORD_SIZE];
    if (s->sequence==UINT32_MAX) return 0;
    memset(r,255,sizeof r); memcpy(r,"SKJ1",4); r[4]=1; r[5]=(uint8_t)barrier;
    put32(r+8,++s->sequence); put32(r+12,0x0000CAFEu);
    if (image) memcpy(r+16,image,SK_STORE_IMAGE_SIZE);
    put32(r+248,crc32(r,248));
    if (!s->io->program(s->io->context,b,off,r,252) ||
        !s->io->read(s->io->context,b,off,check,sizeof check) || memcmp(r,check,sizeof r)) return 0;
    put32(r+252,0);
    if (!s->io->program(s->io->context,b,off+252,r+252,4) ||
        !s->io->read(s->io->context,b,off,check,sizeof check) || memcmp(r,check,sizeof r)) return 0;
    return 1;
}
int sk_store_save(sk_store_t *s, const uint8_t *image) {
    if (!s->ready) return 0;
    if (!memcmp(image,s->image,SK_STORE_IMAGE_SIZE)) return 1;
    unsigned b=s->bank; uint32_t off=s->next_offset;
    s->ready=0;
    if (off>=s->io->sector_size) { b=1u-b; off=0; if (!erase_checked(s,b)) return 0; }
    if (!write_record(s,b,off,image,0)) return 0;
    s->bank=b; s->next_offset=off+SK_STORE_RECORD_SIZE;
    memcpy(s->image,image,SK_STORE_IMAGE_SIZE); s->ready=1; return 1;
}
int sk_store_recover(sk_store_t *s, const uint8_t *image) {
    if (!usable(s->io)) return 0;
    unsigned damaged=0;
    if (scan(s,&damaged)<0) return 0;
    s->ready=0;
    if (s->sequence>UINT32_MAX-2u) return 0;
    if (s->barrier_bank>=0) {
        /* A retry must retain an existing barrier until a replacement snapshot
         * is committed. Erasing the barrier first could revive an old record. */
        unsigned locked=(unsigned)s->barrier_bank;
        unsigned dest=1u-locked;
        if (!erase_checked(s,dest) || !write_record(s,dest,0,image,0) ||
            !erase_checked(s,locked)) return 0;
        s->bank=dest; s->next_offset=SK_STORE_RECORD_SIZE;
        memcpy(s->image,image,SK_STORE_IMAGE_SIZE); s->ready=1; return 1;
    }
    /* Keep damaged evidence until a committed lock barrier exists elsewhere.
     * Then erase the old bank and commit the authorized replacement. A reset
     * at any intermediate step cannot revive an older normal snapshot. */
    unsigned barrier_bank=1u-damaged;
    if (!erase_checked(s,barrier_bank) || !write_record(s,barrier_bank,0,NULL,1) ||
        !erase_checked(s,damaged) || !write_record(s,damaged,0,image,0)) return 0;
    s->bank=damaged; s->next_offset=SK_STORE_RECORD_SIZE;
    memcpy(s->image,image,SK_STORE_IMAGE_SIZE); s->ready=1; return 1;
}
