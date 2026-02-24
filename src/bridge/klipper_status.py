"""
W26 Cobot Axis -- Klipper Status Poller

Periodically queries Klipper status objects (TMC2209 driver status,
stepper enable state) and caches results for the main bridge loop.

The [manual_stepper] module does not expose a velocity status field in
mainline Klipper, so true measured velocity is not available. Instead
we poll TMC2209 driver status for stall detection (sg_result, stst)
and supplement with the commanded rate as the best estimate.

Reference: docs/design/bridge_enhancements.md, Section 1.
"""

from __future__ import annotations

import logging
import threading

from . import config
from .klipper_client import KlipperClient

log = logging.getLogger(__name__)


class KlipperStatusPoller:
    """Periodically queries Klipper status objects and caches results."""

    def __init__(self, klipper_client: KlipperClient,
                 poll_interval: float = config.STATUS_POLL_INTERVAL):
        self._klipper = klipper_client
        self._poll_interval = poll_interval
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Cached status data (protected by lock)
        self._lock = threading.Lock()
        self._last_tmc_status: dict = {}
        self._last_stallguard_status: dict = {}
        self._stepper_enabled_set: set = set()
        self._stale_count = 0
        self._tmc_available = True
        self._stallguard_available = True
        self._sg_accumulator = None

    def set_accumulator(self, accumulator) -> None:
        """Attach a StallGuardAccumulator to receive samples after each poll."""
        self._sg_accumulator = accumulator

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin polling in a background daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, name="klipper-status", daemon=True
        )
        self._thread.start()
        log.info("Klipper status poller started (interval=%.2fs)", self._poll_interval)

    def stop(self) -> None:
        """Stop the polling thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._poll_interval * 3)
            self._thread = None
        log.info("Klipper status poller stopped")

    # ------------------------------------------------------------------
    # Public query methods (called from main loop, thread-safe)
    # ------------------------------------------------------------------

    def get_tmc_status(self) -> dict:
        """Return the latest TMC2209 drv_status dict."""
        with self._lock:
            return dict(self._last_tmc_status)

    def is_stepper_enabled(self, name: str = config.STEPPER_NAME) -> bool:
        """True if the named stepper is reported as enabled by Klipper."""
        stepper_key = f"manual_stepper {name}"
        with self._lock:
            return stepper_key in self._stepper_enabled_set

    def is_stalled(self) -> bool:
        """
        True if StallGuard result is below the configured threshold.

        sg_result is a load measurement from the TMC2209; lower values
        indicate higher load / potential stall.
        """
        with self._lock:
            if not self._tmc_available or not self._last_tmc_status:
                return False
            drv = self._last_tmc_status.get("drv_status", {})
            sg_result = drv.get("sg_result")
            if sg_result is None:
                return False
            return sg_result < config.STALLGUARD_THRESHOLD

    def is_standstill(self) -> bool:
        """True if the TMC2209 stst (standstill) flag is set."""
        with self._lock:
            if not self._tmc_available or not self._last_tmc_status:
                return False
            drv = self._last_tmc_status.get("drv_status", {})
            return bool(drv.get("stst", False))

    def is_hardware_stall(self) -> bool:
        """
        True if core1 DIAG-based stall detection reports an active stall.

        This is faster than UART-polled is_stalled() because core1 monitors
        the DIAG pin at microsecond resolution via gpio16.
        """
        with self._lock:
            if not self._stallguard_available or not self._last_stallguard_status:
                return False
            return bool(self._last_stallguard_status.get("stall_active", False))

    def get_stallguard_status(self) -> dict:
        """Return the latest core1 StallGuard monitor status dict."""
        with self._lock:
            return dict(self._last_stallguard_status)

    # ------------------------------------------------------------------
    # Background polling loop
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        """Run in background thread: poll Klipper status at fixed interval."""
        while not self._stop_event.is_set():
            try:
                self._poll_once()
                self._stale_count = 0
            except TimeoutError:
                self._stale_count += 1
                log.warning("Klipper status poll timed out (stale_count=%d)",
                            self._stale_count)
            except ConnectionError as exc:
                self._stale_count += 1
                log.warning("Klipper status poll connection error: %s", exc)
            except RuntimeError as exc:
                # Klipper returned an error for a status object
                error_msg = str(exc).lower()
                if "tmc2209" in error_msg:
                    log.warning("TMC2209 status unavailable -- disabling TMC queries: %s", exc)
                    with self._lock:
                        self._tmc_available = False
                elif "stallguard" in error_msg:
                    log.warning("StallGuard monitor unavailable -- disabling: %s", exc)
                    with self._lock:
                        self._stallguard_available = False
                else:
                    log.warning("Klipper status poll error: %s", exc)
            except Exception as exc:
                log.error("Klipper status poller unexpected error: %s", exc,
                          exc_info=True)

            self._stop_event.wait(self._poll_interval)

    def _poll_once(self) -> None:
        """Execute a single status query."""
        objects = {}

        # Always query stepper_enable
        objects["stepper_enable"] = None

        # Query TMC2209 if available
        if self._tmc_available:
            objects["tmc2209 manual_stepper pump"] = None

        # Query core1 StallGuard monitor if available
        if self._stallguard_available:
            objects["stallguard_monitor"] = None

        result = self._klipper.query_status(objects)
        status = result.get("status", {})

        with self._lock:
            # Update stepper enable set
            stepper_enable_data = status.get("stepper_enable", {})
            steppers = stepper_enable_data.get("steppers", {})
            self._stepper_enabled_set = {
                name for name, enabled in steppers.items() if enabled
            }

            # Update TMC status
            if self._tmc_available:
                tmc_data = status.get("tmc2209 manual_stepper pump", {})
                if tmc_data:
                    self._last_tmc_status = tmc_data

            # Update StallGuard monitor status
            if self._stallguard_available:
                sg_data = status.get("stallguard_monitor", {})
                if sg_data:
                    self._last_stallguard_status = sg_data

        # Feed accumulator AFTER lock is released (avoids nested locking)
        if self._sg_accumulator is not None:
            drv = self._last_tmc_status.get("drv_status", {})
            sg = drv.get("sg_result", -1)
            sd = self._last_stallguard_status
            self._sg_accumulator.record(
                sg_result=sg if sg is not None else -1,
                stall_active=bool(sd.get("stall_active", False)),
                stall_count=sd.get("stall_count", 0),
                last_stall_ticks=sd.get("last_stall_ticks", 0),
            )
