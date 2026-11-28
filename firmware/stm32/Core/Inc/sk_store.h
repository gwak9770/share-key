/* Portable two-sector snapshot journal. No C structs are written to Flash. */
#ifndef SK_STORE_H
#define SK_STORE_H
#include <stddef.h>
#include <stdint.h>
#define SK_STORE_RECORD_SIZE 256u
#define SK_STORE_IMAGE_SIZE 136u /* VER + 8 explicitly encoded 16-byte key slots + clock floor (11/28) */
typedef struct {
    void *context;
    uint32_t sector_size;
    int (*read)(void *, unsigned, uint32_t, uint8_t *, size_t);
    int (*program)(void *, unsigned, uint32_t, const uint8_t *, size_t);
    int (*erase)(void *, unsigned);
} sk_store_io_t;
typedef struct {
    const sk_store_io_t *io;
    uint32_t sequence, next_offset;
    unsigned bank;
    int barrier_bank;
    int ready;
    uint8_t image[SK_STORE_IMAGE_SIZE];
} sk_store_t;
/* Blank, corrupt, unreadable and barrier-only media return 0 (recovery needed). */
int sk_store_open(sk_store_t *, const sk_store_io_t *, uint8_t *image);
int sk_store_save(sk_store_t *, const uint8_t *image);
/* Authenticated caller only. A durable barrier prevents rollback during reset. */
int sk_store_recover(sk_store_t *, const uint8_t *image);
#endif
