/* F429ZI 2MiB, last two 128KiB sectors. Board verification is still required. */
#include "sk_flash_stm32.h"
#include "stm32f4xx_hal.h"
#include "vehicle_app.h"
#include <string.h>

#define STORE_START 0x081C0000u
#define STORE_SIZE  0x00020000u
extern uint8_t _sidata, _sdata, _edata;
static uint32_t address(unsigned bank,uint32_t offset) { return STORE_START+bank*STORE_SIZE+offset; }
static int layout_ok(void) {
    /* Blocking HAL erases still pause the foreground. Also keep every loadable
     * byte in bank 1 so interrupts/constants cannot stall on a busy bank 2. */
    uintptr_t load_end=(uintptr_t)&_sidata+((uintptr_t)&_edata-(uintptr_t)&_sdata);
    return load_end<=0x08100000u && *(const uint16_t *)FLASHSIZE_BASE==2048u;
}
static int read_flash(void *ctx,unsigned bank,uint32_t off,uint8_t *out,size_t n) {
    (void)ctx;
    if (!layout_ok() || bank>1 || off>STORE_SIZE || n>STORE_SIZE-off) return 0;
    memcpy(out,(const void *)(uintptr_t)address(bank,off),n); return 1;
}
static void reset_cache(void) {
    __HAL_FLASH_DATA_CACHE_DISABLE(); __HAL_FLASH_DATA_CACHE_RESET(); __HAL_FLASH_DATA_CACHE_ENABLE();
    __DSB(); __ISB();
}
static int program_flash(void *ctx,unsigned bank,uint32_t off,const uint8_t *data,size_t n) {
    (void)ctx;
    if (!layout_ok() || bank>1 || off>STORE_SIZE || n>STORE_SIZE-off || (off&3u) || (n&3u)) return 0;
    if (HAL_FLASH_Unlock()!=HAL_OK) return 0;
    int ok=1;
    for (size_t i=0;i<n;i+=4) {
        uint32_t value; memcpy(&value,data+i,4);
        if (HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD,address(bank,off+(uint32_t)i),value)!=HAL_OK) { ok=0; break; }
    }
    if (HAL_FLASH_Lock()!=HAL_OK) ok=0;
    reset_cache(); return ok;
}
static int erase_flash(void *ctx,unsigned bank) {
    (void)ctx;
    const Controller *c=vehicle_app_controller();
    if (!layout_ok() || bank>1 || c->moving || c->output.motor!=0) return 0;
    FLASH_EraseInitTypeDef erase={0}; uint32_t error=0;
    erase.TypeErase=FLASH_TYPEERASE_SECTORS;
    erase.Sector=bank ? FLASH_SECTOR_23 : FLASH_SECTOR_22;
    erase.NbSectors=1; erase.VoltageRange=VOLTAGE_RANGE_3;
    if (HAL_FLASH_Unlock()!=HAL_OK) return 0;
    int ok=HAL_FLASHEx_Erase(&erase,&error)==HAL_OK;
    if (HAL_FLASH_Lock()!=HAL_OK) ok=0;
    reset_cache(); return ok;
}
const sk_store_io_t *sk_flash_stm32_io(void) {
    static const sk_store_io_t io={NULL,STORE_SIZE,read_flash,program_flash,erase_flash};
    return &io;
}
