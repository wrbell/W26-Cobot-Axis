"""
Unit tests for W26 bridge Dashboard Server client.

Tests DashboardClient connection, command/response protocol, status queries,
control commands, and DashboardPoller caching.
"""

import socket
import threading

import pytest
from unittest.mock import MagicMock

from bridge.dashboard_client import DashboardClient, DashboardPoller


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeDashboardServer:
    """Minimal Dashboard Server for testing.

    Accepts a TCP connection, sends a banner, then responds to each
    newline-terminated command with a canned response.
    """

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.default_response = "OK"
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self._thread = None
        self._conn = None

    def start(self):
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        self._conn, _ = self.server.accept()
        f = self._conn.makefile("rw", buffering=1)
        f.write("Connected: UR30\n")
        f.flush()
        try:
            while True:
                line = f.readline()
                if not line:
                    break
                cmd = line.strip()
                resp = self.responses.get(cmd, self.default_response)
                f.write(resp + "\n")
                f.flush()
        except (OSError, BrokenPipeError):
            pass

    def stop(self):
        if self._conn:
            self._conn.close()
        self.server.close()


@pytest.fixture
def fake_server():
    server = FakeDashboardServer(responses={
        "robotmode": "Robotmode: RUNNING",
        "programState": "PLAYING",
        "running": "Program running: true",
        "safetymode": "Safetymode: NORMAL",
        "get robot model": "UR30",
        "get serial number": "2023301234",
        "PolyscopeVersion": "5.14.0",
        "is in remote control": "true",
        "play": "Starting program",
        "stop": "Stopped",
        "power on": "Powering on",
        "brake release": "Brake releasing",
    })
    server.start()
    yield server
    server.stop()


@pytest.fixture
def client(fake_server):
    c = DashboardClient("127.0.0.1", port=fake_server.port, timeout=2.0)
    c.connect()
    yield c
    c.disconnect()


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

class TestConnection:
    def test_connect_reads_banner(self, client):
        assert client.connected is True
        assert "UR30" in client._banner

    def test_disconnect(self, client):
        client.disconnect()
        assert client.connected is False

    def test_double_disconnect_safe(self, client):
        client.disconnect()
        client.disconnect()

    def test_connect_to_bad_host_raises(self):
        c = DashboardClient("127.0.0.1", port=1, timeout=0.1)
        with pytest.raises(ConnectionError):
            c.connect()

    def test_reconnect(self, fake_server):
        c = DashboardClient("127.0.0.1", port=fake_server.port, timeout=2.0)
        c.connect()
        c.disconnect()
        # Can't reconnect to same single-accept server, but disconnect worked
        assert c.connected is False


# ---------------------------------------------------------------------------
# Command/Response
# ---------------------------------------------------------------------------

class TestSendCommand:
    def test_basic_command(self, client):
        resp = client.send_command("robotmode")
        assert "RUNNING" in resp

    def test_not_connected_raises(self):
        c = DashboardClient("127.0.0.1", port=1)
        with pytest.raises(ConnectionError, match="Not connected"):
            c.send_command("robotmode")


# ---------------------------------------------------------------------------
# Status queries
# ---------------------------------------------------------------------------

class TestStatusQueries:
    def test_get_robot_mode(self, client):
        assert client.get_robot_mode() == "RUNNING"

    def test_get_program_state(self, client):
        assert "PLAYING" in client.get_program_state()

    def test_is_running(self, client):
        assert client.is_running() is True

    def test_get_safety_mode(self, client):
        assert client.get_safety_mode() == "NORMAL"

    def test_get_robot_model(self, client):
        assert "UR30" in client.get_robot_model()

    def test_get_serial_number(self, client):
        assert "2023301234" in client.get_serial_number()

    def test_get_polyscope_version(self, client):
        assert "5.14" in client.get_polyscope_version()

    def test_is_in_remote_control(self, client):
        assert client.is_in_remote_control() is True


# ---------------------------------------------------------------------------
# Control commands
# ---------------------------------------------------------------------------

class TestControlCommands:
    def test_play(self, client):
        resp = client.play()
        assert "Starting" in resp

    def test_stop(self, client):
        resp = client.stop()
        assert "Stopped" in resp

    def test_power_on(self, client):
        resp = client.power_on()
        assert "Powering" in resp

    def test_brake_release(self, client):
        resp = client.brake_release()
        assert "Brake" in resp

    def test_load_program(self, client):
        resp = client.load_program("/programs/test.urp")
        assert resp  # returns default "OK"


# ---------------------------------------------------------------------------
# _parse_value helper
# ---------------------------------------------------------------------------

class TestParseValue:
    def test_with_prefix(self):
        assert DashboardClient._parse_value("Robotmode: RUNNING", "Robotmode:") == "RUNNING"

    def test_without_prefix(self):
        assert DashboardClient._parse_value("PLAYING", "Robotmode:") == "PLAYING"


# ---------------------------------------------------------------------------
# DashboardPoller
# ---------------------------------------------------------------------------

class TestDashboardPoller:
    def test_cached_values_default_empty(self):
        dc = MagicMock(spec=DashboardClient)
        poller = DashboardPoller(dc, poll_interval=0.1)
        assert poller.get_cached_robot_mode() == ""
        assert poller.get_cached_program_state() == ""
        assert poller.get_cached_safety_mode() == ""

    def test_start_stop(self):
        dc = MagicMock(spec=DashboardClient)
        dc.connected = True
        dc.get_robot_mode.return_value = "RUNNING"
        dc.get_program_state.return_value = "PLAYING"
        dc.get_safety_mode.return_value = "NORMAL"

        poller = DashboardPoller(dc, poll_interval=0.05)
        poller.start()
        # Give it time to poll
        import time
        time.sleep(0.15)
        poller.stop()

        assert poller.get_cached_robot_mode() == "RUNNING"
        assert poller.get_cached_program_state() == "PLAYING"

    def test_double_start_safe(self):
        dc = MagicMock(spec=DashboardClient)
        dc.connected = False
        poller = DashboardPoller(dc, poll_interval=0.05)
        poller.start()
        poller.start()  # should not create second thread
        poller.stop()
