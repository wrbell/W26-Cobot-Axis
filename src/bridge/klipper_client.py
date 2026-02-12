"""
W26 Cobot Axis — Klipper Unix Socket Client

Communicates with klippy via /tmp/klippy_uds.
Protocol: newline-delimited JSON terminated by \\x03 (ETX).

Reference: tech_docs/Klipper/klipper_protocols.md, Sections 2 & 6.
"""

import json
import logging
import socket
import threading
import time

log = logging.getLogger(__name__)

ETX = b"\x03"


class KlipperClient:
    """Persistent connection to the klippy Unix domain socket."""

    def __init__(self, socket_path: str = "/tmp/klippy_uds"):
        self.socket_path = socket_path
        self._sock: socket.socket | None = None
        self._id_counter = 0
        self._lock = threading.Lock()
        self._recv_buf = b""

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to klippy. Raises ConnectionError on failure."""
        self.disconnect()
        try:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect(self.socket_path)
            self._recv_buf = b""
            log.info("Connected to klippy at %s", self.socket_path)
        except OSError as exc:
            self._sock = None
            raise ConnectionError(f"Cannot connect to klippy: {exc}") from exc

    def disconnect(self) -> None:
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
    # Low-level send / receive
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    def _send(self, method: str, params: dict | None = None) -> int:
        """Send a request and return its ID."""
        if self._sock is None:
            raise ConnectionError("Not connected to klippy")
        msg_id = self._next_id()
        payload = {"id": msg_id, "method": method, "params": params or {}}
        raw = json.dumps(payload).encode() + ETX
        with self._lock:
            self._sock.sendall(raw)
        return msg_id

    def _recv(self, timeout: float = 5.0) -> dict:
        """Read the next ETX-delimited JSON response."""
        if self._sock is None:
            raise ConnectionError("Not connected to klippy")
        self._sock.settimeout(timeout)
        while ETX not in self._recv_buf:
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                raise TimeoutError("Timed out waiting for klippy response")
            if not chunk:
                raise ConnectionError("klippy closed connection")
            self._recv_buf += chunk
        msg_raw, self._recv_buf = self._recv_buf.split(ETX, 1)
        return json.loads(msg_raw)

    def request(self, method: str, params: dict | None = None,
                timeout: float = 5.0) -> dict:
        """Send a request and wait for the matching response."""
        msg_id = self._send(method, params)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"No response for {method} (id={msg_id})")
            resp = self._recv(timeout=remaining)
            if resp.get("id") == msg_id:
                if "error" in resp:
                    raise RuntimeError(
                        f"klippy error: {resp['error'].get('message', resp['error'])}"
                    )
                return resp.get("result", {})
            # else: async notification — skip for now

    # ------------------------------------------------------------------
    # High-level commands
    # ------------------------------------------------------------------

    def gcode(self, script: str, timeout: float = 10.0) -> dict:
        """Execute a G-code script."""
        return self.request("gcode/script", {"script": script}, timeout=timeout)

    def emergency_stop(self) -> None:
        """Immediately halt the printer."""
        try:
            self._send("emergency_stop")
        except Exception:
            pass  # best-effort

    def query_status(self, objects: dict) -> dict:
        """
        Query Klipper status objects.

        Example:
            query_status({"manual_stepper pump": None, "tmc2209 manual_stepper pump": None})
        """
        return self.request("objects/query", {"objects": objects})

    def get_info(self) -> dict:
        """Get klippy server info and state."""
        return self.request("info")

    # ------------------------------------------------------------------
    # Stepper convenience methods
    # ------------------------------------------------------------------

    def stepper_move(self, name: str, distance: float, speed: float,
                     accel: float | None = None) -> dict:
        """Send a MANUAL_STEPPER MOVE command."""
        cmd = f"MANUAL_STEPPER STEPPER={name} MOVE={distance:.4f} SPEED={speed:.2f}"
        if accel is not None:
            cmd += f" ACCEL={accel:.1f}"
        return self.gcode(cmd)

    def stepper_set_position(self, name: str, position: float = 0.0) -> dict:
        """Reset the stepper's position reference."""
        return self.gcode(
            f"MANUAL_STEPPER STEPPER={name} SET_POSITION={position:.4f}"
        )

    def stepper_enable(self, name: str) -> dict:
        return self.gcode(f"MANUAL_STEPPER STEPPER={name} ENABLE=1")

    def stepper_disable(self, name: str) -> dict:
        return self.gcode(f"MANUAL_STEPPER STEPPER={name} ENABLE=0")
