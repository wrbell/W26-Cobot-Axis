"""
W26 Cobot Axis — RTDE-to-Klipper Bridge Daemon

Main loop: reads extrusion commands from UR30 via RTDE, translates
to Klipper MANUAL_STEPPER commands, writes status back to UR30.

Usage:
    python -m bridge.bridge_daemon
    python -m bridge.bridge_daemon --host 192.168.1.100 --dry-run

Reference: reqs/register_allocation.md for register mapping.
"""

import argparse
import logging
import signal
import sys
import time

from . import config
from .rtde_client import RTDEClient
from .klipper_client import KlipperClient

log = logging.getLogger("bridge")

# ---------------------------------------------------------------------------
# Bridge state
# ---------------------------------------------------------------------------

class BridgeState:
    """Tracks the current state of the bridge for status reporting."""

    def __init__(self):
        self.stepper_enabled = False
        self.current_mode = config.MODE_OFF
        self.current_rate = 0.0      # commanded rate (mm/s)
        self.actual_rate = 0.0       # reported by Klipper
        self.status = config.STATUS_IDLE
        self.error_code = config.ERR_NONE
        self.fault = False
        self.ready = False
        self.last_command_time = 0.0


# ---------------------------------------------------------------------------
# Main bridge logic
# ---------------------------------------------------------------------------

class Bridge:
    """RTDE ↔ Klipper bridge daemon."""

    def __init__(self, ur_host: str, dry_run: bool = False):
        self.rtde = RTDEClient(host=ur_host)
        self.klipper = KlipperClient(config.KLIPPY_SOCKET)
        self.state = BridgeState()
        self.dry_run = dry_run
        self._running = False

    def start(self) -> None:
        """Connect to both endpoints and enter main loop."""
        self._running = True
        self._connect_all()
        self.state.ready = True
        self.state.status = config.STATUS_IDLE

        log.info("Bridge running at %d Hz (dry_run=%s)", config.LOOP_HZ, self.dry_run)

        try:
            while self._running:
                loop_start = time.monotonic()
                self._tick()
                elapsed = time.monotonic() - loop_start
                sleep_time = config.LOOP_PERIOD - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        except KeyboardInterrupt:
            log.info("Interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        """Cleanly shut down: disable stepper, disconnect."""
        self._running = False
        log.info("Shutting down bridge...")

        # Disable stepper
        try:
            if not self.dry_run and self.klipper.connected:
                self.klipper.stepper_disable(config.STEPPER_NAME)
        except Exception as exc:
            log.warning("Failed to disable stepper on shutdown: %s", exc)

        # Report offline status
        try:
            if self.rtde.connected:
                self.rtde.write_status(
                    status=config.STATUS_IDLE,
                    error_code=config.ERR_NONE,
                    actual_rate=0.0,
                    ready=False,
                    fault=False,
                )
        except Exception:
            pass

        self.rtde.disconnect()
        self.klipper.disconnect()
        log.info("Bridge stopped.")

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect_all(self) -> None:
        """Connect to RTDE and Klipper, retrying until successful."""
        # Connect RTDE
        while self._running:
            try:
                self.rtde.connect()
                break
            except Exception as exc:
                log.warning("RTDE connection failed: %s — retrying in %.0fs",
                            exc, config.RECONNECT_DELAY)
                time.sleep(config.RECONNECT_DELAY)

        # Connect Klipper
        while self._running:
            try:
                self.klipper.connect()
                # Verify Klipper is ready
                info = self.klipper.get_info()
                log.info("Klipper state: %s", info.get("state_message", "unknown"))
                break
            except Exception as exc:
                log.warning("Klipper connection failed: %s — retrying in %.0fs",
                            exc, config.RECONNECT_DELAY)
                time.sleep(config.RECONNECT_DELAY)

    # ------------------------------------------------------------------
    # Main loop tick
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        """Single iteration of the bridge loop."""
        try:
            # 1. Read commands from UR30
            cmd = self.rtde.read_commands()

            # 2. Process commands
            self._process_commands(cmd)

            # 3. Write status back to UR30
            self._report_status()

        except ConnectionError as exc:
            log.error("Connection lost: %s", exc)
            self.state.status = config.STATUS_ERROR
            self.state.error_code = config.ERR_COMMS_LOST
            self.state.fault = True
            self._try_emergency_stop()
            self._connect_all()

    def _process_commands(self, cmd: dict) -> None:
        """Translate RTDE commands into Klipper actions."""

        # Emergency stop takes priority
        if cmd["estop"]:
            log.warning("E-STOP received from UR30")
            self._emergency_stop()
            return

        # Homing request
        if cmd["home"] and self.state.status != config.STATUS_HOMING:
            self._do_homing()
            return

        # If not enabled, ensure stepper is off
        if not cmd["enable"]:
            if self.state.stepper_enabled:
                self._stop_extrusion()
            return

        # Extrusion control
        mode = cmd["mode"]
        rate = cmd["extrusion_rate"]

        # Clamp rate to safety limit
        rate = max(0.0, min(rate, config.MAX_EXTRUSION_RATE))

        if mode == config.MODE_OFF:
            if self.state.current_mode != config.MODE_OFF:
                self._stop_extrusion()

        elif mode in (config.MODE_EXTRUDE, config.MODE_RETRACT):
            direction = 1.0 if mode == config.MODE_EXTRUDE else -1.0

            if rate > 0.01:  # deadband
                self._set_extrusion(rate * direction)
                self.state.status = config.STATUS_RUNNING
            else:
                self._stop_extrusion()

        self.state.current_mode = mode
        self.state.current_rate = rate

    # ------------------------------------------------------------------
    # Klipper actions
    # ------------------------------------------------------------------

    def _set_extrusion(self, rate_mm_s: float) -> None:
        """
        Command the stepper to move continuously at the given rate.

        Uses a large relative move at the target speed. Klipper's motion
        planner will smoothly accelerate/decelerate between speed changes.
        """
        if self.dry_run:
            log.debug("DRY RUN: MOVE %.2f mm/s", rate_mm_s)
            return

        if not self.state.stepper_enabled:
            self.klipper.stepper_enable(config.STEPPER_NAME)
            self.state.stepper_enabled = True

        # Issue a large move in the desired direction at target speed.
        # The bridge will update speed each tick; Klipper replans smoothly.
        distance = rate_mm_s * 10.0  # ~10 seconds of travel
        speed = abs(rate_mm_s)
        try:
            self.klipper.stepper_move(
                config.STEPPER_NAME, distance, speed, config.DEFAULT_ACCEL
            )
            self.state.last_command_time = time.monotonic()
        except Exception as exc:
            log.error("Klipper move failed: %s", exc)
            self.state.status = config.STATUS_ERROR
            self.state.error_code = config.ERR_COMMS_LOST

    def _stop_extrusion(self) -> None:
        """Stop the stepper and reset state."""
        if self.dry_run:
            log.debug("DRY RUN: STOP")
            self.state.current_mode = config.MODE_OFF
            self.state.status = config.STATUS_IDLE
            return

        try:
            # Set position to 0 — this effectively cancels pending moves
            self.klipper.stepper_set_position(config.STEPPER_NAME, 0.0)
            self.state.current_mode = config.MODE_OFF
            self.state.current_rate = 0.0
            self.state.status = config.STATUS_IDLE
        except Exception as exc:
            log.error("Failed to stop extrusion: %s", exc)

    def _emergency_stop(self) -> None:
        """Immediate halt — disable stepper and send Klipper emergency stop."""
        log.warning("Executing emergency stop")
        if not self.dry_run:
            self.klipper.emergency_stop()
        self.state.stepper_enabled = False
        self.state.status = config.STATUS_ERROR
        self.state.current_mode = config.MODE_OFF
        self.state.current_rate = 0.0

    def _try_emergency_stop(self) -> None:
        """Best-effort emergency stop (used during error recovery)."""
        try:
            if not self.dry_run and self.klipper.connected:
                self.klipper.stepper_disable(config.STEPPER_NAME)
        except Exception:
            pass

    def _do_homing(self) -> None:
        """Execute homing sequence (placeholder — depends on pump setup)."""
        log.info("Homing requested")
        self.state.status = config.STATUS_HOMING
        if not self.dry_run:
            try:
                self.klipper.stepper_set_position(config.STEPPER_NAME, 0.0)
            except Exception as exc:
                log.error("Homing failed: %s", exc)
                self.state.status = config.STATUS_ERROR
                return
        self.state.status = config.STATUS_IDLE
        log.info("Homing complete — position zeroed")

    # ------------------------------------------------------------------
    # Status reporting
    # ------------------------------------------------------------------

    def _report_status(self) -> None:
        """Write current stepper status to UR30 via RTDE input registers."""
        try:
            self.rtde.write_status(
                status=self.state.status,
                error_code=self.state.error_code,
                actual_rate=self.state.current_rate,  # TODO: read from Klipper
                ready=self.state.ready and not self.state.fault,
                fault=self.state.fault,
            )
        except Exception as exc:
            log.warning("Failed to write RTDE status: %s", exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="W26 RTDE-to-Klipper Bridge")
    parser.add_argument("--host", default=config.UR30_HOST,
                        help=f"UR30 IP address (default: {config.UR30_HOST})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without sending commands to Klipper")
    parser.add_argument("--log-level", default=config.LOG_LEVEL,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    bridge = Bridge(ur_host=args.host, dry_run=args.dry_run)

    # Graceful shutdown on SIGTERM
    signal.signal(signal.SIGTERM, lambda *_: bridge.stop())

    bridge.start()


if __name__ == "__main__":
    main()
