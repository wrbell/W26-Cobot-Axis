"""
W26 Cobot Axis — Shared test fixtures for bridge daemon unit tests.

Provides:
    - mock_unix_socket / fake_klippy: In-process Unix socketpair + FakeKlippy helper
    - klipper_client: KlipperClient pre-wired to the mock socket
    - bridge / dry_run_bridge: Bridge instances with mocked RTDEClient and KlipperClient
    - bridge_state: Fresh BridgeState instance
"""

import json
import socket

import pytest
from unittest.mock import MagicMock

from bridge import config
from bridge.klipper_client import KlipperClient, ETX
from bridge.rtde_client import RTDEClient
from bridge.bridge_daemon import Bridge, BridgeState


# ---------------------------------------------------------------------------
# FakeKlippy — test helper that speaks the klippy ETX-delimited JSON protocol
# ---------------------------------------------------------------------------

class FakeKlippy:
    """Test helper wrapping the server end of a Unix socketpair.

    Speaks the same ETX-delimited JSON protocol as klippy so that the real
    KlipperClient code is exercised without touching the filesystem.
    """

    def __init__(self, server_socket: socket.socket):
        self.sock = server_socket
        self.sock.settimeout(2.0)
        self._buf = b""

    def recv_request(self, timeout: float = 2.0) -> dict:
        """Read one ETX-delimited JSON request from the client."""
        self.sock.settimeout(timeout)
        while ETX not in self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Client closed connection")
            self._buf += chunk
        msg_raw, self._buf = self._buf.split(ETX, 1)
        return json.loads(msg_raw)

    def send_response(self, msg_id: int, result: dict | None = None) -> None:
        """Send an ETX-delimited JSON response."""
        payload = {"id": msg_id, "result": result if result is not None else {}}
        self.sock.sendall(json.dumps(payload).encode() + ETX)

    def send_error(self, msg_id: int, message: str) -> None:
        """Send an error response."""
        payload = {"id": msg_id, "error": {"message": message}}
        self.sock.sendall(json.dumps(payload).encode() + ETX)

    def send_async_notification(self, method: str, params: dict | None = None) -> None:
        """Send an unsolicited notification (no id field)."""
        payload = {"method": method, "params": params or {}}
        self.sock.sendall(json.dumps(payload).encode() + ETX)

    def send_raw(self, data: bytes) -> None:
        """Send raw bytes (for testing malformed input, split chunks, etc.)."""
        self.sock.sendall(data)

    def close(self):
        self.sock.close()


# ---------------------------------------------------------------------------
# Socket-level fixtures for KlipperClient tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_unix_socket():
    """Create a connected Unix socketpair (client_end, server_end).

    Returns (client_socket, server_socket). Both are closed after the test.
    """
    client_sock, server_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    yield client_sock, server_sock
    client_sock.close()
    server_sock.close()


@pytest.fixture
def fake_klippy(mock_unix_socket):
    """FakeKlippy wrapping the server-side socket."""
    _, server_sock = mock_unix_socket
    return FakeKlippy(server_sock)


@pytest.fixture
def klipper_client(mock_unix_socket):
    """KlipperClient pre-wired to the client end of the socketpair.

    Bypasses the filesystem connect() by injecting the socket directly.
    """
    client_sock, _ = mock_unix_socket
    kc = KlipperClient(socket_path="/tmp/fake_klippy_uds")
    kc._sock = client_sock
    kc._recv_buf = b""
    return kc


# ---------------------------------------------------------------------------
# Bridge-level fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bridge_state():
    """Fresh BridgeState instance."""
    return BridgeState()


def _make_cmd(
    mode=config.MODE_OFF,
    extrusion_rate=0.0,
    tcp_speed=0.0,
    enable=False,
    estop=False,
    home=False,
) -> dict:
    """Helper to build a command dict with safe defaults."""
    return {
        "mode": mode,
        "extrusion_rate": extrusion_rate,
        "tcp_speed": tcp_speed,
        "enable": enable,
        "estop": estop,
        "home": home,
    }


@pytest.fixture
def make_cmd():
    """Expose the _make_cmd helper as a fixture for test functions."""
    return _make_cmd


@pytest.fixture
def bridge():
    """Bridge with mocked RTDEClient and KlipperClient, ready for _tick() testing."""
    b = Bridge(ur_host="127.0.0.1", dry_run=False)
    b.rtde = MagicMock(spec=RTDEClient)
    b.klipper = MagicMock(spec=KlipperClient)
    b.rtde.connected = True
    b.klipper.connected = True
    b.state.ready = True
    return b


@pytest.fixture
def dry_run_bridge():
    """Bridge in dry_run mode with mocked clients."""
    b = Bridge(ur_host="127.0.0.1", dry_run=True)
    b.rtde = MagicMock(spec=RTDEClient)
    b.klipper = MagicMock(spec=KlipperClient)
    b.rtde.connected = True
    b.klipper.connected = True
    b.state.ready = True
    return b
