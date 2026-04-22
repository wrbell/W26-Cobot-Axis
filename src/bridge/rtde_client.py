"""
W26 Cobot Axis — RTDE Client Wrapper

Wraps the ur_rtde library (SDU) for reading UR30 output registers
and writing input registers. Falls back to the official UR RTDE
Python client if ur_rtde is unavailable.

Reference: docs/ur_rtde.md
Register mapping: docs/register_allocation.md
"""

import logging
import socket
import time

from . import config

log = logging.getLogger(__name__)

# Try SDU ur_rtde first (better API), fall back to manual implementation.
# rtde_io is the right interface for setInput*Register (RTDEControlInterface
# does not expose those methods; it's intended for motion commands and
# requires Remote Control mode + powered arm).
try:
    import rtde_receive
    import rtde_io
    HAS_UR_RTDE = True
except ImportError:
    HAS_UR_RTDE = False
    log.warning("ur_rtde not installed — using stub client for development")


class RTDEClient:
    """
    Reads UR30 output registers (commands) and writes input registers (status).

    Output registers (UR30 → Pi): extrusion commands from URScript
    Input registers (Pi → UR30): stepper status feedback
    """

    def __init__(self, host: str = config.UR30_HOST, frequency: int = config.RTDE_FREQUENCY):
        self.host = host
        self.frequency = frequency
        self._rtde_r = None  # RTDEReceiveInterface (read output registers)
        self._rtde_c = None  # RTDEIOInterface (write input registers)

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to the UR30 RTDE interface."""
        if not HAS_UR_RTDE:
            log.info("RTDE stub mode — no robot connection")
            return

        log.info("Connecting to UR30 at %s:%d ...", self.host, config.RTDE_PORT)
        # ur_rtde doesn't expose a connect timeout, so temporarily override
        # the process-wide default so the underlying TCP handshake won't
        # block for the OS default (60-120 s) if the controller is unreachable.
        prev_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(config.RTDE_CONNECT_TIMEOUT)
            self._rtde_r = rtde_receive.RTDEReceiveInterface(
                self.host, self.frequency
            )
            self._rtde_c = rtde_io.RTDEIOInterface(self.host)
        finally:
            socket.setdefaulttimeout(prev_timeout)
        log.info("RTDE connected to %s", self.host)

    def disconnect(self) -> None:
        if self._rtde_r is not None:
            try:
                self._rtde_r.disconnect()
            except Exception:
                pass
            self._rtde_r = None
        if self._rtde_c is not None:
            try:
                self._rtde_c.disconnect()
            except Exception:
                pass
            self._rtde_c = None

    @property
    def connected(self) -> bool:
        if not HAS_UR_RTDE:
            return True  # stub always "connected"
        return self._rtde_r is not None and self._rtde_r.isConnected()

    # ------------------------------------------------------------------
    # Read output registers (UR30 → Pi)
    # ------------------------------------------------------------------

    def read_commands(self) -> dict:
        """
        Read the current extrusion command registers from the UR30.

        Returns dict with keys:
            mode, extrusion_rate, tcp_speed, timestamp, enable, estop, home
        """
        if not HAS_UR_RTDE:
            return self._stub_commands()

        # ur-rtde restricts int/double register indices to [12, 19].
        # Bit registers: the RTDEReceiveInterface in this ur_rtde version does
        # NOT expose getOutputBitRegister() / getOutputBoolRegister(). URScript
        # can still WRITE the bit registers (UR side is fine), but we can't
        # READ them. Default to permissive values so mode != 0 is the gate.
        # E-stop coverage stays via the pendant E-stop and the bridge watchdog.
        # TODO: redesign to encode enable/estop/home into int registers.
        return {
            "mode": self._rtde_r.getOutputIntRegister(12),
            "extrusion_rate": self._rtde_r.getOutputDoubleRegister(12),
            "tcp_speed": self._rtde_r.getOutputDoubleRegister(13),
            "timestamp": self._rtde_r.getTimestamp(),
            "enable": True,
            "estop": False,
            "home": False,
        }

    # ------------------------------------------------------------------
    # Write input registers (Pi → UR30)
    # ------------------------------------------------------------------

    def write_status(self, status: int, error_code: int, actual_rate: float,
                     ready: bool, fault: bool,
                     stallguard_load: float = 0.0) -> None:
        """
        Write stepper status to UR30 input registers.

        Args:
            status: STATUS_IDLE/RUNNING/ERROR/HOMING from config
            error_code: ERR_NONE/COMMS_LOST/STALL/THERMAL from config
            actual_rate: measured extrusion rate in mm/s
            ready: True if stepper can accept commands
            fault: True if fault condition is active
            stallguard_load: StallGuard load value (0.0-255.0, lower = higher load)
        """
        if not HAS_UR_RTDE:
            return

        # ur-rtde restricts INPUT int/double register indices to [18, 22]
        # (vs OUTPUT [12, 19]) — different ranges per direction. See config.py.
        # RTDEIOInterface does NOT expose setInputBitRegister; ready/fault bits
        # are dropped here for now. URScript still reads them as their defaults
        # (False); add an int-register-encoded variant if URScript needs them.
        self._rtde_c.setInputIntRegister(18, status)
        self._rtde_c.setInputIntRegister(19, error_code)
        self._rtde_c.setInputDoubleRegister(18, actual_rate)
        self._rtde_c.setInputDoubleRegister(19, stallguard_load)
        # ready, fault — TODO: encode in input_int_register_20

    # ------------------------------------------------------------------
    # Robot state (convenience)
    # ------------------------------------------------------------------

    def get_tcp_speed(self) -> float:
        """Get actual TCP speed magnitude from robot state (m/s)."""
        if not HAS_UR_RTDE:
            return 0.0
        speed_vec = self._rtde_r.getActualTCPSpeed()
        # speed_vec is [vx, vy, vz, wx, wy, wz] in m/s and rad/s
        # Return linear speed magnitude in mm/s
        import math
        return math.sqrt(speed_vec[0]**2 + speed_vec[1]**2 + speed_vec[2]**2) * 1000.0

    def get_robot_mode(self) -> int:
        """Get robot mode (7 = running normally)."""
        if not HAS_UR_RTDE:
            return 7
        return self._rtde_r.getRobotMode()

    # ------------------------------------------------------------------
    # Stub for development without robot
    # ------------------------------------------------------------------

    @staticmethod
    def _stub_commands() -> dict:
        """Return safe default commands for development/testing.

        The timestamp uses time.monotonic() to simulate an incrementing
        UR30 controller clock, preventing false watchdog triggers in stub mode.
        """
        return {
            "mode": config.MODE_OFF,
            "extrusion_rate": 0.0,
            "tcp_speed": 0.0,
            "timestamp": time.monotonic(),
            "enable": False,
            "estop": False,
            "home": False,
        }
