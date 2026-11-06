/* Standalone F429ZI link-check layout. Keep the actual CubeIDE-generated linker
 * in the team's project. This file does not reserve a Flash persistence journal.
 * SRAM1+SRAM2+SRAM3 = 192 KiB at 0x20000000; CCM is separate, not contiguous.
 */
ENTRY(Reset_Handler)
MEMORY {
    FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 2048K
    RAM (xrw)  : ORIGIN = 0x20000000, LENGTH = 192K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
_Min_Heap_Size = 0x400;
_Min_Stack_Size = 0x1000;
PHDRS {
    flash PT_LOAD FLAGS(5); /* readable, executable */
    ram_init PT_LOAD FLAGS(6); /* initialized data: load image in Flash */
    ram_zero PT_LOAD FLAGS(6); /* zero/NOLOAD data in SRAM */
}
SECTIONS {
    .isr_vector : { . = ALIGN(4); KEEP(*(.isr_vector)) . = ALIGN(4); } > FLASH :flash
    .text : {
        . = ALIGN(4); *(.text .text*) *(.glue_7 .glue_7t) *(.eh_frame)
        KEEP(*(.init)) KEEP(*(.fini)) . = ALIGN(4); _etext = .;
    } > FLASH :flash
    .rodata : { . = ALIGN(4); *(.rodata .rodata*) . = ALIGN(4); } > FLASH :flash
    .ARM.extab : { *(.ARM.extab* .gnu.linkonce.armextab.*) } > FLASH :flash
    .ARM.exidx : {
        __exidx_start = .; *(.ARM.exidx*) __exidx_end = .;
    } > FLASH :flash
    .preinit_array : {
        PROVIDE_HIDDEN(__preinit_array_start = .); KEEP(*(.preinit_array*))
        PROVIDE_HIDDEN(__preinit_array_end = .);
    } > FLASH :flash
    .init_array : {
        PROVIDE_HIDDEN(__init_array_start = .);
        KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array*))
        PROVIDE_HIDDEN(__init_array_end = .);
    } > FLASH :flash
    .fini_array : {
        PROVIDE_HIDDEN(__fini_array_start = .);
        KEEP(*(SORT(.fini_array.*))) KEEP(*(.fini_array*))
        PROVIDE_HIDDEN(__fini_array_end = .);
    } > FLASH :flash
    _sidata = LOADADDR(.data);
    .data : {
        . = ALIGN(4); _sdata = .; *(.data .data*) . = ALIGN(4); _edata = .;
    } > RAM AT> FLASH :ram_init
    .bss (NOLOAD) : AT(ADDR(.bss)) {
        . = ALIGN(4); _sbss = .; __bss_start__ = .; *(.bss .bss*) *(COMMON)
        . = ALIGN(4); _ebss = .; __bss_end__ = .;
    } > RAM :ram_zero
    ._user_heap_stack (NOLOAD) : {
        . = ALIGN(8); PROVIDE(end = .); PROVIDE(_end = .); _heap_start = .;
        . += _Min_Heap_Size; _heap_end = .;
        . += _Min_Stack_Size; . = ALIGN(8);
    } > RAM :ram_zero
    .ARM.attributes 0 : { *(.ARM.attributes) } :NONE
}
