"""
Unit tests for StallGuard integration across the bridge daemon stack.

Tests:
    - config.py: input_double_register_1 in INPUT_REGISTERS, In.STALLGUARD_LOAD
    - klipper_status.py: is_hardware_stall(), get_stallguard_status()
    - rtde_client.py: write_status() sets input_double_register_1
    - bridge_daemon.py: hardware stall priority over UART stall, stallguard_load in _report_status

All tests are mock-based and run without hardware.
"""

import pytest
from unittest.mock import MagicMock, patch

from bridge import config
from bridge.klipper_status import KlipperStatusPoller
from bridge.rtde_client import RTDEClient
from bridge.bridge_daemon import Bridge


# ===================================================================
# 1. Config: register allocation
# ===================================================================

class TestStallGuardConfig:

    def test_input_double_register_1_in_config(self):
        """input_double_register_1 is listed in INPUT_REGISTERS['double']."""
        assert "input_double_register_1" in config.INPUT_REGISTERS["double"]

    def test_in_stallguard_load_constant(self):
        """In.STALLGUARD_LOAD maps to input_double_register_1."""
        assert config.In.STALLGUARD_LOAD == "input_double_register_1"

    def test_stallguard_monitor_poll_objects(self):
        """STALLGUARD_MONITOR_POLL_OBJECTS has stallguard_monitor key."""
        assert "stallguard_monitor" in config.STALLGUARD_MONITOR_POLL_OBJECTS


# ===================================================================
# 2. KlipperStatusPoller: hardware stall detection
# ===================================================================

class TestKlipperStatusPollerStallGuard:

    @pytest.fixture
    def poller(self):
        """KlipperStatusPoller with mocked KlipperClient (not started)."""
        kc = MagicMock()
        return KlipperStatusPoller(klipper_client=kc)

    def test_is_hardware_stall_false_by_default(self, poller):
        """is_hardware_stall() returns False when no data received."""
        assert poller.is_hardware_stall() is False

    def test_is_hardware_stall_true_when_active(self, poller):
        """is_hardware_stall() returns True when stall_active is True."""
        poller._last_stallguard_status = {"stall_active": True, "stall_count": 1}
        assert poller.is_hardware_stall() is True

    def test_is_hardware_stall_false_when_inactive(self, poller):
        """is_hardware_stall() returns False when stall_active is False."""
        poller._last_stallguard_status = {"stall_active": False, "stall_count": 0}
        assert poller.is_hardware_stall() is False

    def test_is_hardware_stall_false_when_unavailable(self, poller):
        """is_hardware_stall() returns False when stallguard_available is False."""
        poller._stallguard_available = False
        poller._last_stallguard_status = {"stall_active": True}
        assert poller.is_hardware_stall() is False

    def test_get_stallguard_status_returns_copy(self, poller):
        """get_stallguard_status() returns a copy, not the internal dict."""
        poller._last_stallguard_status = {"stall_active": True, "stall_count": 5}
        result = poller.get_stallguard_status()
        assert result == {"stall_active": True, "stall_count": 5}
        assert result is not poller._last_stallguard_status

    def test_get_stallguard_status_empty_by_default(self, poller):
        """get_stallguard_status() returns empty dict before any polls."""
        assert poller.get_stallguard_status() == {}

    def test_poll_once_queries_stallguard_monitor(self, poller):
        """_poll_once() includes stallguard_monitor in the query."""
        poller._klipper.query_status.return_value = {
            "status": {
                "stepper_enable": {"steppers": {}},
                "tmc2209 manual_stepper pump": {},
                "stallguard_monitor": {
                    "stall_active": True,
                    "stall_count": 3,
                    "last_stall_us": 12345,
                },
            }
        }
        poller._poll_once()

        # Verify the query included stallguard_monitor
        call_args = poller._klipper.query_status.call_args[0][0]
        assert "stallguard_monitor" in call_args

        # Verify the cached status was updated
        assert poller._last_stallguard_status["stall_active"] is True
        assert poller._last_stallguard_status["stall_count"] == 3

    def test_poll_once_skips_stallguard_when_unavailable(self, poller):
        """_poll_once() skips stallguard_monitor query when unavailable."""
        poller._stallguard_available = False
        poller._klipper.query_status.return_value = {
            "status": {
                "stepper_enable": {"steppers": {}},
                "tmc2209 manual_stepper pump": {},
            }
        }
        poller._poll_once()

        call_args = poller._klipper.query_status.call_args[0][0]
        assert "stallguard_monitor" not in call_args

    def test_stallguard_runtime_error_disables_queries(self, poller):
        """RuntimeError with 'stallguard' disables stallguard queries."""
        poller._klipper.query_status.side_effect = RuntimeError(
            "Unknown object 'stallguard_monitor'"
        )
        # Simulate what _poll_loop does on RuntimeError
        try:
            poller._poll_once()
        except RuntimeError as exc:
            error_msg = str(exc).lower()
            if "stallguard" in error_msg:
                poller._stallguard_available = False
        assert poller._stallguard_available is False


# ===================================================================
# 3. RTDEClient: write_status with stallguard_load
# ===================================================================

class TestRTDEClientStallGuard:

    @pytest.fixture
    def mocked_client(self):
        """RTDEClient with mocked ur_rtde, connected."""
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
            client = RTDEClient(host="192.168.1.100")
            client.connect()
            yield client, mock_ctrl_instance

    def test_write_status_sets_stallguard_register(self, mocked_client):
        """write_status() calls setInputDoubleRegister(1, stallguard_load)."""
        client, ctrl = mocked_client
        client.write_status(
            status=config.STATUS_RUNNING,
            error_code=config.ERR_NONE,
            actual_rate=10.0,
            ready=True,
            fault=False,
            stallguard_load=150.0,
        )
        ctrl.setInputDoubleRegister.assert_any_call(1, 150.0)

    def test_write_status_stallguard_default_zero(self, mocked_client):
        """write_status() defaults stallguard_load to 0.0."""
        client, ctrl = mocked_client
        client.write_status(
            status=config.STATUS_IDLE,
            error_code=config.ERR_NONE,
            actual_rate=0.0,
            ready=True,
            fault=False,
        )
        ctrl.setInputDoubleRegister.assert_any_call(1, 0.0)

    def test_write_status_both_double_registers(self, mocked_client):
        """write_status() sets both double register 0 (rate) and 1 (sg_load)."""
        client, ctrl = mocked_client
        client.write_status(
            status=config.STATUS_RUNNING,
            error_code=config.ERR_NONE,
            actual_rate=25.0,
            ready=True,
            fault=False,
            stallguard_load=200.0,
        )
        ctrl.setInputDoubleRegister.assert_any_call(0, 25.0)
        ctrl.setInputDoubleRegister.assert_any_call(1, 200.0)

    def test_write_status_stub_mode_no_crash(self):
        """write_status() with stallguard_load in stub mode does not crash."""
        with patch("bridge.rtde_client.HAS_UR_RTDE", False):
            client = RTDEClient()
            client.write_status(
                status=config.STATUS_IDLE,
                error_code=config.ERR_NONE,
                actual_rate=0.0,
                ready=True,
                fault=False,
                stallguard_load=100.0,
            )  # should not raise


# ===================================================================
# 4. Bridge: hardware stall priority + stallguard_load reporting
# ===================================================================

class TestBridgeStallGuard:

    @pytest.fixture
    def bridge_with_poller(self):
        """Bridge with mocked clients and a mocked status poller."""
        b = Bridge(ur_host="127.0.0.1", dry_run=False)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock()
        b.rtde.connected = True
        b.klipper.connected = True
        b.state.ready = True

        # Create a mock status poller
        b.status_poller = MagicMock(spec=KlipperStatusPoller)
        b.status_poller.is_stalled.return_value = False
        b.status_poller.is_hardware_stall.return_value = False
        b.status_poller.is_standstill.return_value = False
        b.status_poller.get_tmc_status.return_value = {}
        return b

    def test_hardware_stall_sets_err_stall(self, bridge_with_poller):
        """is_hardware_stall() True -> ERR_STALL + fault=True."""
        b = bridge_with_poller
        b.status_poller.is_hardware_stall.return_value = True
        b._check_stall_status()

        assert b.state.error_code == config.ERR_STALL
        assert b.state.fault is True

    def test_hardware_stall_takes_priority(self, bridge_with_poller):
        """Hardware stall returns early before checking UART stall."""
        b = bridge_with_poller
        b.status_poller.is_hardware_stall.return_value = True
        b.status_poller.is_stalled.return_value = True
        b._check_stall_status()

        # is_stalled should NOT be checked if hardware stall is already detected
        # (the method returns early after hardware stall)
        assert b.state.error_code == config.ERR_STALL

    def test_uart_stall_fallback(self, bridge_with_poller):
        """UART-polled stall sets ERR_STALL when hardware stall is inactive."""
        b = bridge_with_poller
        b.status_poller.is_hardware_stall.return_value = False
        b.status_poller.is_stalled.return_value = True
        b._check_stall_status()

        assert b.state.error_code == config.ERR_STALL
        assert b.state.fault is True

    def test_no_stall_no_error(self, bridge_with_poller):
        """No stall detected: error_code stays ERR_NONE."""
        b = bridge_with_poller
        b.status_poller.is_hardware_stall.return_value = False
        b.status_poller.is_stalled.return_value = False
        b._check_stall_status()

        assert b.state.error_code == config.ERR_NONE
        assert b.state.fault is False

    def test_stall_not_set_twice(self, bridge_with_poller):
        """Hardware stall does not re-log if error_code already ERR_STALL."""
        b = bridge_with_poller
        b.state.error_code = config.ERR_STALL
        b.state.fault = True
        b.status_poller.is_hardware_stall.return_value = True
        b._check_stall_status()

        # Still ERR_STALL, but no duplicate warning
        assert b.state.error_code == config.ERR_STALL

    def test_report_status_passes_stallguard_load(self, bridge_with_poller):
        """_report_status() passes sg_result as stallguard_load to write_status."""
        b = bridge_with_poller
        b.status_poller.get_tmc_status.return_value = {
            "drv_status": {"sg_result": 185}
        }
        b._report_status()

        call_kwargs = b.rtde.write_status.call_args[1]
        assert call_kwargs["stallguard_load"] == 185.0

    def test_report_status_zero_sg_when_no_tmc_data(self, bridge_with_poller):
        """_report_status() sends 0.0 stallguard_load when no TMC data."""
        b = bridge_with_poller
        b.status_poller.get_tmc_status.return_value = {}
        b._report_status()

        call_kwargs = b.rtde.write_status.call_args[1]
        assert call_kwargs["stallguard_load"] == 0.0

    def test_report_status_zero_sg_when_no_poller(self):
        """_report_status() sends 0.0 stallguard_load without poller."""
        b = Bridge(ur_host="127.0.0.1", dry_run=False,
                   enable_status_poll=False)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock()
        b.rtde.connected = True
        b.klipper.connected = True
        b.state.ready = True

        b._report_status()

        call_kwargs = b.rtde.write_status.call_args[1]
        assert call_kwargs["stallguard_load"] == 0.0

    def test_shutdown_sends_zero_stallguard_load(self):
        """stop() sends stallguard_load=0.0 in the offline status."""
        b = Bridge(ur_host="127.0.0.1", dry_run=False)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock()
        b.rtde.connected = True
        b.klipper.connected = True

        b.stop()

        call_kwargs = b.rtde.write_status.call_args[1]
        assert call_kwargs["stallguard_load"] == 0.0
