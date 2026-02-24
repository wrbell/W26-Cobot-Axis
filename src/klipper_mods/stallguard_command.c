/*
 * W26 Cobot Axis -- Klipper MCU Command Handlers for StallGuard
 *
 * Runs on core0 alongside Klipper's scheduler. Registers two
 * DECL_COMMAND handlers that the klippy host can invoke:
 *
 *   stallguard_query  -> reads shared SRAM, responds with current state
 *   stallguard_clear  -> requests core1 to reset the stall counter
 *
 * The shared SRAM is protected by hardware spinlock #16 (see
 * stallguard_shared.h). Reads are fast (<1us) so there is no
 * measurable impact on Klipper's step timing.
 *
 * Reference: Klipper MCU command protocol (docs/klipper_protocols.md)
 */

#include "autoconf.h"   /* Klipper build config */
#include "command.h"     /* DECL_COMMAND, sendf */
#include "stallguard_shared.h"

/* Shared SRAM instance -- defined in core1_stallguard.c */
extern stallguard_shared_t sg_shared;

/*
 * stallguard_query
 *
 * Read the current StallGuard state from shared SRAM and send it
 * back to the host. The spinlock ensures we get a consistent
 * snapshot even if core1 is mid-update.
 *
 * Response format:
 *   stallguard_state stall_active=%c stall_count=%u last_stall_ticks=%u
 */
void command_stallguard_query(uint32_t *args)
{
    sg_lock_acquire();
    uint8_t  active = sg_shared.stall_active;
    uint32_t count  = sg_shared.stall_count;
    uint32_t ticks  = sg_shared.last_stall_ticks;
    sg_lock_release();

    sendf("stallguard_state stall_active=%c stall_count=%u last_stall_ticks=%u",
          active, count, ticks);
}
DECL_COMMAND(command_stallguard_query, "stallguard_query");

/*
 * stallguard_clear
 *
 * Set the clear_request flag so core1 resets stall_count on its
 * next iteration. We don't modify stall_count directly from core0
 * to avoid a race with core1's increment logic.
 */
void command_stallguard_clear(uint32_t *args)
{
    sg_lock_acquire();
    sg_shared.clear_request = 1;
    sg_lock_release();

    sendf("stallguard_state stall_active=%c stall_count=%u last_stall_ticks=%u",
          sg_shared.stall_active, 0, sg_shared.last_stall_ticks);
}
DECL_COMMAND(command_stallguard_clear, "stallguard_clear");
