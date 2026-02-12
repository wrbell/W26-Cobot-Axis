"""
Unit tests for bridge.rtde_client — RTDEClient.

Tests both stub mode (no ur_rtde installed) and mocked-library mode
(patching HAS_UR_RTDE and injecting mock interfaces).

All tests run without hardware or the ur_rtde C++ bindings.
"""

import math

import pytest
from unittest.mock import MagicMock, patch

from bridge import config
from bridge.rtde_client import RTDEClient


# ===================================================================
# 5.1  Stub Mode (no ur_rtde installed)
# ===================================================================

class TestStubMode:
    """Tests that exercise the stub fallback when HAS_UR_RTDE is False.

    These run against the real RTDEClient code, which falls back to
    stubs when ur_rtde is not importable (the default CI case).
    """

    @pytest.fixture
    def stub_client(self):
        """RTDEClient in stub mode (HAS_UR_RTDE patched to False)."""
        with patch("bridge.rtde_client.HAS_UR_RTDE", False):
            yield RTDEClient(host="10.0.0.1")

    def test_stub_connect_succeeds(self, stub_client):
        """connect() in stub mode does not raise."""
        stub_client.connect()  # should not raise

    def test_stub_connected_returns_true(self, stub_client):
        """connected property returns True in stub mode."""
        assert stub_client.connected is True

    def test_stub_disconnect_no_op(self, stub_client):
        """disconnect() in stub mode is a no-op."""
        stub_client.disconnect()  # should not raise

    def test_stub_read_commands_returns_safe_defaults(self, stub_client):
        """read_commands() returns safe defaults when no robot is connected."""
        cmd = stub_client.read_commands()
        assert cmd["mode"] == config.MODE_OFF
        assert cmd["extrusion_rate"] == 0.0
        assert cmd["tcp_speed"] == 0.0
        assert cmd["enable"] is False
        assert cmd["estop"] is False
        assert cmd["home"] is False

    def test_stub_write_status_no_op(self, stub_client):
        """write_status() in stub mode does not raise."""
        stub_client.write_status(
            status=config.STATUS_IDLE,
            error_code=config.ERR_NONE,
            actual_rate=0.0,
            ready=True,
            fault=False,
        )  # should not raise

    def test_stub_get_tcp_speed_returns_zero(self, stub_client):
        """get_tcp_speed() returns 0.0 in stub mode."""
        assert stub_client.get_tcp_speed() == 0.0

    def test_stub_get_robot_mode_returns_running(self, stub_client):
        """get_robot_mode() returns 7 (running) in stub mode."""
        assert stub_client.get_robot_mode() == 7


# ===================================================================
# Helper: mocked ur_rtde mode
# ===================================================================

@pytest.fixture
def mock_rtde_interfaces():
    """Patch HAS_UR_RTDE to True and inject mock receive/control interfaces."""
    mock_recv_cls = MagicMock()
    mock_ctrl_cls = MagicMock()
    mock_recv_instance = MagicMock()
    mock_ctrl_instance = MagicMock()
    mock_recv_cls.return_value = mock_recv_instance
    mock_ctrl_cls.return_value = mock_ctrl_instance

    with patch("bridge.rtde_client.HAS_UR_RTDE", True), \
         patch("bridge.rtde_client.rtde_receive", create=True) as mock_recv_mod, \
         patch("bridge.rtde_client.rtde_control", create=True) as mock_ctrl_mod:
        mock_recv_mod.RTDEReceiveInterface = mock_recv_cls
        mock_ctrl_mod.RTDEControlInterface = mock_ctrl_cls
        yield {
            "recv_cls": mock_recv_cls,
            "ctrl_cls": mock_ctrl_cls,
            "recv": mock_recv_instance,
            "ctrl": mock_ctrl_instance,
        }


@pytest.fixture
def mocked_client(mock_rtde_interfaces):
    """RTDEClient with mocked ur_rtde, connected."""
    client = RTDEClient(host="192.168.1.100", frequency=500)
    client.connect()
    return client, mock_rtde_interfaces


# ===================================================================
# 5.2  Connection Lifecycle (Mocked ur_rtde)
# ===================================================================

class TestConnectionMocked:

    def test_connect_creates_interfaces(self, mocked_client):
        """connect() instantiates both RTDE interfaces."""
        client, mocks = mocked_client
        mocks["recv_cls"].assert_called_once_with("192.168.1.100", 500)
        mocks["ctrl_cls"].assert_called_once_with("192.168.1.100")

    def test_connect_uses_config_defaults(self, mock_rtde_interfaces):
        """RTDEClient() with no args uses config.UR30_HOST and config.RTDE_FREQUENCY."""
        client = RTDEClient()
        client.connect()
        mock_rtde_interfaces["recv_cls"].assert_called_with(
            config.UR30_HOST, config.RTDE_FREQUENCY
        )
        mock_rtde_interfaces["ctrl_cls"].assert_called_with(config.UR30_HOST)

    def test_connect_uses_custom_host(self, mock_rtde_interfaces):
        """RTDEClient with custom host passes it to interfaces."""
        client = RTDEClient(host="10.0.0.1")
        client.connect()
        mock_rtde_interfaces["recv_cls"].assert_called_with("10.0.0.1", config.RTDE_FREQUENCY)
        mock_rtde_interfaces["ctrl_cls"].assert_called_with("10.0.0.1")

    def test_disconnect_calls_both_interfaces(self, mocked_client):
        """disconnect() calls disconnect() on both interfaces."""
        client, mocks = mocked_client
        client.disconnect()
        mocks["recv"].disconnect.assert_called_once()
        mocks["ctrl"].disconnect.assert_called_once()

    def test_disconnect_sets_none(self, mocked_client):
        """disconnect() sets both interface references to None."""
        client, _ = mocked_client
        client.disconnect()
        assert client._rtde_r is None
        assert client._rtde_c is None

    def test_disconnect_suppresses_exceptions(self, mocked_client):
        """disconnect() suppresses exceptions from interface disconnect()."""
        client, mocks = mocked_client
        mocks["recv"].disconnect.side_effect = RuntimeError("mock error")
        mocks["ctrl"].disconnect.side_effect = RuntimeError("mock error")
        client.disconnect()  # should not raise
        assert client._rtde_r is None
        assert client._rtde_c is None

    def test_disconnect_when_not_connected(self, mock_rtde_interfaces):
        """disconnect() on a never-connected client is a no-op."""
        client = RTDEClient()
        client.disconnect()  # should not raise

    def test_connected_property_true(self, mocked_client):
        """connected returns True when isConnected() returns True."""
        client, mocks = mocked_client
        mocks["recv"].isConnected.return_value = True
        assert client.connected is True

    def test_connected_property_false_when_not_connected(self, mocked_client):
        """connected returns False when isConnected() returns False."""
        client, mocks = mocked_client
        mocks["recv"].isConnected.return_value = False
        assert client.connected is False

    def test_connected_false_when_rtde_r_is_none(self, mock_rtde_interfaces):
        """connected returns False when _rtde_r is None."""
        client = RTDEClient()
        assert client.connected is False


# ===================================================================
# 5.3  Register Read (Mocked ur_rtde)
# ===================================================================

class TestRegisterRead:

    def test_read_commands_reads_all_registers(self, mocked_client):
        """read_commands() returns a dict with all expected keys."""
        client, mocks = mocked_client
        mocks["recv"].getOutputIntRegister.return_value = 0
        mocks["recv"].getOutputDoubleRegister.return_value = 0.0
        mocks["recv"].getOutputBitRegister.return_value = False

        cmd = client.read_commands()
        assert set(cmd.keys()) == {"mode", "extrusion_rate", "tcp_speed", "enable", "estop", "home", "timestamp"}

    def test_read_commands_mode_register(self, mocked_client):
        """read_commands() reads mode from int register 0."""
        client, mocks = mocked_client
        mocks["recv"].getOutputIntRegister.return_value = 1
        mocks["recv"].getOutputDoubleRegister.return_value = 0.0
        mocks["recv"].getOutputBitRegister.return_value = False

        cmd = client.read_commands()
        assert cmd["mode"] == 1
        mocks["recv"].getOutputIntRegister.assert_called_with(0)

    def test_read_commands_extrusion_rate(self, mocked_client):
        """read_commands() reads extrusion_rate from double register 0."""
        client, mocks = mocked_client
        mocks["recv"].getOutputIntRegister.return_value = 0
        mocks["recv"].getOutputDoubleRegister.side_effect = lambda reg: {0: 25.5, 1: 0.0}[reg]
        mocks["recv"].getOutputBitRegister.return_value = False

        cmd = client.read_commands()
        assert cmd["extrusion_rate"] == 25.5

    def test_read_commands_tcp_speed(self, mocked_client):
        """read_commands() reads tcp_speed from double register 1."""
        client, mocks = mocked_client
        mocks["recv"].getOutputIntRegister.return_value = 0
        mocks["recv"].getOutputDoubleRegister.side_effect = lambda reg: {0: 0.0, 1: 100.0}[reg]
        mocks["recv"].getOutputBitRegister.return_value = False

        cmd = client.read_commands()
        assert cmd["tcp_speed"] == 100.0

    def test_read_commands_bool_registers(self, mocked_client):
        """read_commands() reads boolean registers correctly."""
        client, mocks = mocked_client
        mocks["recv"].getOutputIntRegister.return_value = 0
        mocks["recv"].getOutputDoubleRegister.return_value = 0.0
        mocks["recv"].getOutputBitRegister.side_effect = lambda reg: {
            64: True, 65: False, 66: True
        }[reg]

        cmd = client.read_commands()
        assert cmd["enable"] is True
        assert cmd["estop"] is False
        assert cmd["home"] is True

    @pytest.mark.parametrize("mode,rate,speed,enable,estop,home", [
        (0, 0.0, 0.0, False, False, False),     # all zeros
        (1, 25.0, 100.0, True, False, False),    # typical extrude
        (2, 15.0, 50.0, True, False, False),     # typical retract
        (1, 50.0, 200.0, True, True, False),     # estop active
        (0, 0.0, 0.0, False, False, True),       # homing
    ])
    def test_read_commands_parametrized(self, mock_rtde_interfaces, mode, rate,
                                        speed, enable, estop, home):
        """read_commands() correctly maps various register value combinations."""
        client = RTDEClient()
        client.connect()
        mocks = mock_rtde_interfaces

        mocks["recv"].getOutputIntRegister.return_value = mode
        mocks["recv"].getOutputDoubleRegister.side_effect = lambda reg: {0: rate, 1: speed}[reg]
        mocks["recv"].getOutputBitRegister.side_effect = lambda reg: {
            64: enable, 65: estop, 66: home
        }[reg]

        cmd = client.read_commands()
        assert cmd["mode"] == mode
        assert cmd["extrusion_rate"] == rate
        assert cmd["tcp_speed"] == speed
        assert cmd["enable"] == enable
        assert cmd["estop"] == estop
        assert cmd["home"] == home


# ===================================================================
# 5.4  Register Write (Mocked ur_rtde)
# ===================================================================

class TestRegisterWrite:

    def test_write_status_sets_all_registers(self, mocked_client):
        """write_status() calls all five setInput*Register methods."""
        client, mocks = mocked_client
        client.write_status(
            status=config.STATUS_RUNNING,
            error_code=config.ERR_NONE,
            actual_rate=10.0,
            ready=True,
            fault=False,
        )
        ctrl = mocks["ctrl"]
        ctrl.setInputIntRegister.assert_any_call(0, config.STATUS_RUNNING)
        ctrl.setInputIntRegister.assert_any_call(1, config.ERR_NONE)
        ctrl.setInputDoubleRegister.assert_called_once_with(0, 10.0)
        ctrl.setInputBitRegister.assert_any_call(64, True)
        ctrl.setInputBitRegister.assert_any_call(65, False)

    def test_write_status_int_registers(self, mocked_client):
        """write_status() sets int registers with (index, value)."""
        client, mocks = mocked_client
        client.write_status(
            status=config.STATUS_ERROR,
            error_code=config.ERR_COMMS_LOST,
            actual_rate=0.0,
            ready=False,
            fault=True,
        )
        ctrl = mocks["ctrl"]
        ctrl.setInputIntRegister.assert_any_call(0, config.STATUS_ERROR)
        ctrl.setInputIntRegister.assert_any_call(1, config.ERR_COMMS_LOST)

    def test_write_status_double_register(self, mocked_client):
        """write_status() sets double register 0 with actual_rate."""
        client, mocks = mocked_client
        client.write_status(
            status=config.STATUS_IDLE,
            error_code=config.ERR_NONE,
            actual_rate=42.5,
            ready=True,
            fault=False,
        )
        mocks["ctrl"].setInputDoubleRegister.assert_called_once_with(0, 42.5)

    def test_write_status_bool_registers(self, mocked_client):
        """write_status() sets bit registers 64 and 65."""
        client, mocks = mocked_client
        client.write_status(
            status=config.STATUS_IDLE,
            error_code=config.ERR_NONE,
            actual_rate=0.0,
            ready=True,
            fault=True,
        )
        ctrl = mocks["ctrl"]
        ctrl.setInputBitRegister.assert_any_call(64, True)
        ctrl.setInputBitRegister.assert_any_call(65, True)

    @pytest.mark.parametrize("status,error_code,rate,ready,fault", [
        (config.STATUS_IDLE, config.ERR_NONE, 0.0, True, False),
        (config.STATUS_RUNNING, config.ERR_NONE, 25.0, True, False),
        (config.STATUS_ERROR, config.ERR_COMMS_LOST, 0.0, False, True),
        (config.STATUS_HOMING, config.ERR_NONE, 0.0, True, False),
        (config.STATUS_ERROR, config.ERR_STALL, 0.0, False, True),
        (config.STATUS_ERROR, config.ERR_THERMAL, 0.0, False, True),
    ])
    def test_write_status_all_combinations(self, mock_rtde_interfaces,
                                            status, error_code, rate, ready, fault):
        """write_status() correctly maps all status/error combinations."""
        client = RTDEClient()
        client.connect()
        ctrl = mock_rtde_interfaces["ctrl"]

        client.write_status(status, error_code, rate, ready, fault)

        ctrl.setInputIntRegister.assert_any_call(0, status)
        ctrl.setInputIntRegister.assert_any_call(1, error_code)
        ctrl.setInputDoubleRegister.assert_called_with(0, rate)
        ctrl.setInputBitRegister.assert_any_call(64, ready)
        ctrl.setInputBitRegister.assert_any_call(65, fault)


# ===================================================================
# 5.5  Convenience Methods (Mocked ur_rtde)
# ===================================================================

class TestConvenienceMethods:

    def test_get_tcp_speed_computes_magnitude(self, mocked_client):
        """get_tcp_speed() computes linear magnitude in mm/s from m/s vector."""
        client, mocks = mocked_client
        # 0.1 m/s in X only -> 100.0 mm/s
        mocks["recv"].getActualTCPSpeed.return_value = [0.1, 0.0, 0.0, 0.0, 0.0, 0.0]
        assert client.get_tcp_speed() == pytest.approx(100.0)

    def test_get_tcp_speed_3d_vector(self, mocked_client):
        """get_tcp_speed() computes 3D magnitude: sqrt(0.03^2 + 0.04^2) * 1000 = 50.0."""
        client, mocks = mocked_client
        mocks["recv"].getActualTCPSpeed.return_value = [0.03, 0.04, 0.0, 0.0, 0.0, 0.0]
        expected = math.sqrt(0.03**2 + 0.04**2) * 1000.0
        assert client.get_tcp_speed() == pytest.approx(expected)

    def test_get_tcp_speed_zero(self, mocked_client):
        """get_tcp_speed() returns 0.0 when all components are zero."""
        client, mocks = mocked_client
        mocks["recv"].getActualTCPSpeed.return_value = [0, 0, 0, 0, 0, 0]
        assert client.get_tcp_speed() == 0.0

    def test_get_tcp_speed_ignores_rotation(self, mocked_client):
        """get_tcp_speed() only uses linear components (first 3), ignores rotation."""
        client, mocks = mocked_client
        mocks["recv"].getActualTCPSpeed.return_value = [0.0, 0.0, 0.0, 1.0, 2.0, 3.0]
        assert client.get_tcp_speed() == 0.0

    def test_get_robot_mode(self, mocked_client):
        """get_robot_mode() returns the value from getRobotMode()."""
        client, mocks = mocked_client
        mocks["recv"].getRobotMode.return_value = 7
        assert client.get_robot_mode() == 7

    def test_get_robot_mode_other_values(self, mocked_client):
        """get_robot_mode() returns non-7 values correctly."""
        client, mocks = mocked_client
        mocks["recv"].getRobotMode.return_value = 3
        assert client.get_robot_mode() == 3
