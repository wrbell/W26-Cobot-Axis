"""
W26 Cobot Axis -- UR30 Dashboard Server Client

TCP client for the UR30 Dashboard Server (port 29999). Provides
high-level robot lifecycle management: power on/off, brake release,
program load/play/stop, mode and safety queries.

The Dashboard Server uses a text-based protocol: send a command line
terminated by newline, receive a single-line response terminated by
newline.

Reference: docs/design/bridge_enhancements.md, Section 6.
"""

import logging
import socket
import threading
import time

from . import config

log = logging.getLogger(__name__)


class DashboardClient:
    """TCP client for UR30 Dashboard Server (port 29999)."""

    def __init__(self, host: str, port: int = config.DASHBOARD_PORT,
                 timeout: float = config.DASHBOARD_TIMEOUT):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._sock: socket.socket | None = None
        self._file = None
        self._lock = threading.Lock()
        self._banner: str = ""

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to the Dashboard Server and read the welcome banner."""
        self.disconnect()
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self._timeout)
            self._sock.connect((self._host, self._port))
            self._file = self._sock.makefile("rw", buffering=1)
            # Read and discard the welcome banner
            self._banner = self._file.readline().strip()
            log.info("Dashboard connected to %s:%d -- banner: %s",
                     self._host, self._port, self._banner)
        except OSError as exc:
            self._sock = None
            self._file = None
            raise ConnectionError(
                f"Cannot connect to Dashboard Server at {self._host}:{self._port}: {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Close the Dashboard Server connection."""
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    @property
    def connected(self) -> bool:
        return self._sock is not None

    # ------------------------------------------------------------------
    # Low-level command/response
    # ------------------------------------------------------------------

    def send_command(self, command: str) -> str:
        """
        Send a command and return the response line.

        Raises ConnectionError if not connected or communication fails.
        """
        if self._sock is None or self._file is None:
            raise ConnectionError("Not connected to Dashboard Server")

        with self._lock:
            try:
                self._file.write(command + "\n")
                self._file.flush()
                response = self._file.readline().strip()
                log.debug("Dashboard: '%s' -> '%s'", command, response)
                return response
            except (OSError, socket.timeout) as exc:
                raise ConnectionError(
                    f"Dashboard command '{command}' failed: {exc}"
                ) from exc

    # ------------------------------------------------------------------
    # Status queries (read-only, safe to call anytime)
    # ------------------------------------------------------------------

    def get_robot_mode(self) -> str:
        """
        Get current robot mode.

        Returns one of: NO_CONTROLLER, DISCONNECTED, CONFIRM_SAFETY,
        BOOTING, POWER_OFF, POWER_ON, IDLE, BACKDRIVE, RUNNING
        """
        resp = self.send_command("robotmode")
        # Response format: "Robotmode: RUNNING"
        return self._parse_value(resp, "Robotmode:")

    def get_program_state(self) -> str:
        """
        Get current program execution state.

        Returns: PLAYING, STOPPED, PAUSED, or the raw response.
        """
        resp = self.send_command("programState")
        # Response is typically just the state name
        return resp.strip().upper()

    def is_running(self) -> bool:
        """True if a program is currently executing."""
        resp = self.send_command("running")
        return "true" in resp.lower()

    def get_safety_mode(self) -> str:
        """
        Get current safety mode.

        Returns one of: NORMAL, REDUCED, PROTECTIVE_STOP, RECOVERY,
        SAFEGUARD_STOP, SYSTEM_EMERGENCY_STOP, ROBOT_EMERGENCY_STOP,
        VIOLATION, FAULT
        """
        resp = self.send_command("safetymode")
        return self._parse_value(resp, "Safetymode:")

    def get_robot_model(self) -> str:
        """Get robot model string (e.g., 'UR30')."""
        return self.send_command("get robot model").strip()

    def get_serial_number(self) -> str:
        """Get robot serial number."""
        return self.send_command("get serial number").strip()

    def get_polyscope_version(self) -> str:
        """Get Polyscope software version."""
        return self.send_command("PolyscopeVersion").strip()

    def is_in_remote_control(self) -> bool:
        """True if the robot is in remote control mode."""
        resp = self.send_command("is in remote control")
        return "true" in resp.lower()

    # ------------------------------------------------------------------
    # Control commands (require remote control mode)
    # ------------------------------------------------------------------

    def load_program(self, path: str) -> str:
        """Load a program from the robot filesystem."""
        return self.send_command(f"load {path}")

    def play(self) -> str:
        """Start the loaded program."""
        return self.send_command("play")

    def stop(self) -> str:
        """Stop the running program."""
        return self.send_command("stop")

    def pause(self) -> str:
        """Pause the running program."""
        return self.send_command("pause")

    def power_on(self) -> str:
        """Power on the robot arm."""
        return self.send_command("power on")

    def brake_release(self) -> str:
        """Release brakes after power on."""
        return self.send_command("brake release")

    def power_off(self) -> str:
        """Power off the robot arm."""
        return self.send_command("power off")

    def popup(self, message: str) -> str:
        """Show a popup on the teach pendant."""
        return self.send_command(f"popup {message}")

    def close_popup(self) -> str:
        """Close the current popup."""
        return self.send_command("close popup")

    def close_safety_popup(self) -> str:
        """Close a safety popup."""
        return self.send_command("close safety popup")

    def unlock_protective_stop(self) -> str:
        """Unlock after a protective stop event."""
        return self.send_command("unlock protective stop")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_value(response: str, prefix: str) -> str:
        """Extract the value after a 'Key: VALUE' style response."""
        if prefix in response:
            return response.split(prefix, 1)[1].strip()
        return response.strip()


# ---------------------------------------------------------------------------
# Dashboard state poller (background thread)
# ---------------------------------------------------------------------------

class DashboardPoller:
    """
    Periodically polls Dashboard Server for robot/program state.

    Caches the latest state so the main bridge loop can query without
    blocking on a TCP round-trip.
    """

    def __init__(self, dashboard: DashboardClient,
                 poll_interval: float = config.DASHBOARD_POLL_INTERVAL):
        self._dashboard = dashboard
        self._poll_interval = poll_interval
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Cached state (protected by lock)
        self._lock = threading.Lock()
        self._robot_mode: str = ""
        self._program_state: str = ""
        self._safety_mode: str = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background polling thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, name="dashboard-poller", daemon=True
        )
        self._thread.start()
        log.info("Dashboard poller started (interval=%.1fs)", self._poll_interval)

    def stop(self) -> None:
        """Stop the polling thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._poll_interval * 3)
            self._thread = None
        log.info("Dashboard poller stopped")

    # ------------------------------------------------------------------
    # Cached state queries (thread-safe)
    # ------------------------------------------------------------------

    def get_cached_robot_mode(self) -> str:
        with self._lock:
            return self._robot_mode

    def get_cached_program_state(self) -> str:
        with self._lock:
            return self._program_state

    def get_cached_safety_mode(self) -> str:
        with self._lock:
            return self._safety_mode

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        """Poll Dashboard Server at fixed interval."""
        while not self._stop_event.is_set():
            try:
                if self._dashboard.connected:
                    robot_mode = self._dashboard.get_robot_mode()
                    program_state = self._dashboard.get_program_state()
                    safety_mode = self._dashboard.get_safety_mode()

                    with self._lock:
                        self._robot_mode = robot_mode
                        self._program_state = program_state
                        self._safety_mode = safety_mode
            except ConnectionError as exc:
                log.warning("Dashboard poll failed: %s -- attempting reconnect", exc)
                try:
                    self._dashboard.connect()
                except ConnectionError:
                    pass  # will retry next cycle
            except Exception as exc:
                log.error("Dashboard poller unexpected error: %s", exc,
                          exc_info=True)

            self._stop_event.wait(self._poll_interval)
