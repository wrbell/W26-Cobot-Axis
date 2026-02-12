"""
W26 Cobot Axis — RTDE-to-Klipper Bridge Daemon

Main loop: reads extrusion commands from UR30 via RTDE, translates
to Klipper MANUAL_STEPPER commands, writes status back to UR30.

Enhancements (see docs/design/bridge_enhancements.md):
  1. Watchdog timer — detect stale RTDE data, auto-disable stepper
  2. Klipper status polling — TMC2209 stall/standstill feedback
  3. Data logging — CSV telemetry for Phase 4 test/reporting
  4. Speed-proportional extrusion — bridge-computed rate from TCP speed
  5. Extrusion profiles — non-linear rate mapping (JSON-configurable)
  6. Dashboard Server — UR30 lifecycle management (port 29999)

Usage:
    python -m bridge.bridge_daemon
    python -m bridge.bridge_daemon --host 192.168.1.100 --dry-run
    python -m bridge.bridge_daemon --log --extrusion-source bridge --dashboard

Reference: docs/register_allocation.md for register mapping.
"""

import argparse
import logging
import signal
import time

from . import config
from .rtde_client import RTDEClient
from .klipper_client import KlipperClient
from .watchdog import Watchdog
from .klipper_status import KlipperStatusPoller
from .data_logger import DataLogger
from .extrusion_profile import load_active_profile
from .dashboard_client import DashboardClient, DashboardPoller

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
        self.actual_rate = 0.0       # reported back to UR30
        self.status = config.STATUS_IDLE
        self.error_code = config.ERR_NONE
        self.fault = False
        self.ready = False
        self.last_command_time = 0.0


# ---------------------------------------------------------------------------
# Main bridge logic
# ---------------------------------------------------------------------------

class Bridge:
    """RTDE <-> Klipper bridge daemon."""

    def __init__(self, ur_host: str, dry_run: bool = False,
                 enable_watchdog: bool = True,
                 enable_status_poll: bool = True,
                 enable_logging: bool = False,
                 log_dir: str = config.LOG_DIR,
                 log_decimation: int = config.LOG_DECIMATION,
                 extrusion_source: int = config.DEFAULT_EXTRUSION_COMP_MODE,
                 extrusion_multiplier: float = config.EXTRUSION_MULTIPLIER,
                 profile_file: str | None = None,
                 profile_name: str | None = None,
                 enable_dashboard: bool = False,
                 dashboard_auto_start: bool = False,
                 ur_program: str = config.UR_PROGRAM_PATH):
        self.rtde = RTDEClient(host=ur_host)
        self.klipper = KlipperClient(config.KLIPPY_SOCKET)
        self.state = BridgeState()
        self.dry_run = dry_run
        self._running = False
        self._tick_count = 0

        # --- Enhancement 1: Watchdog ---
        self.watchdog = Watchdog(
            timeout=config.WATCHDOG_TIMEOUT,
            enabled=enable_watchdog,
        )

        # --- Enhancement 2: Klipper status polling ---
        self._enable_status_poll = enable_status_poll
        self.status_poller: KlipperStatusPoller | None = None
        if enable_status_poll:
            self.status_poller = KlipperStatusPoller(
                klipper_client=self.klipper,
                poll_interval=config.STATUS_POLL_INTERVAL,
            )

        # --- Enhancement 3: Data logging ---
        self.data_logger: DataLogger | None = None
        if enable_logging:
            self.data_logger = DataLogger(
                log_dir=log_dir,
                decimation=log_decimation,
            )

        # --- Enhancement 4: Speed-proportional extrusion ---
        self.extrusion_source = extrusion_source
        self.extrusion_multiplier = extrusion_multiplier

        # --- Enhancement 5: Extrusion profiles ---
        self.active_profile = load_active_profile(
            profile_file=profile_file,
            profile_name=profile_name,
        )
        log.info("Active extrusion profile: %s", self.active_profile)

        # --- Enhancement 6: Dashboard Server ---
        self._enable_dashboard = enable_dashboard
        self._dashboard_auto_start = dashboard_auto_start
        self._ur_program = ur_program
        self.dashboard: DashboardClient | None = None
        self.dashboard_poller: DashboardPoller | None = None
        if enable_dashboard:
            self.dashboard = DashboardClient(host=ur_host)

    def start(self) -> None:
        """Connect to all endpoints and enter main loop."""
        self._running = True
        self._connect_all()
        self.state.ready = True
        self.state.status = config.STATUS_IDLE

        # Start subsystems
        if self.status_poller:
            self.status_poller.start()

        if self.data_logger:
            self.data_logger.start()

        log.info("Bridge running at %d Hz (dry_run=%s, extrusion_source=%s, "
                 "watchdog=%s, status_poll=%s, logging=%s, dashboard=%s)",
                 config.LOOP_HZ, self.dry_run,
                 "bridge" if self.extrusion_source == config.EXTRUSION_MODE_BRIDGE else "ur",
                 self.watchdog._enabled,
                 self.status_poller is not None,
                 self.data_logger is not None,
                 self.dashboard is not None)

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
        """Cleanly shut down: disable stepper, stop subsystems, disconnect."""
        self._running = False
        log.info("Shutting down bridge...")

        # Stop subsystems
        if self.status_poller:
            self.status_poller.stop()

        if self.dashboard_poller:
            self.dashboard_poller.stop()

        if self.data_logger:
            self.data_logger.stop()

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

        # Disconnect Dashboard Server
        if self.dashboard and self.dashboard.connected:
            try:
                self.dashboard.disconnect()
            except Exception:
                pass

        self.rtde.disconnect()
        self.klipper.disconnect()
        log.info("Bridge stopped.")

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect_all(self) -> None:
        """Connect to RTDE, Klipper, and optionally Dashboard Server."""
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

        # Connect Dashboard Server (optional, non-blocking)
        if self.dashboard:
            try:
                self.dashboard.connect()
                self._log_robot_info()
                # Start background poller
                self.dashboard_poller = DashboardPoller(
                    dashboard=self.dashboard,
                    poll_interval=config.DASHBOARD_POLL_INTERVAL,
                )
                self.dashboard_poller.start()
                # Auto-start sequence
                if self._dashboard_auto_start:
                    self._dashboard_auto_start_sequence()
            except ConnectionError as exc:
                log.warning("Dashboard connection failed (non-critical): %s", exc)
                self.dashboard = None

    def _log_robot_info(self) -> None:
        """Log robot identification from Dashboard Server."""
        if not self.dashboard or not self.dashboard.connected:
            return
        try:
            model = self.dashboard.get_robot_model()
            serial = self.dashboard.get_serial_number()
            version = self.dashboard.get_polyscope_version()
            mode = self.dashboard.get_robot_mode()
            safety = self.dashboard.get_safety_mode()
            log.info("Robot: %s (S/N: %s, Polyscope %s)", model, serial, version)
            log.info("Robot mode: %s, Safety mode: %s", mode, safety)
        except ConnectionError as exc:
            log.warning("Failed to read robot info: %s", exc)

    def _dashboard_auto_start_sequence(self) -> None:
        """Attempt to auto-start the UR program via Dashboard Server."""
        if not self.dashboard or not self.dashboard.connected:
            return

        try:
            if not self.dashboard.is_in_remote_control():
                log.error("Cannot auto-start: robot is not in Remote Control mode")
                return

            robot_mode = self.dashboard.get_robot_mode()
            if robot_mode == "POWER_OFF":
                log.info("Powering on robot...")
                self.dashboard.power_on()
                time.sleep(5.0)
                log.info("Releasing brakes...")
                self.dashboard.brake_release()
                time.sleep(10.0)

            log.info("Loading program: %s", self._ur_program)
            resp = self.dashboard.load_program(self._ur_program)
            log.info("Load response: %s", resp)

            log.info("Starting program...")
            resp = self.dashboard.play()
            log.info("Play response: %s", resp)

        except ConnectionError as exc:
            log.error("Auto-start failed: %s", exc)

    # ------------------------------------------------------------------
    # Main loop tick
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        """Single iteration of the bridge loop."""
        t0 = time.perf_counter()

        try:
            # 1. Read commands from UR30
            cmd = self.rtde.read_commands()
            t1 = time.perf_counter()

            # 2. Feed watchdog
            self.watchdog.feed(cmd)
            if self.watchdog.is_triggered:
                log.warning("Watchdog triggered — RTDE data stale for %.1fs",
                            config.WATCHDOG_TIMEOUT)
                self._stop_extrusion()
                self.state.status = config.STATUS_ERROR
                self.state.error_code = config.ERR_COMMS_LOST
                self.state.fault = True
                self._report_status()
                if self.data_logger:
                    self.data_logger.annotate("WATCHDOG")
                self._watchdog_recovery()
                return

            # 3. Check Dashboard state (if available)
            self._check_dashboard_state()

            # 4. Check Klipper status poller for stalls
            self._check_stall_status()

            # 5. Process commands
            self._process_commands(cmd)
            t2 = time.perf_counter()

            # 6. Write status back to UR30
            self._report_status()
            t3 = time.perf_counter()

            # 7. Log telemetry
            self._tick_count += 1
            if self.data_logger:
                tmc_status = {}
                if self.status_poller:
                    tmc_status = self.status_poller.get_tmc_status()
                drv = tmc_status.get("drv_status", {})
                self.data_logger.log_tick({
                    "timestamp": time.monotonic(),
                    "wall_clock": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "tick_number": self._tick_count,
                    "loop_dt_ms": (t3 - t0) * 1000,
                    "mode": cmd.get("mode", 0),
                    "enable": cmd.get("enable", False),
                    "commanded_rate": self.state.current_rate,
                    "tcp_speed": cmd.get("tcp_speed", 0.0),
                    "actual_rate": self.state.actual_rate,
                    "status": self.state.status,
                    "error_code": self.state.error_code,
                    "stepper_enabled": self.state.stepper_enabled,
                    "tmc_sg_result": drv.get("sg_result", -1),
                    "tmc_standstill": drv.get("stst", False),
                    "rtde_read_us": (t1 - t0) * 1e6,
                    "klipper_cmd_us": (t2 - t1) * 1e6,
                })

        except ConnectionError as exc:
            log.error("Connection lost: %s", exc)
            self.state.status = config.STATUS_ERROR
            self.state.error_code = config.ERR_COMMS_LOST
            self.state.fault = True
            if self.data_logger:
                self.data_logger.annotate("RECONNECT")
            self._try_emergency_stop()
            self._connect_all()

    def _watchdog_recovery(self) -> None:
        """
        Enter recovery mode after watchdog triggers.

        Disables the stepper and waits for fresh RTDE data. When fresh
        data arrives the watchdog resets automatically, but the stepper
        does NOT auto-re-enable -- the UR30 must re-assert enable=True.
        """
        log.info("Entering watchdog recovery -- waiting for fresh RTDE data")
        self._try_emergency_stop()

        while self._running:
            try:
                cmd = self.rtde.read_commands()
                self.watchdog.feed(cmd)
                if not self.watchdog.is_triggered:
                    log.info("Watchdog recovery -- fresh data received, resuming")
                    self.state.fault = False
                    self.state.error_code = config.ERR_NONE
                    self.state.status = config.STATUS_IDLE
                    return
            except ConnectionError:
                log.warning("Connection lost during watchdog recovery")
                self._connect_all()
                return

            time.sleep(config.LOOP_PERIOD)

    def _check_dashboard_state(self) -> None:
        """Check cached Dashboard Server state for program stop/pause."""
        if not self.dashboard_poller:
            return

        prog_state = self.dashboard_poller.get_cached_program_state()
        if prog_state in ("STOPPED", "PAUSED") and self.state.stepper_enabled:
            log.warning("UR30 program %s — disabling stepper", prog_state)
            self._stop_extrusion()
            if self.data_logger:
                self.data_logger.annotate(f"UR_PROG_{prog_state}")

        safety_mode = self.dashboard_poller.get_cached_safety_mode()
        if safety_mode and safety_mode != "NORMAL":
            if not self.state.fault:
                log.warning("UR30 safety mode: %s — setting fault", safety_mode)
                self.state.fault = True
                self._stop_extrusion()
                if self.data_logger:
                    self.data_logger.annotate(f"SAFETY_{safety_mode}")

    def _check_stall_status(self) -> None:
        """Check Klipper status poller for stall detection."""
        if not self.status_poller:
            return

        if self.status_poller.is_stalled():
            if self.state.error_code != config.ERR_STALL:
                log.warning("Stepper stall detected (StallGuard below threshold)")
                self.state.error_code = config.ERR_STALL
                self.state.fault = True
                if self.data_logger:
                    self.data_logger.annotate("STALL")

    # ------------------------------------------------------------------
    # Extrusion rate computation (Enhancements 4 + 5)
    # ------------------------------------------------------------------

    def _resolve_extrusion_rate(self, cmd: dict) -> float:
        """
        Determine extrusion rate based on computation mode and profile.

        Pipeline:
            1. Source selection (UR-computed or bridge-computed)
            2. Profile mapping (linear, polynomial, lookup table)
            3. Safety clamp to MAX_EXTRUSION_RATE
        """
        # Step 1: Select rate source
        if self.extrusion_source == config.EXTRUSION_MODE_BRIDGE:
            tcp_speed = cmd.get("tcp_speed", 0.0)
            raw_rate = tcp_speed * self.extrusion_multiplier
        else:
            raw_rate = cmd.get("extrusion_rate", 0.0)

        # Step 2: Apply profile mapping
        mapped_rate = self._apply_profile(raw_rate)

        # Step 3: Safety clamp
        return max(0.0, min(mapped_rate, config.MAX_EXTRUSION_RATE))

    def _apply_profile(self, raw_rate: float) -> float:
        """Apply the active extrusion profile to map raw rate to output rate."""
        try:
            return self.active_profile.apply(raw_rate)
        except Exception as exc:
            log.warning("Profile apply failed: %s — using raw rate", exc)
            return raw_rate

    def _process_commands(self, cmd: dict) -> None:
        """Translate RTDE commands into Klipper actions."""

        # Emergency stop takes priority
        if cmd["estop"]:
            log.warning("E-STOP received from UR30")
            self._emergency_stop()
            if self.data_logger:
                self.data_logger.annotate("ESTOP")
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
        rate = self._resolve_extrusion_rate(cmd)

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
            self.state.current_rate = 0.0
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
    # Status reporting (Enhancement 2: Klipper status feedback)
    # ------------------------------------------------------------------

    def _report_status(self) -> None:
        """Write current stepper status to UR30 via RTDE input registers."""
        # Determine actual rate using Klipper status feedback
        if self.status_poller:
            if self.status_poller.is_standstill() or self.status_poller.is_stalled():
                actual_rate = 0.0
            else:
                actual_rate = self.state.current_rate  # commanded rate as best estimate
        else:
            actual_rate = self.state.current_rate  # no poller — use commanded rate

        self.state.actual_rate = actual_rate

        try:
            self.rtde.write_status(
                status=self.state.status,
                error_code=self.state.error_code,
                actual_rate=actual_rate,
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

    # Core arguments
    parser.add_argument("--host", default=config.UR30_HOST,
                        help=f"UR30 IP address (default: {config.UR30_HOST})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without sending commands to Klipper")
    parser.add_argument("--log-level", default=config.LOG_LEVEL,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    # Enhancement 1: Watchdog
    parser.add_argument("--no-watchdog", action="store_true",
                        help="Disable the RTDE watchdog timer")

    # Enhancement 2: Klipper status polling
    parser.add_argument("--no-status-poll", action="store_true",
                        help="Disable Klipper TMC2209 status polling")

    # Enhancement 3: Data logging
    parser.add_argument("--log", action="store_true", dest="enable_log",
                        help="Enable CSV data logging")
    parser.add_argument("--log-dir", default=config.LOG_DIR,
                        help=f"Log output directory (default: {config.LOG_DIR})")
    parser.add_argument("--log-decimate", type=int, default=config.LOG_DECIMATION,
                        help=f"Log every Nth tick (default: {config.LOG_DECIMATION})")

    # Enhancement 4: Speed-proportional extrusion
    parser.add_argument("--extrusion-source", choices=["ur", "bridge"],
                        default="ur",
                        help="Extrusion rate source (default: ur)")
    parser.add_argument("--extrusion-multiplier", type=float,
                        default=config.EXTRUSION_MULTIPLIER,
                        help=f"mm extruded per mm/s TCP speed (default: {config.EXTRUSION_MULTIPLIER})")

    # Enhancement 5: Extrusion profiles
    parser.add_argument("--profile", default=None,
                        help="Active extrusion profile name (from profiles.json)")
    parser.add_argument("--profile-file", default=None,
                        help="Path to extrusion profiles JSON file")

    # Enhancement 6: Dashboard Server
    parser.add_argument("--dashboard", action="store_true",
                        help="Enable Dashboard Server integration (port 29999)")
    parser.add_argument("--dashboard-auto", action="store_true",
                        help="Auto-start UR program on bridge startup (implies --dashboard)")
    parser.add_argument("--ur-program", default=config.UR_PROGRAM_PATH,
                        help=f"URScript program path on robot (default: {config.UR_PROGRAM_PATH})")

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Validate extrusion multiplier
    if args.extrusion_multiplier <= 0.0:
        parser.error("--extrusion-multiplier must be positive")

    # Resolve extrusion source enum
    extrusion_source = (config.EXTRUSION_MODE_BRIDGE
                        if args.extrusion_source == "bridge"
                        else config.EXTRUSION_MODE_UR)

    # --dashboard-auto implies --dashboard
    enable_dashboard = args.dashboard or args.dashboard_auto

    bridge = Bridge(
        ur_host=args.host,
        dry_run=args.dry_run,
        enable_watchdog=not args.no_watchdog,
        enable_status_poll=not args.no_status_poll,
        enable_logging=args.enable_log,
        log_dir=args.log_dir,
        log_decimation=args.log_decimate,
        extrusion_source=extrusion_source,
        extrusion_multiplier=args.extrusion_multiplier,
        profile_file=args.profile_file,
        profile_name=args.profile,
        enable_dashboard=enable_dashboard,
        dashboard_auto_start=args.dashboard_auto,
        ur_program=args.ur_program,
    )

    # Graceful shutdown on SIGTERM
    signal.signal(signal.SIGTERM, lambda *_: bridge.stop())

    bridge.start()


if __name__ == "__main__":
    main()
