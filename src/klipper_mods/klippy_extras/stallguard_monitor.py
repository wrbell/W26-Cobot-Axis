"""
W26 Cobot Axis -- Klippy Extras: StallGuard Monitor

Queries the RP2040 core1 StallGuard state via custom MCU commands
and exposes results as a Klipper status object.

Core1 monitors the TMC2209 DIAG pin (gpio16) at microsecond speed
and writes stall events to shared SRAM. This module polls that state
from the host side at a configurable interval (default 20 Hz / 50ms).

Installation:
    Copy to ~/klipper/klippy/extras/stallguard_monitor.py
    Add [stallguard_monitor] section to printer.cfg

Status object fields (available via objects/query):
    stall_active       - bool: True if DIAG pin is currently asserted
    stall_count        - int: cumulative stall events since last clear
    last_stall_ticks   - int: MCU timer ticks at last stall edge
"""

import logging


class StallGuardMonitor:
    """Klipper extras module for core1 StallGuard monitoring."""

    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.name = config.get_name()

        # Configuration
        self.poll_interval = config.getfloat(
            "poll_interval", default=0.05, minval=0.01, maxval=1.0
        )

        # State
        self.stall_active = False
        self.stall_count = 0
        self.last_stall_ticks = 0
        self._mcu = None
        self._cmd_query = None
        self._cmd_clear = None
        self._poll_timer = None
        self._error_count = 0

        # Register with Klipper's object system so Moonraker can find us
        self.printer.add_object(self.name, self)

        # Register event handlers
        self.printer.register_event_handler(
            "klippy:connect", self._handle_connect
        )
        self.printer.register_event_handler(
            "klippy:disconnect", self._handle_disconnect
        )

    def _handle_connect(self):
        """Called when klippy connects to the MCU."""
        self._mcu = self.printer.lookup_object("mcu")

        # Allocate a command queue so stallguard queries don't compete
        # with stepper commands on the default queue.
        cmd_queue = self._mcu.alloc_command_queue()

        # Register MCU commands — if firmware overlay is missing, these
        # will raise and Klipper will log a clear error at startup.
        self._cmd_query = self._mcu.lookup_command(
            "stallguard_query", cq=cmd_queue
        )
        self._mcu.register_response(
            self._handle_stallguard_state, "stallguard_state"
        )
        self._cmd_clear = self._mcu.lookup_command(
            "stallguard_clear", cq=cmd_queue
        )

        # Start polling timer
        self._poll_timer = self.reactor.register_timer(
            self._poll_callback, self.reactor.NOW
        )
        logging.info(
            "StallGuard monitor started (poll_interval=%.3fs)",
            self.poll_interval,
        )

    def _handle_disconnect(self):
        """Called when klippy disconnects from the MCU."""
        if self._poll_timer is not None:
            self.reactor.unregister_timer(self._poll_timer)
            self._poll_timer = None

    def _poll_callback(self, eventtime):
        """Timer callback: send a stallguard_query to the MCU."""
        try:
            self._cmd_query.send()
            self._error_count = 0
        except Exception:
            self._error_count += 1
            if self._error_count <= 3:
                logging.exception("StallGuard query failed")
            elif self._error_count == 4:
                logging.error(
                    "StallGuard query failing repeatedly — suppressing"
                )
        return eventtime + self.poll_interval

    def _handle_stallguard_state(self, params):
        """Handle stallguard_state response from MCU."""
        self.stall_active = bool(params.get("stall_active", 0))
        self.stall_count = params.get("stall_count", 0)
        self.last_stall_ticks = params.get("last_stall_ticks", 0)

    def clear_stall_count(self):
        """Request core1 to reset the stall counter."""
        if self._cmd_clear is not None:
            self._cmd_clear.send()

    def get_status(self, eventtime=None):
        """Return status dict for Klipper's objects/query API."""
        return {
            "stall_active": self.stall_active,
            "stall_count": self.stall_count,
            "last_stall_ticks": self.last_stall_ticks,
        }


def load_config(config):
    """Klipper extras entry point."""
    return StallGuardMonitor(config)
