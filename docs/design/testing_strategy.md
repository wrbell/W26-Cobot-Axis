# Testing Strategy — W26 Cobot Axis Bridge Daemon

**Project:** W26 Cobot Axis
**Author:** Willem (Software/EE)
**Date:** 2026-02-12
**Status:** Design

---

## Table of Contents

1. [Overview](#1-overview)
2. [Directory Structure and Conventions](#2-directory-structure-and-conventions)
3. [Test Framework and Tooling](#3-test-framework-and-tooling)
4. [Unit Tests: klipper_client.py](#4-unit-tests-klipper_clientpy)
5. [Unit Tests: rtde_client.py](#5-unit-tests-rtde_clientpy)
6. [Unit Tests: bridge_daemon.py](#6-unit-tests-bridge_daemonpy)
7. [Integration Tests: URSim Setup](#7-integration-tests-ursim-setup)
8. [Integration Tests: Bridge + URSim](#8-integration-tests-bridge--ursim)
9. [Coverage Targets and Hard-to-Test Areas](#9-coverage-targets-and-hard-to-test-areas)
10. [CI Pipeline Design](#10-ci-pipeline-design)

---

## 1. Overview

The bridge daemon translates UR30 robot commands (via RTDE) into Klipper stepper motor commands (via Unix socket). Testing must cover the full chain while the project has no access to physical hardware during development. The strategy is organized in three tiers:

| Tier | Scope | Dependencies | Runs In CI |
|------|-------|-------------|------------|
| Unit tests | Single module, mocked I/O | None (pure Python + mocks) | Yes, always |
| Integration tests (URSim) | Bridge + real RTDE against simulator | Docker (URSim container) | Yes, with Docker runner |
| Hardware tests | Full end-to-end with physical UR30, Pi, SKR Pico | Lab hardware | No (Phase 4 manual) |

This document covers tiers 1 and 2 only. Hardware tests are out of scope here and will be defined during Phase 4.

### Modules Under Test

| Module | LOC | Key Responsibilities | External Dependencies |
|--------|-----|---------------------|-----------------------|
| `src/bridge/klipper_client.py` | 164 | Unix socket connection, ETX-delimited JSON protocol, request/response correlation, stepper convenience methods | Unix domain socket (`/tmp/klippy_uds`) |
| `src/bridge/rtde_client.py` | 163 | RTDE register read/write, stub fallback mode, connection lifecycle | `rtde_receive`, `rtde_control` (C++ library with Python bindings) |
| `src/bridge/bridge_daemon.py` | 336 | Main loop, command translation, e-stop, homing, mode switching, reconnection, status reporting | Both of the above |
| `src/bridge/config.py` | 100 | Constants and register mappings | None (pure data) |

---

## 2. Directory Structure and Conventions

```
W26-Cobot-Axis/
  src/
    bridge/
      __init__.py
      __main__.py
      bridge_daemon.py
      config.py
      klipper_client.py
      rtde_client.py
  tests/
    __init__.py
    conftest.py                    # Shared fixtures (mock sockets, fake Klipper server, etc.)
    unit/
      __init__.py
      test_klipper_client.py       # KlipperClient unit tests
      test_rtde_client.py          # RTDEClient unit tests
      test_bridge_daemon.py        # Bridge + BridgeState unit tests
      test_config.py               # Config sanity checks (optional but cheap)
    integration/
      __init__.py
      conftest.py                  # URSim fixtures (Docker lifecycle, wait-for-ready)
      test_bridge_ursim.py         # Bridge + URSim integration tests
    docker/
      docker-compose.ursim.yml    # URSim Docker Compose file for integration tests
```

### Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>` (e.g., `TestKlipperClient`)
- Test functions: `test_<behavior_under_test>` (e.g., `test_connect_raises_on_missing_socket`)
- Fixtures: descriptive lowercase with underscores (e.g., `mock_klipper_socket`, `ursim_container`)

### Running Tests

```bash
# All unit tests (fast, no Docker)
pytest tests/unit/ -v

# Integration tests (requires Docker)
pytest tests/integration/ -v --ursim

# Full suite with coverage
pytest tests/ -v --cov=src/bridge --cov-report=html

# Only tests matching a keyword
pytest tests/ -k "estop" -v
```

---

## 3. Test Framework and Tooling

### Core Dependencies

| Tool | Version | Purpose |
|------|---------|---------|
| `pytest` | >= 8.0 | Test runner, fixtures, parametrize, markers |
| `pytest-cov` | >= 5.0 | Coverage measurement and reporting |
| `pytest-timeout` | >= 2.2 | Per-test timeouts (critical for socket tests) |
| `pytest-mock` | >= 3.14 | `mocker` fixture wrapping `unittest.mock` |

### Optional / Integration Dependencies

| Tool | Purpose |
|------|---------|
| `docker` / `docker compose` | URSim container lifecycle |
| `pytest-docker` or custom fixture | Manage Docker containers from pytest |
| `ur-rtde` | Real RTDE client for integration tests |

### `conftest.py` — Shared Fixtures

The top-level `tests/conftest.py` provides fixtures reused across all test modules:

- **`mock_unix_socket`**: A `socketpair(AF_UNIX)` that creates a connected pair of Unix sockets. One end acts as the "client" (KlipperClient connects to it) and the other as the "server" (test code sends/receives). This avoids filesystem socket creation entirely.
- **`fake_klippy_server`**: A helper class that wraps the server-side socket, implements the ETX-delimited JSON protocol, and provides methods like `expect_request(method)` and `send_response(id, result)`.
- **`mock_rtde_receive`** / **`mock_rtde_control`**: Mock objects mimicking the `rtde_receive.RTDEReceiveInterface` and `rtde_control.RTDEControlInterface` classes.
- **`bridge_state`**: A fresh `BridgeState()` instance.

---

## 4. Unit Tests: `klipper_client.py`

### Mocking Strategy

The KlipperClient communicates over a Unix domain socket using an ETX-delimited JSON protocol. The mocking approach uses Python's `socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)` to create an in-process connected socket pair. The test controls the "server" end and KlipperClient uses the "client" end. This tests the real socket I/O code path without touching the filesystem.

**How to inject the mock socket:** Patch `socket.socket` so that `KlipperClient.connect()` returns the pre-connected test socket instead of connecting to `/tmp/klippy_uds`. Alternatively, after calling `client = KlipperClient(...)`, directly assign `client._sock = client_end` and set `client._recv_buf = b""`. The latter is simpler and avoids patching the `connect()` call.

**Fake klippy server helper:**

```
class FakeKlippy:
    """Test helper that speaks the klippy ETX-delimited JSON protocol."""

    def __init__(self, server_socket):
        self.sock = server_socket

    def recv_request(self, timeout=2.0) -> dict:
        """Read one ETX-delimited JSON request from the client."""

    def send_response(self, msg_id: int, result: dict) -> None:
        """Send an ETX-delimited JSON response."""

    def send_error(self, msg_id: int, message: str) -> None:
        """Send an error response."""

    def send_async_notification(self, method: str, params: dict) -> None:
        """Send an unsolicited notification (no id field)."""
```

### Test Cases

#### 4.1 Connection Lifecycle

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_connect_success` | Patch `socket.socket` to return a pre-connected mock; call `connect()` | `connected` property returns `True`, `_sock` is set, `_recv_buf` is empty |
| `test_connect_raises_on_os_error` | Patch `socket.socket.connect` to raise `OSError` | `connect()` raises `ConnectionError`, `_sock` is `None` |
| `test_connect_calls_disconnect_first` | Set `_sock` to a mock, then call `connect()` | `close()` is called on the old socket before creating a new one |
| `test_disconnect_closes_socket` | Connect, then call `disconnect()` | `_sock` is `None`, `connected` returns `False` |
| `test_disconnect_when_not_connected` | Call `disconnect()` without prior `connect()` | No exception, no-op |
| `test_disconnect_suppresses_os_error` | Set `_sock` to a mock whose `close()` raises `OSError` | No exception raised |
| `test_connected_property_false_initially` | Fresh `KlipperClient()` | `connected` is `False` |

#### 4.2 Low-Level Send

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_send_formats_json_with_etx` | Call `_send("info")`, read from server end | Server receives `{"id": 1, "method": "info", "params": {}}` + `\x03` |
| `test_send_with_params` | Call `_send("gcode/script", {"script": "G28"})` | Params included in JSON payload |
| `test_send_increments_id` | Call `_send()` twice | IDs are 1 and 2 respectively |
| `test_send_raises_when_not_connected` | Call `_send()` with `_sock = None` | Raises `ConnectionError("Not connected to klippy")` |
| `test_send_thread_safety` | Call `_send()` from two threads simultaneously | No interleaved bytes on the wire (lock serializes sends) |

#### 4.3 Low-Level Receive

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_recv_parses_etx_delimited_json` | Server sends `{"id":1,"result":{}}` + ETX | `_recv()` returns `{"id": 1, "result": {}}` |
| `test_recv_handles_split_chunks` | Server sends response in two separate `send()` calls (split mid-JSON) | `_recv()` reassembles and returns complete JSON |
| `test_recv_handles_multiple_messages_in_buffer` | Server sends two responses in one `send()` call | First `_recv()` returns first message, second `_recv()` returns second (from buffer) |
| `test_recv_timeout` | Server sends nothing | Raises `TimeoutError("Timed out waiting for klippy response")` |
| `test_recv_empty_read_means_closed` | Server closes its end | Raises `ConnectionError("klippy closed connection")` |
| `test_recv_when_not_connected` | `_sock` is `None` | Raises `ConnectionError("Not connected to klippy")` |
| `test_recv_preserves_leftover_in_buffer` | Server sends `msg1\x03partial_msg2` | `_recv()` returns msg1, `_recv_buf` contains `partial_msg2` |

#### 4.4 Request/Response Correlation

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_request_sends_and_receives` | Call `request("info")`, server responds with matching id | Returns the `result` dict |
| `test_request_skips_async_notifications` | Server sends a notification (no id) then the real response | Returns the response, notification is silently skipped |
| `test_request_skips_wrong_id` | Server sends response with wrong id, then correct id | Returns the correct response |
| `test_request_raises_on_error_response` | Server sends `{"id": 1, "error": {"message": "Shutdown"}}` | Raises `RuntimeError("klippy error: Shutdown")` |
| `test_request_raises_on_timeout` | Server never sends matching response | Raises `TimeoutError` after deadline |
| `test_request_returns_empty_dict_when_no_result` | Server sends `{"id": 1}` (no "result" key) | Returns `{}` |

#### 4.5 High-Level Commands

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_gcode_sends_script` | Call `gcode("G28")` | Server receives `gcode/script` method with `{"script": "G28"}` |
| `test_gcode_custom_timeout` | Call `gcode("M400", timeout=30.0)` | Timeout passed through to `request()` |
| `test_emergency_stop_sends_fire_and_forget` | Call `emergency_stop()` | Server receives `emergency_stop` method; no response expected |
| `test_emergency_stop_suppresses_exceptions` | Disconnect before calling `emergency_stop()` | No exception raised |
| `test_query_status_sends_objects` | Call `query_status({"manual_stepper pump": None})` | Server receives `objects/query` with correct objects dict |
| `test_get_info` | Call `get_info()` | Server receives `info` method, returns result |

#### 4.6 Stepper Convenience Methods

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_stepper_move_formats_gcode` | Call `stepper_move("pump", 10.0, 25.0, 200.0)` | G-code sent: `MANUAL_STEPPER STEPPER=pump MOVE=10.0000 SPEED=25.00 ACCEL=200.0` |
| `test_stepper_move_without_accel` | Call `stepper_move("pump", 5.0, 10.0)` | G-code has no ACCEL parameter |
| `test_stepper_move_negative_distance` | Call `stepper_move("pump", -10.0, 25.0)` | G-code: `MOVE=-10.0000` (negative distance for retract direction) |
| `test_stepper_set_position` | Call `stepper_set_position("pump", 0.0)` | G-code: `MANUAL_STEPPER STEPPER=pump SET_POSITION=0.0000` |
| `test_stepper_set_position_nonzero` | Call `stepper_set_position("pump", 42.5)` | G-code: `SET_POSITION=42.5000` |
| `test_stepper_enable` | Call `stepper_enable("pump")` | G-code: `MANUAL_STEPPER STEPPER=pump ENABLE=1` |
| `test_stepper_disable` | Call `stepper_disable("pump")` | G-code: `MANUAL_STEPPER STEPPER=pump ENABLE=0` |
| `test_stepper_move_precision` | Call with very small values (0.0001 mm, 0.01 mm/s) | Values formatted correctly, no scientific notation |

#### 4.7 Edge Cases and Error Conditions

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_recv_malformed_json` | Server sends `not-json\x03` | Raises `json.JSONDecodeError` (or wrapping exception) |
| `test_send_large_payload` | Send a very long G-code script (e.g., 10 KB) | Sent without error; `sendall()` handles fragmentation |
| `test_concurrent_requests` | Two threads call `request()` simultaneously | Both get correct responses (lock prevents interleaving) |

---

## 5. Unit Tests: `rtde_client.py`

### Mocking Strategy

The RTDEClient wraps the `ur_rtde` C++ library (`rtde_receive` and `rtde_control` modules). The mocking approach depends on whether `ur_rtde` is installed:

1. **Stub mode (default for CI):** When `ur_rtde` is not importable, `HAS_UR_RTDE` is `False` and the client returns safe defaults. These tests verify the stub behavior and require no mocking.

2. **Mocked `ur_rtde` mode:** Patch `rtde_receive` and `rtde_control` at the module level using `unittest.mock.patch` to inject mock `RTDEReceiveInterface` and `RTDEControlInterface` objects. This tests the real-library code path without needing the actual C++ bindings.

**Patching approach for mocked mode:** Since the imports happen at module load time with a `try/except`, the test must patch `rtde_client.HAS_UR_RTDE = True` and inject mocks for `rtde_client.rtde_receive` and `rtde_client.rtde_control` before instantiating `RTDEClient`.

### Test Cases

#### 5.1 Stub Mode (No `ur_rtde` Installed)

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_stub_connect_succeeds` | Call `connect()` in stub mode | No exception, logs "RTDE stub mode" |
| `test_stub_connected_returns_true` | Check `connected` in stub mode | Returns `True` (stub is always "connected") |
| `test_stub_disconnect_no_op` | Call `disconnect()` in stub mode | No exception |
| `test_stub_read_commands_returns_safe_defaults` | Call `read_commands()` | Returns dict with `mode=0`, `extrusion_rate=0.0`, `tcp_speed=0.0`, `enable=False`, `estop=False`, `home=False` |
| `test_stub_write_status_no_op` | Call `write_status(...)` | No exception, no effect |
| `test_stub_get_tcp_speed_returns_zero` | Call `get_tcp_speed()` | Returns `0.0` |
| `test_stub_get_robot_mode_returns_running` | Call `get_robot_mode()` | Returns `7` (running normally) |

#### 5.2 Connection Lifecycle (Mocked `ur_rtde`)

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_connect_creates_interfaces` | Call `connect()` with mocked ur_rtde | `RTDEReceiveInterface` created with `(host, frequency)`, `RTDEControlInterface` created with `(host,)` |
| `test_connect_uses_config_defaults` | Create `RTDEClient()` with no args, call `connect()` | Uses `config.UR30_HOST` and `config.RTDE_FREQUENCY` |
| `test_connect_uses_custom_host` | Create `RTDEClient(host="10.0.0.1")`, call `connect()` | Interfaces created with `"10.0.0.1"` |
| `test_disconnect_calls_both_interfaces` | Connect then disconnect | Both `_rtde_r.disconnect()` and `_rtde_c.disconnect()` called |
| `test_disconnect_sets_none` | Call `disconnect()` | `_rtde_r` and `_rtde_c` are both `None` |
| `test_disconnect_suppresses_exceptions` | Mock `disconnect()` to raise | No exception propagated |
| `test_disconnect_when_not_connected` | Call `disconnect()` without connecting | No exception |
| `test_connected_property_true` | Mock `isConnected()` to return `True` | `connected` returns `True` |
| `test_connected_property_false_when_not_connected` | Mock `isConnected()` to return `False` | `connected` returns `False` |
| `test_connected_false_when_rtde_r_is_none` | Set `_rtde_r = None` | `connected` returns `False` |

#### 5.3 Register Read (Mocked `ur_rtde`)

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_read_commands_reads_all_registers` | Mock all `getOutput*Register` methods | Returned dict has keys: `mode`, `extrusion_rate`, `tcp_speed`, `enable`, `estop`, `home` |
| `test_read_commands_mode_register` | Mock `getOutputIntRegister(0)` to return `1` | `cmd["mode"]` is `1` |
| `test_read_commands_extrusion_rate` | Mock `getOutputDoubleRegister(0)` to return `25.5` | `cmd["extrusion_rate"]` is `25.5` |
| `test_read_commands_tcp_speed` | Mock `getOutputDoubleRegister(1)` to return `100.0` | `cmd["tcp_speed"]` is `100.0` |
| `test_read_commands_bool_registers` | Mock bit registers to return `True`/`False` | `enable`, `estop`, `home` match mocked values |

Parametrize over various register value combinations to cover edge cases (zero, negative, maximum).

#### 5.4 Register Write (Mocked `ur_rtde`)

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_write_status_sets_all_registers` | Call `write_status(status=1, error_code=0, actual_rate=10.0, ready=True, fault=False)` | All five `setInput*Register` methods called with correct args |
| `test_write_status_int_registers` | Verify `setInputIntRegister(0, status)` and `setInputIntRegister(1, error_code)` | Called with register index and value |
| `test_write_status_double_register` | Verify `setInputDoubleRegister(0, actual_rate)` | Called with `(0, 10.0)` |
| `test_write_status_bool_registers` | Verify `setInputBitRegister(64, ready)` and `setInputBitRegister(65, fault)` | Called with correct values |

Parametrize with `@pytest.mark.parametrize` over all status/error combinations from `config.py`:
- `(STATUS_IDLE, ERR_NONE, 0.0, True, False)`
- `(STATUS_RUNNING, ERR_NONE, 25.0, True, False)`
- `(STATUS_ERROR, ERR_COMMS_LOST, 0.0, False, True)`
- `(STATUS_HOMING, ERR_NONE, 0.0, True, False)`

#### 5.5 Convenience Methods (Mocked `ur_rtde`)

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_get_tcp_speed_computes_magnitude` | Mock `getActualTCPSpeed()` to return `[0.1, 0.0, 0.0, 0.0, 0.0, 0.0]` | Returns `100.0` (0.1 m/s * 1000 = 100 mm/s) |
| `test_get_tcp_speed_3d_vector` | Mock speed `[0.03, 0.04, 0.0, 0.0, 0.0, 0.0]` | Returns `50.0` (sqrt(0.03^2+0.04^2) * 1000) |
| `test_get_tcp_speed_zero` | Mock speed `[0, 0, 0, 0, 0, 0]` | Returns `0.0` |
| `test_get_tcp_speed_ignores_rotation` | Mock speed `[0.0, 0.0, 0.0, 1.0, 2.0, 3.0]` | Returns `0.0` (only linear components) |
| `test_get_robot_mode` | Mock `getRobotMode()` to return `7` | Returns `7` |

---

## 6. Unit Tests: `bridge_daemon.py`

### Mocking Strategy

The Bridge class depends on two clients (`RTDEClient` and `KlipperClient`) and the `time` module. All three are mocked:

- **`RTDEClient`**: Use `unittest.mock.MagicMock` spec'd against `RTDEClient`. Configure `read_commands()` return values to simulate UR30 commands.
- **`KlipperClient`**: Use `unittest.mock.MagicMock` spec'd against `KlipperClient`. Verify G-code commands sent.
- **`time.monotonic`**: Patch to control timing for loop period and timeout tests.
- **`time.sleep`**: Patch to prevent actual sleeping in tests.

**Fixture structure:**

```
@pytest.fixture
def bridge():
    """Create a Bridge with mocked clients, ready for _tick() testing."""
    b = Bridge(ur_host="127.0.0.1", dry_run=False)
    b.rtde = MagicMock(spec=RTDEClient)
    b.klipper = MagicMock(spec=KlipperClient)
    b.rtde.connected = True
    b.klipper.connected = True
    b.state.ready = True
    return b
```

The majority of tests exercise `_process_commands()` and `_tick()` rather than `start()` (which contains the infinite loop).

### Test Cases

#### 6.1 BridgeState Initialization

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_initial_state` | Create `BridgeState()` | `stepper_enabled=False`, `current_mode=MODE_OFF`, `current_rate=0.0`, `actual_rate=0.0`, `status=STATUS_IDLE`, `error_code=ERR_NONE`, `fault=False`, `ready=False`, `last_command_time=0.0` |

#### 6.2 Command Translation: Mode Handling

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_mode_off_when_already_off` | `cmd={mode: MODE_OFF, enable: True, ...}`, current mode already OFF | No Klipper calls, state stays IDLE |
| `test_mode_off_stops_running_extrusion` | `cmd={mode: MODE_OFF, enable: True, ...}`, current mode was EXTRUDE | `stepper_set_position("pump", 0.0)` called, mode set to OFF, status to IDLE |
| `test_mode_extrude_at_valid_rate` | `cmd={mode: MODE_EXTRUDE, enable: True, rate: 25.0, ...}` | `stepper_enable("pump")` then `stepper_move("pump", 250.0, 25.0, 200)` called, status=RUNNING |
| `test_mode_extrude_direction_positive` | mode=EXTRUDE, rate=10.0 | Move distance is `10.0 * 10.0 = 100.0` (positive) |
| `test_mode_retract_direction_negative` | mode=RETRACT, rate=10.0 | Move distance is `-10.0 * 10.0 = -100.0` (negative) |
| `test_mode_retract_at_valid_rate` | `cmd={mode: MODE_RETRACT, enable: True, rate: 15.0, ...}` | `stepper_move` called with negative distance, speed=15.0 |

#### 6.3 Rate Clamping

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_rate_clamped_to_max` | `cmd={rate: 100.0, ...}` (exceeds `MAX_EXTRUSION_RATE=50.0`) | Rate clamped to 50.0 in the move command |
| `test_rate_clamped_to_zero_floor` | `cmd={rate: -5.0, ...}` | Rate clamped to 0.0 |
| `test_rate_at_max_allowed` | `cmd={rate: 50.0, ...}` | Rate passes through as 50.0 |
| `test_rate_zero_stops_extrusion` | `cmd={mode: EXTRUDE, rate: 0.0, ...}` | Below deadband (0.01), `_stop_extrusion()` called |
| `test_rate_at_deadband_boundary` | `cmd={mode: EXTRUDE, rate: 0.01, ...}` | At boundary, treated as zero, `_stop_extrusion()` called |
| `test_rate_just_above_deadband` | `cmd={mode: EXTRUDE, rate: 0.02, ...}` | Above deadband, move command issued |

#### 6.4 E-Stop Handling

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_estop_calls_emergency_stop` | `cmd={estop: True, ...}` | `klipper.emergency_stop()` called |
| `test_estop_disables_stepper_state` | `cmd={estop: True, ...}` | `stepper_enabled=False`, `status=STATUS_ERROR`, `mode=MODE_OFF`, `rate=0.0` |
| `test_estop_takes_priority_over_extrude` | `cmd={estop: True, mode: EXTRUDE, rate: 25.0, enable: True, ...}` | Emergency stop executed, no extrude command sent |
| `test_estop_takes_priority_over_home` | `cmd={estop: True, home: True, ...}` | Emergency stop executed, no homing |
| `test_estop_in_dry_run_skips_klipper_call` | Bridge in dry_run mode, `cmd={estop: True}` | `klipper.emergency_stop()` NOT called, but state updated |

#### 6.5 Homing

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_homing_sets_position_zero` | `cmd={home: True, ...}` | `stepper_set_position("pump", 0.0)` called |
| `test_homing_status_transitions` | `cmd={home: True, ...}` | Status goes to HOMING then back to IDLE |
| `test_homing_ignored_when_already_homing` | State status=HOMING, `cmd={home: True, ...}` | No duplicate homing call |
| `test_homing_error_sets_error_status` | `stepper_set_position` raises exception | `status=STATUS_ERROR` |
| `test_homing_dry_run_skips_klipper` | dry_run=True, `cmd={home: True, ...}` | No Klipper calls, status transitions normally |

#### 6.6 Enable/Disable

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_disable_stops_enabled_stepper` | `enable=False`, stepper was enabled | `_stop_extrusion()` called |
| `test_disable_noop_when_already_disabled` | `enable=False`, stepper was disabled | No Klipper calls |
| `test_enable_activates_stepper_on_first_move` | `enable=True, mode=EXTRUDE, rate=10.0` | `stepper_enable("pump")` called before first move |
| `test_enable_does_not_re_enable` | Stepper already enabled, new extrude command | `stepper_enable` NOT called again |

#### 6.7 Extrusion Start/Stop Mechanics

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_set_extrusion_enables_stepper_first` | First extrude with `stepper_enabled=False` | `stepper_enable` called before `stepper_move` |
| `test_set_extrusion_skips_enable_if_already_enabled` | `stepper_enabled=True` | `stepper_enable` NOT called |
| `test_set_extrusion_calculates_distance` | rate=20.0 mm/s | Distance = `20.0 * 10.0 = 200.0`, speed = `20.0` |
| `test_set_extrusion_uses_default_accel` | Any rate | Accel is `config.DEFAULT_ACCEL` (200) |
| `test_set_extrusion_updates_last_command_time` | Call `_set_extrusion(10.0)` | `state.last_command_time` is updated |
| `test_set_extrusion_error_sets_error_state` | `stepper_move` raises | `status=STATUS_ERROR`, `error_code=ERR_COMMS_LOST` |
| `test_stop_extrusion_resets_position` | Call `_stop_extrusion()` | `stepper_set_position("pump", 0.0)` called |
| `test_stop_extrusion_resets_state` | Call `_stop_extrusion()` | `mode=MODE_OFF`, `rate=0.0`, `status=IDLE` |
| `test_stop_extrusion_error_logged` | `stepper_set_position` raises | Exception caught and logged, no crash |

#### 6.8 Dry Run Mode

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_dry_run_extrude_no_klipper_calls` | dry_run=True, extrude command | No `stepper_move` or `stepper_enable` calls |
| `test_dry_run_stop_no_klipper_calls` | dry_run=True, stop command | No `stepper_set_position` call, state still transitions |
| `test_dry_run_estop_no_klipper_calls` | dry_run=True, e-stop | No `emergency_stop` call, state still updated |
| `test_dry_run_homing_no_klipper_calls` | dry_run=True, home command | No `stepper_set_position` call |
| `test_dry_run_shutdown_no_klipper_calls` | dry_run=True, `stop()` | No `stepper_disable` call |

#### 6.9 Status Reporting

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_report_status_writes_all_fields` | After tick, verify `write_status` call | Called with correct status, error_code, actual_rate, ready, fault |
| `test_report_status_ready_and_fault` | `state.ready=True, state.fault=True` | `ready` parameter is `False` (ready AND NOT fault) |
| `test_report_status_ready_no_fault` | `state.ready=True, state.fault=False` | `ready` parameter is `True` |
| `test_report_status_failure_logged` | `write_status` raises | Exception caught, logged as warning, no crash |

#### 6.10 Connection Loss and Reconnection

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_tick_connection_error_triggers_estop` | `read_commands()` raises `ConnectionError` | `status=STATUS_ERROR`, `error_code=ERR_COMMS_LOST`, `fault=True` |
| `test_tick_connection_error_attempts_reconnect` | `read_commands()` raises `ConnectionError` | `_connect_all()` is called |
| `test_tick_connection_error_tries_emergency_stop` | `read_commands()` raises `ConnectionError` | `stepper_disable` called (best-effort) |
| `test_try_emergency_stop_suppresses_exceptions` | `stepper_disable` raises | No exception propagated |
| `test_try_emergency_stop_skips_in_dry_run` | dry_run=True | `stepper_disable` not called |
| `test_try_emergency_stop_skips_when_disconnected` | `klipper.connected=False` | `stepper_disable` not called |

#### 6.11 Shutdown (`stop()`)

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_stop_disables_stepper` | Call `stop()` | `stepper_disable("pump")` called |
| `test_stop_reports_offline_status` | Call `stop()` | `write_status(STATUS_IDLE, ERR_NONE, 0.0, False, False)` |
| `test_stop_disconnects_both_clients` | Call `stop()` | `rtde.disconnect()` and `klipper.disconnect()` called |
| `test_stop_sets_running_false` | Call `stop()` | `_running` is `False` |
| `test_stop_handles_klipper_error_gracefully` | `stepper_disable` raises | Continues to report status and disconnect |
| `test_stop_handles_rtde_error_gracefully` | `write_status` raises | Continues to disconnect |

#### 6.12 Main Loop Mechanics

These tests verify `start()` behavior without running an infinite loop:

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_start_connects_both` | Mock `_connect_all`, set `_running=False` after first tick | `_connect_all()` called, `state.ready=True`, `state.status=STATUS_IDLE` |
| `test_start_keyboard_interrupt_calls_stop` | `_tick()` raises `KeyboardInterrupt` | `stop()` is called |
| `test_start_loop_sleeps_correct_period` | Patch `time.monotonic` and `time.sleep` | Sleep called with `LOOP_PERIOD - elapsed` |
| `test_start_loop_no_sleep_when_overrun` | Patch elapsed time to exceed LOOP_PERIOD | `time.sleep` NOT called |

---

## 7. Integration Tests: URSim Setup

### 7.1 What Is URSim

URSim (Universal Robots Simulator) is the official offline simulator that provides a full RTDE interface identical to a physical robot. It runs as a Docker container and exposes the same TCP ports as a real UR controller, including port 30004 for RTDE.

### 7.2 Docker Configuration

**`tests/docker/docker-compose.ursim.yml`:**

```yaml
version: "3.8"

services:
  ursim:
    image: universalrobots/ursim_e-series
    environment:
      - ROBOT_MODEL=UR30
    ports:
      - "30004:30004"    # RTDE
      - "29999:29999"    # Dashboard server
      - "30001:30001"    # Primary interface
      - "30002:30002"    # Secondary interface
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1024M
    healthcheck:
      test: ["CMD", "bash", "-c", "echo quit | nc -w 2 localhost 29999"]
      interval: 5s
      timeout: 5s
      retries: 20
      start_period: 30s
```

### 7.3 URSim Startup Sequence

The UR simulator requires a specific startup sequence before it can accept RTDE connections:

1. **Container start** (~5-10s): Linux VM boots inside the container.
2. **Controller initialization** (~10-20s): The UR controller software starts.
3. **Robot power-on** (~5s): The simulated robot must be powered on and brakes released.
4. **Program running**: RTDE registers are only written by a running URScript program.

**Automated startup via Dashboard Server (port 29999):**

The Dashboard Server accepts text commands over TCP. The test fixture must send these commands after the container's healthcheck passes:

```
1. Connect to port 29999
2. Send: "power on\n"        -> Wait for "Robotmode: RUNNING"
3. Send: "brake release\n"   -> Wait for "Robotmode: RUNNING"
4. (Optional) Load and start a URScript program that writes output registers
```

### 7.4 URSim Pytest Fixture

**`tests/integration/conftest.py`:**

The fixture should:

1. Start the Docker container (or verify it is running).
2. Wait for the healthcheck to pass.
3. Power on the robot via the Dashboard Server.
4. Release brakes.
5. Optionally load a test URScript program.
6. Yield the container's hostname/IP and port to the test.
7. On teardown, stop the container (or leave it running for faster iteration).

**Fixture design:**

```
@pytest.fixture(scope="session")
def ursim_container():
    """Start URSim Docker container, wait for ready, yield host info."""
    # 1. docker compose up -d
    # 2. Wait for healthcheck (poll dashboard port 29999)
    # 3. Send "power on" + "brake release" via dashboard
    # 4. Wait for robot mode == RUNNING
    # 5. yield {"host": "127.0.0.1", "rtde_port": 30004, "dashboard_port": 29999}
    # 6. docker compose down (teardown)

@pytest.fixture
def ursim_rtde_client(ursim_container):
    """Create a connected RTDEClient pointing at URSim."""
    client = RTDEClient(host=ursim_container["host"])
    client.connect()
    yield client
    client.disconnect()
```

**Session scope** for the container fixture is important: starting URSim takes 20-30 seconds, so it should be started once per test session, not per test.

### 7.5 Test URScript Program

A minimal URScript program must run on URSim to write output registers that the bridge daemon reads. Without a running program, the output registers contain stale or default values.

**`tests/integration/test_program.script`:**

```urscript
# Minimal test program: writes known values to output registers
# so integration tests can verify the bridge reads them correctly.

write_output_integer_register(0, 1)          # mode = EXTRUDE
write_output_float_register(0, 10.0)         # rate = 10.0 mm/s
write_output_float_register(1, 50.0)         # tcp_speed = 50.0 mm/s
write_output_boolean_register(64, True)       # enable = True
write_output_boolean_register(65, False)      # estop = False
write_output_boolean_register(66, False)      # home = False

while True:
    # Keep program running so registers persist
    sync()
end
```

This program can be loaded onto URSim via the Dashboard Server (`load <path>`) or by mounting a volume into the container.

### 7.6 Alternative: Skip URSim Program

If loading a URScript program into URSim is complex to automate, an alternative is to test only the RTDE input register writing path (Pi -> UR30). The bridge daemon writes input registers; the integration test can then read those registers back via a second RTDE receive interface to verify correctness. This path works without a running URScript program.

### 7.7 CI Considerations for URSim

| Consideration | Approach |
|---------------|----------|
| Docker required | CI runner must support Docker (GitHub Actions ubuntu runners have Docker) |
| Startup time | 20-30s; use session-scoped fixture, run integration tests as a separate job |
| Resource limits | URSim needs ~1 CPU core and ~1 GB RAM |
| Architecture | URSim Docker image is `linux/amd64`; CI must use an x86_64 runner (not ARM) |
| Flakiness | Network timing in containers can be flaky; use retries with backoff for connection setup |
| Licensing | URSim is free for non-commercial use; acceptable for a university capstone |

---

## 8. Integration Tests: Bridge + URSim

### 8.1 Scope

These tests verify the real RTDE communication path: the bridge daemon's `RTDEClient` connects to a real (simulated) UR controller and exchanges register data. Klipper is still mocked (no real klippy in the integration tests), isolating the RTDE layer.

### 8.2 Test Cases

#### 8.2.1 RTDE Connection

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_connect_to_ursim` | `RTDEClient.connect()` against URSim | No exception, `connected` returns `True` |
| `test_disconnect_from_ursim` | Connect then disconnect | Clean disconnect, `connected` returns `False` |
| `test_reconnect_after_disconnect` | Connect, disconnect, connect again | Second connection succeeds |

#### 8.2.2 Register Read

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_read_commands_returns_dict` | `read_commands()` against URSim | Returns dict with all expected keys |
| `test_read_commands_mode_default` | Read mode register without running program | Returns `0` (default value) |
| `test_read_commands_with_running_program` | Load test script that writes known values, then `read_commands()` | Returns values matching what the URScript wrote |
| `test_read_commands_rate_float` | Read extrusion rate register | Returns a `float` value |
| `test_read_commands_bool_registers` | Read boolean registers | Returns `bool` values |

#### 8.2.3 Register Write

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_write_status_no_exception` | `write_status(STATUS_IDLE, ERR_NONE, 0.0, True, False)` | No exception raised |
| `test_write_status_all_combinations` | Parametrize over all status/error combos | All write successfully |
| `test_write_read_roundtrip` | Write input registers, read them back via a second RTDE connection | Values match (if URScript reads and echoes, or via URSim introspection) |

#### 8.2.4 Mode Transitions (Bridge Level)

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_bridge_idle_to_extrude` | URSim sends mode=EXTRUDE, enable=True, rate=10.0; bridge processes | Klipper mock receives `stepper_enable` then `stepper_move` |
| `test_bridge_extrude_to_stop` | Transition from extrude to mode=OFF | Klipper mock receives `stepper_set_position(0.0)` |
| `test_bridge_estop_from_ursim` | URSim sends estop=True | Klipper mock receives `emergency_stop()` |

#### 8.2.5 Fault Injection

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_ursim_restart_triggers_reconnect` | Stop URSim container mid-test, then restart it | Bridge detects `ConnectionError`, reconnects after container returns |
| `test_ursim_kill_triggers_fault_state` | Kill URSim container without restart | Bridge enters `STATUS_ERROR` with `ERR_COMMS_LOST` |
| `test_network_delay_simulation` | Use `tc` or Docker network to add 50ms latency | Bridge continues to function; measure observed latency |

#### 8.2.6 Latency Measurement

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| `test_rtde_roundtrip_latency` | Timestamp before `write_status`, read back in next cycle, timestamp after | Roundtrip < 50ms (generous bound for Docker) |
| `test_read_commands_throughput` | Call `read_commands()` 1000 times in a loop, measure time | At least 100 reads/second (well below 500 Hz physical limit, but reasonable for Python + Docker) |

### 8.3 Running Integration Tests

```bash
# Start URSim first (or let the fixture handle it)
docker compose -f tests/docker/docker-compose.ursim.yml up -d

# Wait for ready (fixture does this, but for manual runs):
until echo "quit" | nc -w 2 127.0.0.1 29999; do sleep 2; done

# Run integration tests
pytest tests/integration/ -v --ursim

# Tear down
docker compose -f tests/docker/docker-compose.ursim.yml down
```

The `--ursim` flag is a custom pytest marker. Integration tests should be decorated with `@pytest.mark.ursim` so they can be skipped in environments without Docker:

```python
@pytest.mark.ursim
def test_connect_to_ursim(ursim_rtde_client):
    assert ursim_rtde_client.connected
```

In `conftest.py`:

```python
def pytest_addoption(parser):
    parser.addoption("--ursim", action="store_true", help="run URSim integration tests")

def pytest_collection_modifyitems(config, items):
    if not config.getoption("--ursim"):
        skip_ursim = pytest.mark.skip(reason="need --ursim option to run")
        for item in items:
            if "ursim" in item.keywords:
                item.add_marker(skip_ursim)
```

---

## 9. Coverage Targets and Hard-to-Test Areas

### 9.1 Coverage Targets

| Module | Target | Rationale |
|--------|--------|-----------|
| `config.py` | 100% | Pure constants; trivially covered by importing |
| `klipper_client.py` | >= 95% | All code paths testable with socket mocks |
| `rtde_client.py` | >= 90% | Stub mode is fully testable; mocked ur_rtde covers the rest. The `import` try/except at module level is hard to cover both branches in one test run. |
| `bridge_daemon.py` | >= 85% | Most logic is testable. The `start()` infinite loop and `main()` argparse entry point are harder to cover completely. |
| **Overall** | **>= 90%** | Realistic for a well-tested bridge daemon |

### 9.2 Hard-to-Test Areas

| Area | Difficulty | Mitigation |
|------|-----------|------------|
| `start()` infinite loop with `time.sleep` | Medium | Test by setting `_running = False` after N ticks; verify loop mechanics indirectly |
| `_connect_all()` retry loop | Medium | Mock `connect()` to succeed on second call; verify retry count and delay |
| `main()` argparse + signal handling | Low-Medium | Test with `subprocess.run()` or by calling `main()` with patched `sys.argv` and immediate `KeyboardInterrupt` |
| SIGTERM handler | Low | Verify `signal.signal` was called; invoke the handler directly |
| `HAS_UR_RTDE` import-time branching | Hard | Requires separate test processes or `importlib.reload`. Accept covering only one branch per test run. |
| Thread safety of `KlipperClient._lock` | Medium | Use `threading.Barrier` to synchronize two test threads making concurrent `_send()` calls |
| Real Klipper integration | N/A | Out of scope for automated tests; requires klippy running with a connected MCU. Covered by manual hardware testing in Phase 4. |
| USB serial to SKR Pico | N/A | Internal to Klipper; not our code to test |
| Stepper motor physical behavior | N/A | Phase 4 hardware testing only |

### 9.3 What We Explicitly Do Not Test

- **Klipper internals**: Motion planning, step generation, MCU protocol. These are tested by the Klipper project itself.
- **ur_rtde library internals**: TCP protocol handling, binary packing. Tested by the SDU ur_rtde project.
- **URScript execution**: Correctness of the URScript program. Validated manually on the teach pendant or URSim GUI.
- **Network infrastructure**: Switch latency, cable integrity. Verified during hardware commissioning.

---

## 10. CI Pipeline Design

### 10.1 Pipeline Structure

```
on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - Checkout code
      - Set up Python 3.11+
      - Install: pip install pytest pytest-cov pytest-mock pytest-timeout
      - Run: pytest tests/unit/ -v --cov=src/bridge --cov-report=xml --timeout=10
      - Upload coverage report

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests        # Only run if unit tests pass
    services:
      ursim:
        image: universalrobots/ursim_e-series
        env:
          ROBOT_MODEL: UR30
        ports:
          - 30004:30004
          - 29999:29999
        options: --cpus=1
    steps:
      - Checkout code
      - Set up Python 3.11+
      - Install: pip install pytest pytest-timeout ur-rtde
      - Wait for URSim ready (poll dashboard port 29999)
      - Power on robot via dashboard
      - Run: pytest tests/integration/ -v --ursim --timeout=60
```

### 10.2 CI Environment Notes

| Concern | Approach |
|---------|----------|
| `ur-rtde` not installable on CI | Unit tests do not require `ur-rtde` (they use mocks or test stub mode). Only integration tests need it. |
| Docker image pull time | Cache the `universalrobots/ursim_e-series` image in CI. First pull is ~1.5 GB. |
| URSim startup time | Allow 60s startup in the wait step. Use session-scoped fixtures. |
| Flaky network timing | Use `pytest-timeout` (60s per integration test) and `pytest.mark.flaky` with retries if needed. |
| ARM runners (Apple Silicon) | URSim is x86_64 only. CI must use `ubuntu-latest` (x86_64). Local Mac development runs unit tests only; integration tests run in CI or via Rosetta/Docker emulation. |
| No `ur-rtde` on ARM (local dev) | Stub mode covers this. Integration tests are CI-only or optional locally. |

### 10.3 Local Development Workflow

```bash
# Quick feedback loop (no Docker, no ur-rtde needed)
pytest tests/unit/ -v --timeout=5

# With coverage
pytest tests/unit/ -v --cov=src/bridge --cov-report=term-missing

# Integration tests (requires Docker Desktop)
docker compose -f tests/docker/docker-compose.ursim.yml up -d
# Wait ~30s for URSim to start
pytest tests/integration/ -v --ursim --timeout=60
docker compose -f tests/docker/docker-compose.ursim.yml down
```

### 10.4 Test Dependencies Summary

**`requirements-test.txt`:**

```
pytest>=8.0
pytest-cov>=5.0
pytest-mock>=3.14
pytest-timeout>=2.2
```

**`requirements-integration.txt`** (additional, for integration tests only):

```
ur-rtde>=1.5
```

---

## Appendix A: Command-to-G-code Translation Matrix

This table enumerates every combination of input commands and the expected Klipper G-code output. Each row corresponds to one or more unit tests in `test_bridge_daemon.py`.

| enable | estop | home | mode | rate (mm/s) | Expected Klipper Action | State After |
|--------|-------|------|------|-------------|-------------------------|-------------|
| any | **True** | any | any | any | `emergency_stop()` | ERROR, mode=OFF, rate=0 |
| any | False | **True** | any | any | `MANUAL_STEPPER STEPPER=pump SET_POSITION=0.0000` | IDLE (after HOMING) |
| **False** | False | False | any | any | `stepper_set_position(0.0)` (if was enabled) | IDLE, mode=OFF |
| True | False | False | **OFF** | any | `stepper_set_position(0.0)` (if mode was not OFF) | IDLE, mode=OFF |
| True | False | False | **EXTRUDE** | 25.0 | `ENABLE=1` (if needed) + `MOVE=250.0000 SPEED=25.00 ACCEL=200.0` | RUNNING, mode=EXTRUDE |
| True | False | False | **RETRACT** | 15.0 | `ENABLE=1` (if needed) + `MOVE=-150.0000 SPEED=15.00 ACCEL=200.0` | RUNNING, mode=RETRACT |
| True | False | False | EXTRUDE | 0.005 | `stepper_set_position(0.0)` (below deadband) | IDLE, mode=OFF |
| True | False | False | EXTRUDE | 100.0 | Clamped to 50.0: `MOVE=500.0000 SPEED=50.00 ACCEL=200.0` | RUNNING |

---

## Appendix B: Fixture Dependency Graph

```
tests/conftest.py
  |
  +-- mock_unix_socket          (socketpair for KlipperClient tests)
  +-- fake_klippy_server        (FakeKlippy wrapping server-side socket)
  +-- mock_rtde_receive         (MagicMock of RTDEReceiveInterface)
  +-- mock_rtde_control         (MagicMock of RTDEControlInterface)
  +-- bridge_state              (fresh BridgeState instance)
  +-- bridge                    (Bridge with mocked clients)
  +-- dry_run_bridge            (Bridge with dry_run=True)

tests/integration/conftest.py
  |
  +-- ursim_container           (session-scoped Docker lifecycle)
  +-- ursim_dashboard           (TCP connection to port 29999)
  +-- ursim_rtde_client         (connected RTDEClient)
  +-- ursim_bridge              (Bridge with real RTDE, mocked Klipper)
```

---

## Appendix C: URSim Docker Quick Reference

**Pull the image:**
```bash
docker pull universalrobots/ursim_e-series
```

**Start with UR30 model and RTDE port exposed:**
```bash
docker run -d \
    --name ursim-w26 \
    -e ROBOT_MODEL=UR30 \
    -p 30004:30004 \
    -p 29999:29999 \
    -p 30001:30001 \
    --cpus=1 \
    universalrobots/ursim_e-series
```

**Wait for controller ready:**
```bash
until echo "robotmode" | nc -w 2 127.0.0.1 29999 | grep -q "RUNNING\|IDLE"; do
    sleep 2
done
```

**Power on and release brakes (via Dashboard Server):**
```bash
echo "power on" | nc -w 2 127.0.0.1 29999
sleep 5
echo "brake release" | nc -w 2 127.0.0.1 29999
sleep 3
```

**Load a URScript program:**
```bash
# Mount a volume with the script, or use the dashboard:
echo "load /programs/test_program.urp" | nc -w 2 127.0.0.1 29999
echo "play" | nc -w 2 127.0.0.1 29999
```

**Stop and remove:**
```bash
docker stop ursim-w26 && docker rm ursim-w26
```

**Available UR30 robot model in e-series image:** Set `ROBOT_MODEL=UR30` as an environment variable. The default is UR5 if unset.

---

*This document was prepared as part of the W26 Cobot Axis project (ME 472, Winter 2026). It covers the testing design only; implementation of the test code is tracked separately in `todo.md`.*
