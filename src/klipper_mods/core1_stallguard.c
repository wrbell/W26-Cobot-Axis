/*
 * W26 Cobot Axis -- Core1 StallGuard DIAG Pin Monitor
 *
 * Runs on the RP2040's second Cortex-M0+ core, which Klipper leaves
 * idle in the bootrom's WFE loop. Monitors the TMC2209 DIAG pin
 * (active-low when StallGuard threshold is crossed) and updates
 * shared SRAM so core0 can report stall events to the host.
 *
 * Why core1?
 *   - DIAG asserts in microseconds; Klipper UART polls at 4 Hz (250ms)
 *   - A blocked pump can damage workpiece/pump in <250ms at high rates
 *   - Core1 gives hardware-speed detection with zero Klipper impact
 *
 * Why not TMC UART from core1?
 *   - TMC2209 uses half-duplex single-wire UART owned by core0/Klipper
 *   - Two cores on the same bus risks corruption
 *   - DIAG pin provides the same stall signal without bus access
 *
 * Pin: gpio16 (active-low, directly from TMC2209 DIAG output)
 *      Requires DIAG jumper installed on SKR Pico E-stepper header
 *
 * Reference: RP2040 Datasheet Sections 2.3.1 (SIO), 2.19 (GPIO)
 *            TMC2209 Datasheet Section 11 (DIAG output)
 */

#include <stdint.h>
#include "stallguard_shared.h"

/* RP2040 bare-metal register addresses */
#define IO_BANK0_BASE       0x40014000
#define PADS_BANK0_BASE     0x4001C000
#define SIO_GPIO_IN         (*(volatile uint32_t *)(SIO_BASE + 0x004))
#define SIO_GPIO_OE_CLR     (*(volatile uint32_t *)(SIO_BASE + 0x028))
#define TIMER_TIMERAWL      (*(volatile uint32_t *)0x40054028)

/* GPIO function select: SIO = function 5 */
#define GPIO_FUNC_SIO       5

/* DIAG pin configuration */
#define DIAG_PIN            16
#define DIAG_PIN_MASK       (1u << DIAG_PIN)

/* Debounce: 16 consecutive matching reads (~1.3us at 125 MHz) */
#define DEBOUNCE_COUNT      16

/* Core1 stack: 2KB in .bss, aligned to 32 bytes (Cortex-M0+ requirement) */
static uint32_t core1_stack[512] __attribute__((aligned(32)));

/* Shared SRAM instance -- core0 accesses this via extern declaration */
stallguard_shared_t sg_shared;

/* ------------------------------------------------------------------ */
/* GPIO bare-metal setup                                               */
/* ------------------------------------------------------------------ */

/*
 * Configure gpio16 as SIO input with pull-up.
 * DIAG is active-low: high = no stall, low = stall detected.
 */
static void diag_pin_init(void)
{
    /* Set pad: input enable, pull-up, no pull-down */
    volatile uint32_t *pad_ctrl = (volatile uint32_t *)(
        PADS_BANK0_BASE + 0x04 + (DIAG_PIN * 4)
    );
    /*
     * Pad control bits:
     *   bit 6: IE (input enable) = 1
     *   bit 3: PUE (pull-up enable) = 1
     *   bit 2: PDE (pull-down enable) = 0
     *   bit 1: SCHMITT = 1
     *   bit 0: SLEWFAST = 0
     */
    *pad_ctrl = (1u << 6) | (1u << 3) | (1u << 1);

    /* Set GPIO function to SIO (function 5) */
    volatile uint32_t *gpio_ctrl = (volatile uint32_t *)(
        IO_BANK0_BASE + 0x04 + (DIAG_PIN * 8)
    );
    *gpio_ctrl = GPIO_FUNC_SIO;

    /* Ensure output is disabled (input only) */
    SIO_GPIO_OE_CLR = DIAG_PIN_MASK;
}

/* ------------------------------------------------------------------ */
/* Core1 main loop                                                     */
/* ------------------------------------------------------------------ */

/*
 * Read the DIAG pin with debouncing.
 * Returns 1 if stalled (DIAG low for DEBOUNCE_COUNT consecutive reads).
 * Returns 0 if not stalled (DIAG high for DEBOUNCE_COUNT consecutive reads).
 * Returns -1 if bouncing (no stable state).
 */
static int diag_read_debounced(void)
{
    uint32_t low_count = 0;
    uint32_t high_count = 0;

    for (int i = 0; i < DEBOUNCE_COUNT; i++) {
        if (SIO_GPIO_IN & DIAG_PIN_MASK)
            high_count++;
        else
            low_count++;
    }

    if (low_count == DEBOUNCE_COUNT)
        return 1;   /* stalled: DIAG is active-low */
    if (high_count == DEBOUNCE_COUNT)
        return 0;   /* not stalled */
    return -1;      /* bouncing */
}

/*
 * Core1 entry point: tight polling loop for DIAG pin monitoring.
 *
 * Detects rising and falling edges on the DIAG pin (after debounce)
 * and updates the shared SRAM struct under spinlock protection.
 */
static void core1_stallguard_main(void)
{
    diag_pin_init();

    /* Initialize shared state */
    sg_lock_acquire();
    sg_shared.stall_active = 0;
    sg_shared.stall_count = 0;
    sg_shared.last_stall_ticks = 0;
    sg_shared.clear_request = 0;
    sg_lock_release();

    uint8_t prev_stall = 0;

    for (;;) {
        int state = diag_read_debounced();

        if (state < 0)
            continue;  /* bouncing -- skip */

        uint8_t stalled = (uint8_t)state;

        /* Detect rising edge: not stalled -> stalled */
        if (stalled && !prev_stall) {
            sg_lock_acquire();
            sg_shared.stall_active = 1;
            sg_shared.stall_count++;
            sg_shared.last_stall_ticks = TIMER_TIMERAWL;
            sg_lock_release();
        }
        /* Detect falling edge: stalled -> not stalled */
        else if (!stalled && prev_stall) {
            sg_lock_acquire();
            sg_shared.stall_active = 0;
            sg_lock_release();
        }

        /* Check for clear request from core0 */
        if (sg_shared.clear_request) {
            sg_lock_acquire();
            sg_shared.stall_count = 0;
            sg_shared.clear_request = 0;
            sg_lock_release();
        }

        prev_stall = stalled;
    }
}

/* ------------------------------------------------------------------ */
/* Core1 launch protocol                                               */
/* ------------------------------------------------------------------ */

/*
 * RP2040 SIO FIFO registers for inter-core communication.
 * Used during the core1 launch handshake.
 */
#define SIO_FIFO_ST     (*(volatile uint32_t *)(SIO_BASE + 0x050))
#define SIO_FIFO_WR     (*(volatile uint32_t *)(SIO_BASE + 0x054))
#define SIO_FIFO_RD     (*(volatile uint32_t *)(SIO_BASE + 0x058))
#define SIO_FIFO_ST_VLD (1u << 0)  /* FIFO has data to read */
#define SIO_FIFO_ST_RDY (1u << 1)  /* FIFO has room to write */

/* Drain any stale data from the inter-core FIFO */
static void fifo_drain(void)
{
    /* SEV to ensure core1 isn't stuck in WFE */
    __asm volatile ("sev");
    while (SIO_FIFO_ST & SIO_FIFO_ST_VLD)
        (void)SIO_FIFO_RD;
}

/* Blocking write to the inter-core FIFO */
static void fifo_push(uint32_t val)
{
    while (!(SIO_FIFO_ST & SIO_FIFO_ST_RDY))
        ;  /* wait for space */
    SIO_FIFO_WR = val;
    __asm volatile ("sev");
}

/* Blocking read from the inter-core FIFO */
static uint32_t fifo_pop(void)
{
    while (!(SIO_FIFO_ST & SIO_FIFO_ST_VLD))
        __asm volatile ("wfe");
    return SIO_FIFO_RD;
}

/*
 * Launch core1 from the bootrom idle state.
 *
 * The RP2040 bootrom puts core1 into a WFE loop waiting for a
 * specific FIFO handshake sequence:
 *   1. Send 0, 0, 1, vector_table, stack_pointer, entry_point
 *   2. Core1 responds with 0 after each pair, then echoes entry
 *
 * This function must be called from core0 before sched_main().
 */
void core1_launch(void)
{
    extern uint32_t _vector_table[];  /* from Klipper's linker script */

    uint32_t entry = (uint32_t)core1_stallguard_main;
    uint32_t sp = (uint32_t)&core1_stack[sizeof(core1_stack) / sizeof(uint32_t)];
    uint32_t vtor = (uint32_t)_vector_table;

    /* Sequence values to send to bootrom */
    uint32_t seq[] = { 0, 0, 1, vtor, sp, entry };
    uint32_t seq_len = sizeof(seq) / sizeof(seq[0]);

    uint32_t response;
    int tries = 0;

    do {
        fifo_drain();

        for (uint32_t i = 0; i < seq_len; i++) {
            fifo_push(seq[i]);
            response = fifo_pop();

            /* After items 0 and 1 (the two zeros), expect 0 back.
             * After items 2-5, the last pop should echo the entry point. */
            if (i < 2 && response != 0) {
                /* Handshake failed at early stage -- retry */
                break;
            }
        }

        tries++;
    } while (response != entry && tries < 10);
}
