"""
W26 Cobot Axis -- RTDE Watchdog Timer

Detects stale RTDE data (UR30 program paused/stopped or silent
connection degradation) and triggers safe stepper shutdown.

Detection: monitors the UR30 controller timestamp field in RTDE data.
If the timestamp stops incrementing for WATCHDOG_TIMEOUT seconds, the
data is definitively stale.

Reference: docs/design/bridge_enhancements.md, Section 4.
"""

import logging
import time

from . import config

log = logging.getLogger(__name__)


class Watchdog:
    """Detects stale RTDE data and triggers safe shutdown."""

    def __init__(self, timeout: float = config.WATCHDOG_TIMEOUT,
                 enabled: bool = True):
        self._timeout = timeout
        self._enabled = enabled
        self._last_timestamp = None
        self._last_feed_time = time.monotonic()
        self._triggered = False

    @property
    def is_triggered(self) -> bool:
        """True if RTDE data has been stale for longer than the timeout."""
        return self._triggered

    def feed(self, cmd: dict) -> None:
        """
        Feed the watchdog with the latest command data from RTDE.

        Call this every tick with the dict returned by RTDEClient.read_commands().
        The dict must include a 'timestamp' key (UR30 controller time).
        """
        if not self._enabled:
            return

        now = time.monotonic()
        timestamp = cmd.get("timestamp")

        if timestamp is None:
            # No timestamp field -- cannot detect staleness, skip
            return

        if self._last_timestamp is None:
            # First feed -- initialise
            self._last_timestamp = timestamp
            self._last_feed_time = now
            return

        if timestamp != self._last_timestamp:
            # Data changed -- fresh
            self._last_timestamp = timestamp
            self._last_feed_time = now
            if self._triggered:
                log.info("Watchdog: fresh data received -- clearing trigger")
                self._triggered = False
            return

        # Timestamp unchanged -- check how long
        stale_duration = now - self._last_feed_time
        if stale_duration >= self._timeout and not self._triggered:
            log.warning("Watchdog triggered -- RTDE data stale for %.1fs "
                        "(timeout=%.1fs)", stale_duration, self._timeout)
            self._triggered = True

    def reset(self) -> None:
        """Reset the watchdog after recovery."""
        self._last_timestamp = None
        self._last_feed_time = time.monotonic()
        self._triggered = False
        log.debug("Watchdog reset")
