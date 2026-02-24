/*
 * W26 Cobot Axis -- Shared memory between RP2040 cores for StallGuard
 *
 * Core0 (Klipper) and Core1 (DIAG pin monitor) communicate through
 * a shared struct in SRAM, protected by hardware spinlock #16.
 *
 * The RP2040 SIO spinlock registers provide atomic mutual exclusion
 * between cores without disabling interrupts on either side.
 *
 * Reference: RP2040 Datasheet, Section 2.3.1.3 (Spinlocks)
 */

#ifndef STALLGUARD_SHARED_H
#define STALLGUARD_SHARED_H

#include <stdint.h>

/* RP2040 SIO base address and spinlock register offsets */
#define SIO_BASE            0xD0000000
#define SIO_SPINLOCK_BASE   (SIO_BASE + 0x100)
#define SG_SPINLOCK_NUM     16
#define SG_SPINLOCK_ADDR    (SIO_SPINLOCK_BASE + (SG_SPINLOCK_NUM * 4))

/* Volatile pointer to the spinlock register */
#define SG_SPINLOCK_REG     (*(volatile uint32_t *)SG_SPINLOCK_ADDR)

/* Shared data structure between cores */
typedef struct {
    volatile uint32_t stall_count;       /* cumulative stall events */
    volatile uint8_t  stall_active;      /* current DIAG pin state (1=stalled) */
    volatile uint32_t last_stall_ticks;  /* timer_hw->timerawl at last rising edge */
    volatile uint32_t clear_request;     /* set by core0 to reset stall_count */
} stallguard_shared_t;

/*
 * Acquire spinlock #16.
 * Spins until the lock is available. Reading the spinlock register
 * returns 0 if already locked, non-zero on successful acquisition.
 */
static inline void sg_lock_acquire(void)
{
    while (SG_SPINLOCK_REG == 0)
        ;  /* spin until acquired */
}

/*
 * Release spinlock #16.
 * Writing any value to the spinlock register releases it.
 */
static inline void sg_lock_release(void)
{
    SG_SPINLOCK_REG = 1;
}

#endif /* STALLGUARD_SHARED_H */
