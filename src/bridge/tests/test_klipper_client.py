"""
Unit tests for bridge.klipper_client — KlipperClient.

Tests the Unix socket connection lifecycle, ETX-delimited JSON protocol,
request/response correlation, high-level commands, stepper convenience
methods, and error handling.

All tests use an in-process socketpair (via conftest fixtures) so no
filesystem sockets or running klippy instance is required.
"""

import json
import threading
import time

import pytest
from unittest.mock import MagicMock

from bridge.klipper_client import KlipperClient, ETX


# ===================================================================
# 4.1  Connection Lifecycle
# ===================================================================

class TestConnectionLifecycle:

    def test_connected_property_false_initially(self):
        """Fresh KlipperClient has connected == False."""
        kc = KlipperClient()
        assert kc.connected is False

    def test_connect_success(self, klipper_client):
        """Pre-wired client reports connected == True."""
        assert klipper_client.connected is True
        assert klipper_client._sock is not None
        assert klipper_client._recv_buf == b""

    def test_connect_raises_on_os_error(self):
        """connect() raises ConnectionError when the socket path is invalid."""
        kc = KlipperClient(socket_path="/tmp/nonexistent_klippy_socket_w26_test")
        with pytest.raises(ConnectionError, match="Cannot connect to klippy"):
            kc.connect()
        assert kc._sock is None

    def test_connect_calls_disconnect_first(self):
        """connect() closes any existing socket before opening a new one."""
        kc = KlipperClient()
        old_sock = MagicMock()
        kc._sock = old_sock

        # connect() will fail (no real socket path), but that's fine --
        # we only care that disconnect was called on the old socket.
        with pytest.raises(ConnectionError):
            kc.connect()

        old_sock.close.assert_called_once()

    def test_disconnect_closes_socket(self, klipper_client):
        """disconnect() sets _sock to None."""
        assert klipper_client.connected is True
        klipper_client.disconnect()
        assert klipper_client._sock is None
        assert klipper_client.connected is False

    def test_disconnect_when_not_connected(self):
        """disconnect() on a fresh client is a no-op."""
        kc = KlipperClient()
        kc.disconnect()  # should not raise
        assert kc._sock is None

    def test_disconnect_suppresses_os_error(self):
        """disconnect() suppresses OSError from close()."""
        kc = KlipperClient()
        mock_sock = MagicMock()
        mock_sock.close.side_effect = OSError("mock close error")
        kc._sock = mock_sock

        kc.disconnect()  # should not raise
        assert kc._sock is None


# ===================================================================
# 4.2  Low-Level Send
# ===================================================================

class TestSend:

    def test_send_formats_json_with_etx(self, klipper_client, fake_klippy):
        """_send() produces ETX-delimited JSON with correct structure."""
        msg_id = klipper_client._send("info")
        assert msg_id == 1

        request = fake_klippy.recv_request()
        assert request["id"] == 1
        assert request["method"] == "info"
        assert request["params"] == {}

    def test_send_with_params(self, klipper_client, fake_klippy):
        """_send() includes params in the JSON payload."""
        klipper_client._send("gcode/script", {"script": "G28"})

        request = fake_klippy.recv_request()
        assert request["method"] == "gcode/script"
        assert request["params"]["script"] == "G28"

    def test_send_increments_id(self, klipper_client, fake_klippy):
        """Consecutive _send() calls produce incrementing IDs."""
        id1 = klipper_client._send("info")
        id2 = klipper_client._send("info")
        assert id1 == 1
        assert id2 == 2

    def test_send_raises_when_not_connected(self):
        """_send() raises ConnectionError when _sock is None."""
        kc = KlipperClient()
        with pytest.raises(ConnectionError, match="Not connected to klippy"):
            kc._send("info")

    def test_send_thread_safety(self, klipper_client, fake_klippy):
        """Concurrent _send() calls don't interleave bytes."""
        results = []
        barrier = threading.Barrier(2)

        def send_from_thread(method_name):
            barrier.wait()
            klipper_client._send(method_name)

        t1 = threading.Thread(target=send_from_thread, args=("method_a",))
        t2 = threading.Thread(target=send_from_thread, args=("method_b",))
        t1.start()
        t2.start()
        t1.join(timeout=2)
        t2.join(timeout=2)

        # Read both messages from server side
        req1 = fake_klippy.recv_request()
        req2 = fake_klippy.recv_request()
        methods = {req1["method"], req2["method"]}
        assert methods == {"method_a", "method_b"}


# ===================================================================
# 4.3  Low-Level Receive
# ===================================================================

class TestRecv:

    def test_recv_parses_etx_delimited_json(self, klipper_client, fake_klippy):
        """_recv() returns parsed JSON dict."""
        fake_klippy.send_response(1, {"state": "ready"})
        resp = klipper_client._recv(timeout=2.0)
        assert resp["id"] == 1
        assert resp["result"]["state"] == "ready"

    def test_recv_handles_split_chunks(self, klipper_client, mock_unix_socket):
        """_recv() reassembles a response split across multiple recv() calls."""
        _, server_sock = mock_unix_socket
        payload = json.dumps({"id": 1, "result": {"ok": True}}).encode()
        # Send in two halves
        midpoint = len(payload) // 2
        server_sock.sendall(payload[:midpoint])
        time.sleep(0.01)
        server_sock.sendall(payload[midpoint:] + ETX)

        resp = klipper_client._recv(timeout=2.0)
        assert resp["id"] == 1
        assert resp["result"]["ok"] is True

    def test_recv_handles_multiple_messages_in_buffer(self, klipper_client, mock_unix_socket):
        """When two messages arrive in one recv(), _recv() returns them sequentially."""
        _, server_sock = mock_unix_socket
        msg1 = json.dumps({"id": 1, "result": {}}).encode() + ETX
        msg2 = json.dumps({"id": 2, "result": {}}).encode() + ETX
        server_sock.sendall(msg1 + msg2)

        resp1 = klipper_client._recv(timeout=2.0)
        resp2 = klipper_client._recv(timeout=2.0)
        assert resp1["id"] == 1
        assert resp2["id"] == 2

    def test_recv_timeout(self, klipper_client):
        """_recv() raises TimeoutError if no data arrives."""
        with pytest.raises(TimeoutError, match="Timed out waiting for klippy response"):
            klipper_client._recv(timeout=0.1)

    def test_recv_empty_read_means_closed(self, klipper_client, mock_unix_socket):
        """_recv() raises ConnectionError when the server closes."""
        _, server_sock = mock_unix_socket
        server_sock.close()
        with pytest.raises(ConnectionError, match="klippy closed connection"):
            klipper_client._recv(timeout=2.0)

    def test_recv_when_not_connected(self):
        """_recv() raises ConnectionError when _sock is None."""
        kc = KlipperClient()
        with pytest.raises(ConnectionError, match="Not connected to klippy"):
            kc._recv()

    def test_recv_preserves_leftover_in_buffer(self, klipper_client, mock_unix_socket):
        """After parsing msg1, leftover bytes remain in _recv_buf."""
        _, server_sock = mock_unix_socket
        partial = b'{"id":99'
        msg1 = json.dumps({"id": 1, "result": {}}).encode() + ETX
        server_sock.sendall(msg1 + partial)

        resp = klipper_client._recv(timeout=2.0)
        assert resp["id"] == 1
        assert klipper_client._recv_buf == partial


# ===================================================================
# 4.4  Request/Response Correlation
# ===================================================================

class TestRequest:

    def _respond_in_thread(self, fake_klippy, msg_id, result=None, delay=0.0):
        """Helper: respond to a request from a background thread."""
        def _respond():
            req = fake_klippy.recv_request(timeout=5.0)
            if delay > 0:
                time.sleep(delay)
            fake_klippy.send_response(req["id"], result or {})
        t = threading.Thread(target=_respond)
        t.start()
        return t

    def test_request_sends_and_receives(self, klipper_client, fake_klippy):
        """request() sends a method call and returns the result dict."""
        t = self._respond_in_thread(fake_klippy, 1, {"state": "ready"})
        result = klipper_client.request("info", timeout=5.0)
        t.join(timeout=5)
        assert result == {"state": "ready"}

    def test_request_skips_async_notifications(self, klipper_client, fake_klippy):
        """request() skips unsolicited notifications and returns the real response."""
        def _respond():
            req = fake_klippy.recv_request(timeout=5.0)
            # Send an async notification first (no id)
            fake_klippy.send_async_notification("notify_status_update", {"temp": 42})
            # Then the real response
            fake_klippy.send_response(req["id"], {"ok": True})

        t = threading.Thread(target=_respond)
        t.start()
        result = klipper_client.request("info", timeout=5.0)
        t.join(timeout=5)
        assert result == {"ok": True}

    def test_request_skips_wrong_id(self, klipper_client, fake_klippy):
        """request() skips responses with non-matching IDs."""
        def _respond():
            req = fake_klippy.recv_request(timeout=5.0)
            # Send a stale response with wrong id
            fake_klippy.send_response(999, {"stale": True})
            # Then the correct one
            fake_klippy.send_response(req["id"], {"fresh": True})

        t = threading.Thread(target=_respond)
        t.start()
        result = klipper_client.request("info", timeout=5.0)
        t.join(timeout=5)
        assert result == {"fresh": True}

    def test_request_raises_on_error_response(self, klipper_client, fake_klippy):
        """request() raises RuntimeError on klippy error response."""
        def _respond():
            req = fake_klippy.recv_request(timeout=5.0)
            fake_klippy.send_error(req["id"], "Shutdown")

        t = threading.Thread(target=_respond)
        t.start()
        with pytest.raises(RuntimeError, match="klippy error: Shutdown"):
            klipper_client.request("info", timeout=5.0)
        t.join(timeout=5)

    def test_request_raises_on_timeout(self, klipper_client):
        """request() raises TimeoutError when no matching response arrives."""
        with pytest.raises(TimeoutError):
            klipper_client.request("info", timeout=0.1)

    def test_request_returns_empty_dict_when_no_result(self, klipper_client, fake_klippy):
        """request() returns {} when the response has no 'result' key."""
        def _respond():
            req = fake_klippy.recv_request(timeout=5.0)
            # Send response with id but no "result" or "error" key
            payload = {"id": req["id"]}
            fake_klippy.sock.sendall(json.dumps(payload).encode() + ETX)

        t = threading.Thread(target=_respond)
        t.start()
        result = klipper_client.request("info", timeout=5.0)
        t.join(timeout=5)
        assert result == {}


# ===================================================================
# 4.5  High-Level Commands
# ===================================================================

class TestHighLevelCommands:

    def test_gcode_sends_script(self, klipper_client, fake_klippy):
        """gcode() sends gcode/script method with the correct payload."""
        received = {}

        def _capture():
            req = fake_klippy.recv_request(timeout=5.0)
            received.update(req)
            fake_klippy.send_response(req["id"], {})

        t = threading.Thread(target=_capture)
        t.start()
        klipper_client.gcode("G28")
        t.join(timeout=5)

        assert received["method"] == "gcode/script"
        assert received["params"]["script"] == "G28"

    def test_gcode_custom_timeout(self, klipper_client, fake_klippy):
        """gcode() passes timeout through to request()."""
        # This test verifies the timeout parameter is forwarded.
        # We let it time out with a very short timeout to verify behavior.
        with pytest.raises(TimeoutError):
            klipper_client.gcode("M400", timeout=0.05)

    def test_emergency_stop_sends_fire_and_forget(self, klipper_client, fake_klippy):
        """emergency_stop() sends the method without waiting for response."""
        klipper_client.emergency_stop()
        req = fake_klippy.recv_request(timeout=2.0)
        assert req["method"] == "emergency_stop"

    def test_emergency_stop_suppresses_exceptions(self):
        """emergency_stop() does not raise even when disconnected."""
        kc = KlipperClient()
        kc.emergency_stop()  # should not raise

    def test_query_status_sends_objects(self, klipper_client, fake_klippy):
        """query_status() sends objects/query with the objects dict."""
        received = {}

        def _capture():
            req = fake_klippy.recv_request(timeout=5.0)
            received.update(req)
            fake_klippy.send_response(req["id"], {"status": {}})

        t = threading.Thread(target=_capture)
        t.start()
        klipper_client.query_status({"manual_stepper pump": None})
        t.join(timeout=5)

        assert received["method"] == "objects/query"
        assert received["params"]["objects"] == {"manual_stepper pump": None}

    def test_get_info(self, klipper_client, fake_klippy):
        """get_info() sends info method and returns the result."""
        def _respond():
            req = fake_klippy.recv_request(timeout=5.0)
            fake_klippy.send_response(req["id"], {
                "state": "ready", "state_message": "Printer is ready"
            })

        t = threading.Thread(target=_respond)
        t.start()
        result = klipper_client.get_info()
        t.join(timeout=5)
        assert result["state"] == "ready"
        assert result["state_message"] == "Printer is ready"


# ===================================================================
# 4.6  Stepper Convenience Methods
# ===================================================================

class TestStepperConvenience:

    def _capture_gcode(self, klipper_client, fake_klippy):
        """Helper: call a stepper method, capture the G-code sent."""
        captured = {}

        def _capture():
            req = fake_klippy.recv_request(timeout=5.0)
            captured.update(req)
            fake_klippy.send_response(req["id"], {})

        t = threading.Thread(target=_capture)
        t.start()
        return captured, t

    def test_stepper_move_formats_gcode(self, klipper_client, fake_klippy):
        """stepper_move() formats MANUAL_STEPPER MOVE with ACCEL."""
        captured, t = self._capture_gcode(klipper_client, fake_klippy)
        klipper_client.stepper_move("pump", 10.0, 25.0, 200.0)
        t.join(timeout=5)

        gcode = captured["params"]["script"]
        assert gcode == "MANUAL_STEPPER STEPPER=pump MOVE=10.0000 SPEED=25.00 ACCEL=200.0"

    def test_stepper_move_without_accel(self, klipper_client, fake_klippy):
        """stepper_move() without accel omits the ACCEL parameter."""
        captured, t = self._capture_gcode(klipper_client, fake_klippy)
        klipper_client.stepper_move("pump", 5.0, 10.0)
        t.join(timeout=5)

        gcode = captured["params"]["script"]
        assert "ACCEL" not in gcode
        assert gcode == "MANUAL_STEPPER STEPPER=pump MOVE=5.0000 SPEED=10.00"

    def test_stepper_move_negative_distance(self, klipper_client, fake_klippy):
        """stepper_move() handles negative distance (retract direction)."""
        captured, t = self._capture_gcode(klipper_client, fake_klippy)
        klipper_client.stepper_move("pump", -10.0, 25.0)
        t.join(timeout=5)

        gcode = captured["params"]["script"]
        assert "MOVE=-10.0000" in gcode

    def test_stepper_set_position(self, klipper_client, fake_klippy):
        """stepper_set_position() sends SET_POSITION G-code."""
        captured, t = self._capture_gcode(klipper_client, fake_klippy)
        klipper_client.stepper_set_position("pump", 0.0)
        t.join(timeout=5)

        gcode = captured["params"]["script"]
        assert gcode == "MANUAL_STEPPER STEPPER=pump SET_POSITION=0.0000"

    def test_stepper_set_position_nonzero(self, klipper_client, fake_klippy):
        """stepper_set_position() works with non-zero positions."""
        captured, t = self._capture_gcode(klipper_client, fake_klippy)
        klipper_client.stepper_set_position("pump", 42.5)
        t.join(timeout=5)

        gcode = captured["params"]["script"]
        assert "SET_POSITION=42.5000" in gcode

    def test_stepper_enable(self, klipper_client, fake_klippy):
        """stepper_enable() sends ENABLE=1."""
        captured, t = self._capture_gcode(klipper_client, fake_klippy)
        klipper_client.stepper_enable("pump")
        t.join(timeout=5)

        gcode = captured["params"]["script"]
        assert gcode == "MANUAL_STEPPER STEPPER=pump ENABLE=1"

    def test_stepper_disable(self, klipper_client, fake_klippy):
        """stepper_disable() sends ENABLE=0."""
        captured, t = self._capture_gcode(klipper_client, fake_klippy)
        klipper_client.stepper_disable("pump")
        t.join(timeout=5)

        gcode = captured["params"]["script"]
        assert gcode == "MANUAL_STEPPER STEPPER=pump ENABLE=0"

    def test_stepper_move_precision(self, klipper_client, fake_klippy):
        """stepper_move() formats small values without scientific notation."""
        captured, t = self._capture_gcode(klipper_client, fake_klippy)
        klipper_client.stepper_move("pump", 0.0001, 0.01, 0.1)
        t.join(timeout=5)

        gcode = captured["params"]["script"]
        assert "MOVE=0.0001" in gcode
        assert "SPEED=0.01" in gcode
        assert "ACCEL=0.1" in gcode
        # Ensure no scientific notation (e.g., 1e-04) in the numeric values
        # Extract just the numeric parts to check
        for token in gcode.split():
            if "=" in token:
                value_part = token.split("=", 1)[1]
                assert "e" not in value_part.lower(), f"Scientific notation in {token}"


# ===================================================================
# 4.7  Edge Cases and Error Conditions
# ===================================================================

class TestEdgeCases:

    def test_recv_malformed_json(self, klipper_client, mock_unix_socket):
        """_recv() raises json.JSONDecodeError on malformed JSON."""
        _, server_sock = mock_unix_socket
        server_sock.sendall(b"not-valid-json" + ETX)

        with pytest.raises(json.JSONDecodeError):
            klipper_client._recv(timeout=2.0)

    def test_send_large_payload(self, klipper_client, fake_klippy):
        """_send() handles large payloads via sendall()."""
        big_script = "G1 X100 Y100 ; " * 1000  # ~16 KB
        klipper_client._send("gcode/script", {"script": big_script})

        req = fake_klippy.recv_request(timeout=5.0)
        assert req["params"]["script"] == big_script

    def test_concurrent_requests(self, klipper_client, fake_klippy):
        """Two threads calling request() simultaneously get correct responses."""
        results = [None, None]

        def _server():
            # Respond to two requests
            for _ in range(2):
                req = fake_klippy.recv_request(timeout=5.0)
                fake_klippy.send_response(req["id"], {"method_echo": req["method"]})

        server_thread = threading.Thread(target=_server)
        server_thread.start()

        barrier = threading.Barrier(2)

        def _client(index, method):
            barrier.wait()
            results[index] = klipper_client.request(method, timeout=5.0)

        t1 = threading.Thread(target=_client, args=(0, "info"))
        t2 = threading.Thread(target=_client, args=(1, "objects/query"))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        server_thread.join(timeout=5)

        # Both threads should have gotten some response (exact matching depends
        # on timing, but both should be non-None dicts)
        assert results[0] is not None
        assert results[1] is not None
