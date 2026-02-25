"""
Unit tests for bridge.bridge_daemon — Bridge and BridgeState.

Tests command translation, e-stop handling, mode switching, rate clamping,
homing, reconnection logic, status reporting, shutdown, dry-run mode,
main loop mechanics, subsystem integration (watchdog, dashboard, data
logging, stall detection, extrusion profiles), and CLI entry point.

All external I/O (RTDEClient, KlipperClient, time) is mocked.
"""

import time as real_time

import pytest
from unittest.mock import MagicMock, patch

from bridge import config
from bridge.bridge_daemon import Bridge, main
from bridge.rtde_client import RTDEClient
from bridge.klipper_client import KlipperClient
from bridge.klipper_status import KlipperStatusPoller
from bridge.data_logger import DataLogger
from bridge.dashboard_client import DashboardClient, DashboardPoller
from bridge.stallguard_accumulator import StallGuardAccumulator


# ===================================================================
# 6.1  BridgeState Initialization
# ===================================================================

class TestBridgeState:

    def test_initial_state(self, bridge_state):
        """BridgeState() has safe initial values."""
        s = bridge_state
        assert s.stepper_enabled is False
        assert s.current_mode == config.MODE_OFF
        assert s.current_rate == 0.0
        assert s.actual_rate == 0.0
        assert s.status == config.STATUS_IDLE
        assert s.error_code == config.ERR_NONE
        assert s.fault is False
        assert s.ready is False
        assert s.last_command_time == 0.0


# ===================================================================
# 6.2  Command Translation: Mode Handling
# ===================================================================

class TestModeHandling:

    def test_mode_off_when_already_off(self, bridge, make_cmd):
        """MODE_OFF when already off: no Klipper calls, state stays IDLE."""
        bridge.state.current_mode = config.MODE_OFF
        cmd = make_cmd(enable=True, mode=config.MODE_OFF)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_set_position.assert_not_called()
        bridge.klipper.stepper_move.assert_not_called()
        assert bridge.state.status == config.STATUS_IDLE

    def test_mode_off_stops_running_extrusion(self, bridge, make_cmd):
        """MODE_OFF when mode was EXTRUDE: stops extrusion."""
        bridge.state.current_mode = config.MODE_EXTRUDE
        bridge.state.stepper_enabled = True
        cmd = make_cmd(enable=True, mode=config.MODE_OFF)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_set_position.assert_called_once_with(config.STEPPER_NAME, 0.0)
        assert bridge.state.current_mode == config.MODE_OFF
        assert bridge.state.status == config.STATUS_IDLE

    def test_mode_extrude_at_valid_rate(self, bridge, make_cmd):
        """MODE_EXTRUDE with valid rate: enables stepper and issues move."""
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=25.0)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_enable.assert_called_once_with(config.STEPPER_NAME)
        bridge.klipper.stepper_move.assert_called_once_with(
            config.STEPPER_NAME, 250.0, 25.0, config.DEFAULT_ACCEL
        )
        assert bridge.state.status == config.STATUS_RUNNING

    def test_mode_extrude_direction_positive(self, bridge, make_cmd):
        """MODE_EXTRUDE produces positive distance."""
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=10.0)
        bridge._process_commands(cmd)

        # distance = rate * 10.0 = 100.0 (positive for extrude)
        call_args = bridge.klipper.stepper_move.call_args
        distance = call_args[0][1]  # second positional arg
        assert distance == 100.0

    def test_mode_retract_direction_negative(self, bridge, make_cmd):
        """MODE_RETRACT produces negative distance."""
        cmd = make_cmd(enable=True, mode=config.MODE_RETRACT, extrusion_rate=10.0)
        bridge._process_commands(cmd)

        call_args = bridge.klipper.stepper_move.call_args
        distance = call_args[0][1]
        assert distance == -100.0

    def test_mode_retract_at_valid_rate(self, bridge, make_cmd):
        """MODE_RETRACT with valid rate: move with negative distance, correct speed."""
        cmd = make_cmd(enable=True, mode=config.MODE_RETRACT, extrusion_rate=15.0)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_move.assert_called_once_with(
            config.STEPPER_NAME, -150.0, 15.0, config.DEFAULT_ACCEL
        )


# ===================================================================
# 6.3  Rate Clamping
# ===================================================================

class TestRateClamping:

    def test_rate_clamped_to_max(self, bridge, make_cmd):
        """Rate exceeding MAX_EXTRUSION_RATE is clamped to 50.0."""
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=100.0)
        bridge._process_commands(cmd)

        call_args = bridge.klipper.stepper_move.call_args
        speed = call_args[0][2]  # third positional arg
        assert speed == config.MAX_EXTRUSION_RATE  # 50.0

    def test_rate_clamped_to_zero_floor(self, bridge, make_cmd):
        """Negative rate is clamped to 0.0."""
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=-5.0)
        bridge._process_commands(cmd)

        # Rate 0.0 is below deadband, so _stop_extrusion() is called instead of move
        bridge.klipper.stepper_move.assert_not_called()

    def test_rate_at_max_allowed(self, bridge, make_cmd):
        """Rate exactly at MAX_EXTRUSION_RATE passes through."""
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=50.0)
        bridge._process_commands(cmd)

        call_args = bridge.klipper.stepper_move.call_args
        speed = call_args[0][2]
        assert speed == 50.0

    def test_rate_zero_stops_extrusion(self, bridge, make_cmd):
        """Rate 0.0 in EXTRUDE mode: below deadband, calls _stop_extrusion()."""
        bridge.state.stepper_enabled = True
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=0.0)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_move.assert_not_called()
        bridge.klipper.stepper_set_position.assert_called_once_with(config.STEPPER_NAME, 0.0)

    def test_rate_at_deadband_boundary(self, bridge, make_cmd):
        """Rate exactly at 0.01 (deadband): treated as zero, stops extrusion."""
        bridge.state.stepper_enabled = True
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=0.01)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_move.assert_not_called()
        bridge.klipper.stepper_set_position.assert_called_once_with(config.STEPPER_NAME, 0.0)

    def test_rate_just_above_deadband(self, bridge, make_cmd):
        """Rate 0.02 is above deadband: move command issued."""
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=0.02)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_move.assert_called_once()


# ===================================================================
# 6.4  E-Stop Handling
# ===================================================================

class TestEStop:

    def test_estop_calls_emergency_stop(self, bridge, make_cmd):
        """E-stop command triggers klipper.emergency_stop()."""
        cmd = make_cmd(estop=True)
        bridge._process_commands(cmd)
        bridge.klipper.emergency_stop.assert_called_once()

    def test_estop_disables_stepper_state(self, bridge, make_cmd):
        """E-stop sets state: stepper_enabled=False, STATUS_ERROR, MODE_OFF, rate=0."""
        bridge.state.stepper_enabled = True
        bridge.state.current_mode = config.MODE_EXTRUDE
        bridge.state.current_rate = 25.0

        cmd = make_cmd(estop=True)
        bridge._process_commands(cmd)

        assert bridge.state.stepper_enabled is False
        assert bridge.state.status == config.STATUS_ERROR
        assert bridge.state.current_mode == config.MODE_OFF
        assert bridge.state.current_rate == 0.0

    def test_estop_takes_priority_over_extrude(self, bridge, make_cmd):
        """E-stop executes even when mode=EXTRUDE is also set."""
        cmd = make_cmd(estop=True, mode=config.MODE_EXTRUDE, extrusion_rate=25.0, enable=True)
        bridge._process_commands(cmd)

        bridge.klipper.emergency_stop.assert_called_once()
        bridge.klipper.stepper_move.assert_not_called()

    def test_estop_takes_priority_over_home(self, bridge, make_cmd):
        """E-stop executes even when home=True is also set."""
        cmd = make_cmd(estop=True, home=True)
        bridge._process_commands(cmd)

        bridge.klipper.emergency_stop.assert_called_once()
        bridge.klipper.stepper_set_position.assert_not_called()

    def test_estop_in_dry_run_skips_klipper_call(self, dry_run_bridge, make_cmd):
        """In dry_run mode, e-stop updates state but does NOT call Klipper."""
        cmd = make_cmd(estop=True)
        dry_run_bridge._process_commands(cmd)

        dry_run_bridge.klipper.emergency_stop.assert_not_called()
        assert dry_run_bridge.state.status == config.STATUS_ERROR
        assert dry_run_bridge.state.stepper_enabled is False


# ===================================================================
# 6.5  Homing
# ===================================================================

class TestHoming:

    def test_homing_sets_position_zero(self, bridge, make_cmd):
        """Homing calls stepper_set_position(name, 0.0)."""
        cmd = make_cmd(home=True, enable=True)
        bridge._process_commands(cmd)
        bridge.klipper.stepper_set_position.assert_called_once_with(config.STEPPER_NAME, 0.0)

    def test_homing_status_transitions(self, bridge, make_cmd):
        """After homing, status returns to IDLE."""
        cmd = make_cmd(home=True, enable=True)
        bridge._process_commands(cmd)
        assert bridge.state.status == config.STATUS_IDLE

    def test_homing_ignored_when_already_homing(self, bridge, make_cmd):
        """Homing request is ignored when status is already HOMING."""
        bridge.state.status = config.STATUS_HOMING
        cmd = make_cmd(home=True, enable=True)
        bridge._process_commands(cmd)
        bridge.klipper.stepper_set_position.assert_not_called()

    def test_homing_error_sets_error_status(self, bridge, make_cmd):
        """If stepper_set_position raises, status becomes ERROR."""
        bridge.klipper.stepper_set_position.side_effect = RuntimeError("homing failed")
        cmd = make_cmd(home=True, enable=True)
        bridge._process_commands(cmd)
        assert bridge.state.status == config.STATUS_ERROR

    def test_homing_dry_run_skips_klipper(self, dry_run_bridge, make_cmd):
        """In dry_run mode, homing updates state without calling Klipper."""
        cmd = make_cmd(home=True, enable=True)
        dry_run_bridge._process_commands(cmd)
        dry_run_bridge.klipper.stepper_set_position.assert_not_called()
        assert dry_run_bridge.state.status == config.STATUS_IDLE


# ===================================================================
# 6.6  Enable/Disable
# ===================================================================

class TestEnableDisable:

    def test_disable_stops_enabled_stepper(self, bridge, make_cmd):
        """enable=False when stepper was enabled calls _stop_extrusion()."""
        bridge.state.stepper_enabled = True
        cmd = make_cmd(enable=False)
        bridge._process_commands(cmd)
        bridge.klipper.stepper_set_position.assert_called_once_with(config.STEPPER_NAME, 0.0)

    def test_disable_noop_when_already_disabled(self, bridge, make_cmd):
        """enable=False when stepper already disabled: no Klipper calls."""
        bridge.state.stepper_enabled = False
        cmd = make_cmd(enable=False)
        bridge._process_commands(cmd)
        bridge.klipper.stepper_set_position.assert_not_called()
        bridge.klipper.stepper_move.assert_not_called()

    def test_enable_activates_stepper_on_first_move(self, bridge, make_cmd):
        """First extrude command calls stepper_enable() before stepper_move()."""
        assert bridge.state.stepper_enabled is False
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=10.0)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_enable.assert_called_once_with(config.STEPPER_NAME)
        bridge.klipper.stepper_move.assert_called_once()

    def test_enable_does_not_re_enable(self, bridge, make_cmd):
        """Stepper already enabled: stepper_enable NOT called again."""
        bridge.state.stepper_enabled = True
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=10.0)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_enable.assert_not_called()
        bridge.klipper.stepper_move.assert_called_once()


# ===================================================================
# 6.7  Extrusion Start/Stop Mechanics
# ===================================================================

class TestExtrusionMechanics:

    def test_set_extrusion_enables_stepper_first(self, bridge):
        """_set_extrusion() enables the stepper before issuing a move."""
        bridge.state.stepper_enabled = False
        bridge._set_extrusion(20.0)

        bridge.klipper.stepper_enable.assert_called_once_with(config.STEPPER_NAME)
        bridge.klipper.stepper_move.assert_called_once()
        assert bridge.state.stepper_enabled is True

    def test_set_extrusion_skips_enable_if_already_enabled(self, bridge):
        """_set_extrusion() does not re-enable already-enabled stepper."""
        bridge.state.stepper_enabled = True
        bridge._set_extrusion(20.0)

        bridge.klipper.stepper_enable.assert_not_called()
        bridge.klipper.stepper_move.assert_called_once()

    def test_set_extrusion_calculates_distance(self, bridge):
        """_set_extrusion(20.0): distance = 20.0 * 10.0 = 200.0, speed = 20.0."""
        bridge.state.stepper_enabled = True
        bridge._set_extrusion(20.0)

        call_args = bridge.klipper.stepper_move.call_args
        assert call_args[0][1] == 200.0   # distance
        assert call_args[0][2] == 20.0    # speed

    def test_set_extrusion_uses_default_accel(self, bridge):
        """_set_extrusion() passes config.DEFAULT_ACCEL."""
        bridge.state.stepper_enabled = True
        bridge._set_extrusion(10.0)

        call_args = bridge.klipper.stepper_move.call_args
        assert call_args[0][3] == config.DEFAULT_ACCEL

    def test_set_extrusion_updates_last_command_time(self, bridge):
        """_set_extrusion() updates state.last_command_time."""
        bridge.state.stepper_enabled = True
        before = real_time.monotonic()
        bridge._set_extrusion(10.0)
        after = real_time.monotonic()

        assert before <= bridge.state.last_command_time <= after

    def test_set_extrusion_error_sets_error_state(self, bridge):
        """_set_extrusion() catches move errors and sets error state."""
        bridge.state.stepper_enabled = True
        bridge.klipper.stepper_move.side_effect = RuntimeError("move failed")
        bridge._set_extrusion(10.0)

        assert bridge.state.status == config.STATUS_ERROR
        assert bridge.state.error_code == config.ERR_COMMS_LOST

    def test_stop_extrusion_resets_position(self, bridge):
        """_stop_extrusion() calls stepper_set_position(name, 0.0)."""
        bridge._stop_extrusion()
        bridge.klipper.stepper_set_position.assert_called_once_with(config.STEPPER_NAME, 0.0)

    def test_stop_extrusion_resets_state(self, bridge):
        """_stop_extrusion() resets mode, rate, and status."""
        bridge.state.current_mode = config.MODE_EXTRUDE
        bridge.state.current_rate = 25.0
        bridge.state.status = config.STATUS_RUNNING

        bridge._stop_extrusion()

        assert bridge.state.current_mode == config.MODE_OFF
        assert bridge.state.current_rate == 0.0
        assert bridge.state.status == config.STATUS_IDLE

    def test_stop_extrusion_error_logged(self, bridge):
        """_stop_extrusion() catches exceptions without crashing."""
        bridge.klipper.stepper_set_position.side_effect = RuntimeError("stop failed")
        bridge._stop_extrusion()  # should not raise


# ===================================================================
# 6.8  Dry Run Mode
# ===================================================================

class TestDryRun:

    def test_dry_run_extrude_no_klipper_calls(self, dry_run_bridge, make_cmd):
        """In dry_run, extrude commands do not call Klipper."""
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=25.0)
        dry_run_bridge._process_commands(cmd)

        dry_run_bridge.klipper.stepper_move.assert_not_called()
        dry_run_bridge.klipper.stepper_enable.assert_not_called()

    def test_dry_run_stop_no_klipper_calls(self, dry_run_bridge, make_cmd):
        """In dry_run, stop does not call Klipper but state transitions."""
        dry_run_bridge.state.current_mode = config.MODE_EXTRUDE
        dry_run_bridge.state.stepper_enabled = True
        cmd = make_cmd(enable=True, mode=config.MODE_OFF)
        dry_run_bridge._process_commands(cmd)

        dry_run_bridge.klipper.stepper_set_position.assert_not_called()
        assert dry_run_bridge.state.current_mode == config.MODE_OFF
        assert dry_run_bridge.state.status == config.STATUS_IDLE

    def test_dry_run_estop_no_klipper_calls(self, dry_run_bridge, make_cmd):
        """In dry_run, e-stop does not call Klipper but state updates."""
        cmd = make_cmd(estop=True)
        dry_run_bridge._process_commands(cmd)

        dry_run_bridge.klipper.emergency_stop.assert_not_called()
        assert dry_run_bridge.state.status == config.STATUS_ERROR

    def test_dry_run_homing_no_klipper_calls(self, dry_run_bridge, make_cmd):
        """In dry_run, homing does not call Klipper."""
        cmd = make_cmd(home=True, enable=True)
        dry_run_bridge._process_commands(cmd)

        dry_run_bridge.klipper.stepper_set_position.assert_not_called()
        assert dry_run_bridge.state.status == config.STATUS_IDLE

    def test_dry_run_shutdown_no_klipper_calls(self, dry_run_bridge):
        """In dry_run, stop() does not call stepper_disable."""
        dry_run_bridge.stop()
        dry_run_bridge.klipper.stepper_disable.assert_not_called()


# ===================================================================
# 6.9  Status Reporting
# ===================================================================

class TestStatusReporting:

    def test_report_status_writes_all_fields(self, bridge, make_cmd):
        """_report_status() calls write_status with correct fields."""
        bridge.state.status = config.STATUS_RUNNING
        bridge.state.error_code = config.ERR_NONE
        bridge.state.current_rate = 25.0
        bridge.state.ready = True
        bridge.state.fault = False

        bridge._report_status()

        bridge.rtde.write_status.assert_called_once_with(
            status=config.STATUS_RUNNING,
            error_code=config.ERR_NONE,
            actual_rate=25.0,
            ready=True,
            fault=False,
            stallguard_load=0.0,
        )

    def test_report_status_ready_and_fault(self, bridge):
        """ready AND fault: ready parameter is False (ready AND NOT fault)."""
        bridge.state.ready = True
        bridge.state.fault = True

        bridge._report_status()

        call_kwargs = bridge.rtde.write_status.call_args[1]
        assert call_kwargs["ready"] is False

    def test_report_status_ready_no_fault(self, bridge):
        """ready=True, fault=False: ready parameter is True."""
        bridge.state.ready = True
        bridge.state.fault = False

        bridge._report_status()

        call_kwargs = bridge.rtde.write_status.call_args[1]
        assert call_kwargs["ready"] is True

    def test_report_status_failure_logged(self, bridge):
        """write_status failure is caught and does not crash."""
        bridge.rtde.write_status.side_effect = RuntimeError("RTDE error")
        bridge._report_status()  # should not raise


# ===================================================================
# 6.10  Connection Loss and Reconnection
# ===================================================================

class TestConnectionLoss:

    def test_tick_connection_error_triggers_estop(self, bridge):
        """ConnectionError in _tick() sets STATUS_ERROR and ERR_COMMS_LOST."""
        bridge.rtde.read_commands.side_effect = ConnectionError("lost")
        bridge._running = True  # needed for _connect_all retry loop

        # Prevent _connect_all from looping forever
        def stop_running(*args, **kwargs):
            bridge._running = False
        bridge.rtde.connect.side_effect = stop_running

        bridge._tick()

        assert bridge.state.status == config.STATUS_ERROR
        assert bridge.state.error_code == config.ERR_COMMS_LOST
        assert bridge.state.fault is True

    def test_tick_connection_error_attempts_reconnect(self, bridge):
        """ConnectionError triggers _connect_all()."""
        bridge.rtde.read_commands.side_effect = ConnectionError("lost")
        bridge._running = True

        # Track _connect_all being called
        with patch.object(bridge, "_connect_all") as mock_connect:
            bridge._tick()
            mock_connect.assert_called_once()

    def test_tick_connection_error_tries_emergency_stop(self, bridge):
        """ConnectionError triggers best-effort stepper_disable."""
        bridge.rtde.read_commands.side_effect = ConnectionError("lost")
        bridge._running = True

        with patch.object(bridge, "_connect_all"):
            bridge._tick()

        bridge.klipper.stepper_disable.assert_called_once_with(config.STEPPER_NAME)

    def test_try_emergency_stop_suppresses_exceptions(self, bridge):
        """_try_emergency_stop() suppresses exceptions from stepper_disable."""
        bridge.klipper.stepper_disable.side_effect = RuntimeError("failed")
        bridge._try_emergency_stop()  # should not raise

    def test_try_emergency_stop_skips_in_dry_run(self, dry_run_bridge):
        """_try_emergency_stop() does nothing in dry_run mode."""
        dry_run_bridge._try_emergency_stop()
        dry_run_bridge.klipper.stepper_disable.assert_not_called()

    def test_try_emergency_stop_skips_when_disconnected(self, bridge):
        """_try_emergency_stop() skips when Klipper is disconnected."""
        bridge.klipper.connected = False
        bridge._try_emergency_stop()
        bridge.klipper.stepper_disable.assert_not_called()


# ===================================================================
# 6.11  Shutdown (stop())
# ===================================================================

class TestShutdown:

    def test_stop_disables_stepper(self, bridge):
        """stop() calls stepper_disable("pump")."""
        bridge.stop()
        bridge.klipper.stepper_disable.assert_called_once_with(config.STEPPER_NAME)

    def test_stop_reports_offline_status(self, bridge):
        """stop() writes IDLE status with ready=False."""
        bridge.stop()
        bridge.rtde.write_status.assert_called_once_with(
            status=config.STATUS_IDLE,
            error_code=config.ERR_NONE,
            actual_rate=0.0,
            ready=False,
            fault=False,
            stallguard_load=0.0,
        )

    def test_stop_disconnects_both_clients(self, bridge):
        """stop() disconnects RTDE, Klipper, and status socket."""
        bridge.stop()
        bridge.rtde.disconnect.assert_called_once()
        bridge.klipper.disconnect.assert_called_once()
        bridge._status_klipper.disconnect.assert_called_once()

    def test_stop_sets_running_false(self, bridge):
        """stop() sets _running to False."""
        bridge._running = True
        bridge.stop()
        assert bridge._running is False

    def test_stop_handles_klipper_error_gracefully(self, bridge):
        """stop() continues even if stepper_disable raises."""
        bridge.klipper.stepper_disable.side_effect = RuntimeError("klipper down")
        bridge.stop()  # should not raise

        # Still reports status and disconnects
        bridge.rtde.write_status.assert_called_once()
        bridge.rtde.disconnect.assert_called_once()
        bridge.klipper.disconnect.assert_called_once()

    def test_stop_handles_rtde_error_gracefully(self, bridge):
        """stop() continues even if write_status raises."""
        bridge.rtde.write_status.side_effect = RuntimeError("rtde down")
        bridge.stop()  # should not raise

        # Still disconnects both
        bridge.rtde.disconnect.assert_called_once()
        bridge.klipper.disconnect.assert_called_once()


# ===================================================================
# 6.12  Main Loop Mechanics
# ===================================================================

class TestMainLoop:

    def test_start_connects_both(self, bridge):
        """start() calls _connect_all and sets state.ready and status."""
        call_count = 0

        def tick_then_stop():
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                bridge._running = False

        with patch.object(bridge, "_connect_all") as mock_connect, \
             patch.object(bridge, "_tick", side_effect=tick_then_stop), \
             patch("bridge.bridge_daemon.time.sleep"):
            bridge.start()

        # _connect_all was called once during start()
        mock_connect.assert_called_once()
        # state.ready was set to True before the loop (still True — stop() doesn't clear it)
        assert bridge.state.ready is True

    def test_start_keyboard_interrupt_calls_stop(self, bridge):
        """KeyboardInterrupt in the loop triggers stop()."""
        with patch.object(bridge, "_connect_all"), \
             patch.object(bridge, "_tick", side_effect=KeyboardInterrupt), \
             patch.object(bridge, "stop") as mock_stop:
            bridge.start()
            mock_stop.assert_called_once()

    def test_start_loop_sleeps_correct_period(self, bridge):
        """Loop sleeps for LOOP_PERIOD - elapsed time."""
        tick_count = 0

        def tick_once():
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 1:
                bridge._running = False

        # Simulate monotonic returning: start=0.0, after_tick=0.001
        time_values = iter([0.0, 0.001])

        with patch.object(bridge, "_connect_all"), \
             patch.object(bridge, "_tick", side_effect=tick_once), \
             patch("bridge.bridge_daemon.time.monotonic", side_effect=time_values), \
             patch("bridge.bridge_daemon.time.sleep") as mock_sleep:
            bridge.start()

        expected_sleep = config.LOOP_PERIOD - 0.001
        mock_sleep.assert_called_once()
        actual_sleep = mock_sleep.call_args[0][0]
        assert actual_sleep == pytest.approx(expected_sleep, abs=0.0001)

    def test_start_loop_no_sleep_when_overrun(self, bridge):
        """When tick takes longer than LOOP_PERIOD, no sleep is called."""
        tick_count = 0

        def tick_once():
            nonlocal tick_count
            tick_count += 1
            if tick_count >= 1:
                bridge._running = False

        # elapsed = 0.1 which is > LOOP_PERIOD (0.008)
        time_values = iter([0.0, 0.1])

        with patch.object(bridge, "_connect_all"), \
             patch.object(bridge, "_tick", side_effect=tick_once), \
             patch("bridge.bridge_daemon.time.monotonic", side_effect=time_values), \
             patch("bridge.bridge_daemon.time.sleep") as mock_sleep:
            bridge.start()

        mock_sleep.assert_not_called()


# ===================================================================
# Appendix A: Command-to-G-code Translation Matrix (comprehensive)
# ===================================================================

class TestTranslationMatrix:
    """End-to-end command translation tests from Appendix A of the design doc."""

    def test_estop_any_state(self, bridge, make_cmd):
        """estop=True (any other fields): emergency_stop(), STATUS_ERROR."""
        cmd = make_cmd(estop=True, enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=25.0)
        bridge._process_commands(cmd)

        bridge.klipper.emergency_stop.assert_called_once()
        assert bridge.state.status == config.STATUS_ERROR
        assert bridge.state.current_mode == config.MODE_OFF
        assert bridge.state.current_rate == 0.0

    def test_home_command(self, bridge, make_cmd):
        """home=True: stepper_set_position(0.0), status transitions HOMING -> IDLE."""
        cmd = make_cmd(home=True, enable=True)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_set_position.assert_called_with(config.STEPPER_NAME, 0.0)
        assert bridge.state.status == config.STATUS_IDLE

    def test_disable_when_enabled(self, bridge, make_cmd):
        """enable=False, stepper was enabled: stepper_set_position(0.0)."""
        bridge.state.stepper_enabled = True
        cmd = make_cmd(enable=False)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_set_position.assert_called_with(config.STEPPER_NAME, 0.0)

    def test_mode_off_while_extruding(self, bridge, make_cmd):
        """enable=True, mode=OFF, was extruding: stepper_set_position(0.0)."""
        bridge.state.current_mode = config.MODE_EXTRUDE
        bridge.state.stepper_enabled = True
        cmd = make_cmd(enable=True, mode=config.MODE_OFF)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_set_position.assert_called_with(config.STEPPER_NAME, 0.0)
        assert bridge.state.current_mode == config.MODE_OFF

    def test_extrude_25_mm_s(self, bridge, make_cmd):
        """enable=True, mode=EXTRUDE, rate=25.0: MOVE=250.0 SPEED=25.0 ACCEL=200."""
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=25.0)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_enable.assert_called_with(config.STEPPER_NAME)
        bridge.klipper.stepper_move.assert_called_with(
            config.STEPPER_NAME, 250.0, 25.0, config.DEFAULT_ACCEL
        )
        assert bridge.state.status == config.STATUS_RUNNING
        assert bridge.state.current_mode == config.MODE_EXTRUDE

    def test_retract_15_mm_s(self, bridge, make_cmd):
        """enable=True, mode=RETRACT, rate=15.0: MOVE=-150.0 SPEED=15.0."""
        cmd = make_cmd(enable=True, mode=config.MODE_RETRACT, extrusion_rate=15.0)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_move.assert_called_with(
            config.STEPPER_NAME, -150.0, 15.0, config.DEFAULT_ACCEL
        )
        assert bridge.state.status == config.STATUS_RUNNING

    def test_extrude_below_deadband(self, bridge, make_cmd):
        """enable=True, mode=EXTRUDE, rate=0.005: below deadband, stops."""
        bridge.state.stepper_enabled = True
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=0.005)
        bridge._process_commands(cmd)

        bridge.klipper.stepper_move.assert_not_called()
        bridge.klipper.stepper_set_position.assert_called_with(config.STEPPER_NAME, 0.0)

    def test_extrude_clamped_to_50(self, bridge, make_cmd):
        """enable=True, mode=EXTRUDE, rate=100.0: clamped to 50.0."""
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=100.0)
        bridge._process_commands(cmd)

        call_args = bridge.klipper.stepper_move.call_args
        distance = call_args[0][1]  # 50.0 * 10.0 = 500.0
        speed = call_args[0][2]     # 50.0
        assert distance == 500.0
        assert speed == 50.0
        assert bridge.state.status == config.STATUS_RUNNING


# ===================================================================
# _tick() integration: read -> process -> report
# ===================================================================

class TestTickIntegration:
    """Tests that _tick() wires read_commands -> _process_commands -> _report_status."""

    def test_tick_reads_processes_reports(self, bridge, make_cmd):
        """A single _tick() reads commands, processes them, and reports status."""
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=20.0)
        bridge.rtde.read_commands.return_value = cmd

        bridge._tick()

        bridge.rtde.read_commands.assert_called_once()
        bridge.klipper.stepper_move.assert_called_once()
        bridge.rtde.write_status.assert_called_once()

    def test_tick_idle_cycle(self, bridge, make_cmd):
        """A single _tick() with all-off command: no stepper calls, reports IDLE."""
        cmd = make_cmd()  # all defaults = off
        bridge.rtde.read_commands.return_value = cmd

        bridge._tick()

        bridge.klipper.stepper_move.assert_not_called()
        bridge.rtde.write_status.assert_called_once()

        call_kwargs = bridge.rtde.write_status.call_args[1]
        assert call_kwargs["status"] == config.STATUS_IDLE


# ===================================================================
# Bridge construction with optional subsystems
# ===================================================================

class TestBridgeConstructor:

    def test_constructor_with_logging_enabled(self):
        """enable_logging=True creates a DataLogger instance."""
        b = Bridge(ur_host="127.0.0.1", enable_logging=True)
        assert b.data_logger is not None

    def test_constructor_with_dashboard_enabled(self):
        """enable_dashboard=True creates a DashboardClient instance."""
        b = Bridge(ur_host="127.0.0.1", enable_dashboard=True)
        assert b.dashboard is not None

    def test_constructor_with_sg_accumulator(self):
        """SG accumulator is created when both sg and status_poll are enabled."""
        b = Bridge(ur_host="127.0.0.1", enable_sg_accumulator=True,
                   enable_status_poll=True)
        assert b.sg_accumulator is not None

    def test_constructor_sg_accumulator_disabled_when_no_poll(self):
        """SG accumulator is None when status_poll is disabled."""
        b = Bridge(ur_host="127.0.0.1", enable_sg_accumulator=True,
                   enable_status_poll=False)
        assert b.sg_accumulator is None

    def test_constructor_no_dashboard_by_default(self):
        """Dashboard is None by default."""
        b = Bridge(ur_host="127.0.0.1")
        assert b.dashboard is None

    def test_constructor_creates_status_klipper_when_poll_enabled(self):
        """_status_klipper is a separate KlipperClient when status_poll is enabled."""
        b = Bridge(ur_host="127.0.0.1", enable_status_poll=True)
        assert b._status_klipper is not None
        assert isinstance(b._status_klipper, KlipperClient)
        assert b._status_klipper is not b.klipper

    def test_constructor_no_status_klipper_when_poll_disabled(self):
        """_status_klipper is None when status_poll is disabled."""
        b = Bridge(ur_host="127.0.0.1", enable_status_poll=False)
        assert b._status_klipper is None

    def test_constructor_poller_uses_status_klipper(self):
        """KlipperStatusPoller uses the dedicated _status_klipper, not main klipper."""
        b = Bridge(ur_host="127.0.0.1", enable_status_poll=True)
        assert b.status_poller is not None
        assert b.status_poller._klipper is b._status_klipper

    def test_constructor_custom_status_poll_interval(self):
        """Custom status_poll_interval is passed through to the poller."""
        b = Bridge(ur_host="127.0.0.1", enable_status_poll=True,
                   status_poll_interval=0.1)
        assert b.status_poller is not None
        assert b.status_poller._poll_interval == 0.1

    def test_constructor_sg_accumulator_uses_poll_interval_rate(self):
        """SG accumulator sample_rate_hz derived from status_poll_interval."""
        b = Bridge(ur_host="127.0.0.1", enable_status_poll=True,
                   status_poll_interval=0.1)
        assert b.sg_accumulator is not None
        # 1/0.1 = 10 Hz, 300s * 10 = 3000 capacity
        assert b.sg_accumulator.capacity == int(config.SG_ACCUMULATOR_DURATION_S * 10.0)


# ===================================================================
# _connect_all() retry loops
# ===================================================================

class TestConnectAll:

    def test_rtde_retry_on_failure(self, bridge):
        """_connect_all retries RTDE connection on failure."""
        bridge._running = True
        attempt = [0]

        def connect_side_effect():
            attempt[0] += 1
            if attempt[0] < 2:
                raise ConnectionError("refused")

        bridge.rtde.connect.side_effect = connect_side_effect
        bridge.klipper.connect.return_value = None
        bridge.klipper.get_info.return_value = {"state_message": "ready"}

        with patch("bridge.bridge_daemon.time.sleep"):
            bridge._connect_all()

        assert bridge.rtde.connect.call_count == 2

    def test_klipper_retry_on_failure(self, bridge):
        """_connect_all retries Klipper connection on failure."""
        bridge._running = True
        bridge.rtde.connect.return_value = None
        attempt = [0]

        def connect_side_effect():
            attempt[0] += 1
            if attempt[0] < 2:
                raise ConnectionError("socket not found")

        bridge.klipper.connect.side_effect = connect_side_effect
        bridge.klipper.get_info.return_value = {"state_message": "ready"}

        with patch("bridge.bridge_daemon.time.sleep"):
            bridge._connect_all()

        assert bridge.klipper.connect.call_count == 2

    def test_connect_all_with_dashboard(self):
        """_connect_all connects Dashboard Server when enabled."""
        b = Bridge(ur_host="127.0.0.1", enable_dashboard=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b._status_klipper = MagicMock(spec=KlipperClient)
        b.dashboard = MagicMock(spec=DashboardClient)
        b.dashboard.connected = True
        b._running = True
        b.klipper.get_info.return_value = {"state_message": "ready"}

        with patch("bridge.bridge_daemon.time.sleep"):
            b._connect_all()

        b.dashboard.connect.assert_called_once()

    def test_connect_all_dashboard_failure_non_critical(self):
        """Dashboard connection failure is non-critical — sets dashboard=None."""
        b = Bridge(ur_host="127.0.0.1", enable_dashboard=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b._status_klipper = MagicMock(spec=KlipperClient)
        b.dashboard = MagicMock(spec=DashboardClient)
        b.dashboard.connect.side_effect = ConnectionError("refused")
        b._running = True
        b.klipper.get_info.return_value = {"state_message": "ready"}

        with patch("bridge.bridge_daemon.time.sleep"):
            b._connect_all()

        assert b.dashboard is None

    def test_connect_all_stops_when_not_running(self, bridge):
        """_connect_all() exits RTDE retry loop when _running is False."""
        bridge._running = False
        bridge.rtde.connect.side_effect = ConnectionError("refused")

        with patch("bridge.bridge_daemon.time.sleep"):
            bridge._connect_all()

        # Should not have retried since _running is False
        bridge.rtde.connect.assert_not_called()

    def test_connect_all_connects_status_klipper(self, bridge):
        """_connect_all connects the dedicated status socket."""
        bridge._running = True
        bridge.klipper.get_info.return_value = {"state_message": "ready"}

        with patch("bridge.bridge_daemon.time.sleep"):
            bridge._connect_all()

        bridge._status_klipper.connect.assert_called_once()

    def test_connect_all_retries_status_klipper(self):
        """_connect_all retries status socket connection on failure."""
        b = Bridge(ur_host="127.0.0.1", enable_status_poll=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b._status_klipper = MagicMock(spec=KlipperClient)
        b._running = True
        b.klipper.get_info.return_value = {"state_message": "ready"}
        attempt = [0]

        def connect_side_effect():
            attempt[0] += 1
            if attempt[0] < 2:
                raise ConnectionError("socket not found")

        b._status_klipper.connect.side_effect = connect_side_effect

        with patch("bridge.bridge_daemon.time.sleep"):
            b._connect_all()

        assert b._status_klipper.connect.call_count == 2

    def test_connect_all_skips_status_klipper_when_disabled(self):
        """_connect_all skips status socket when status_poll is disabled."""
        b = Bridge(ur_host="127.0.0.1", enable_status_poll=False)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b._running = True
        b.klipper.get_info.return_value = {"state_message": "ready"}

        with patch("bridge.bridge_daemon.time.sleep"):
            b._connect_all()

        # _status_klipper is None, so no connect attempted
        assert b._status_klipper is None


# ===================================================================
# _log_robot_info()
# ===================================================================

class TestLogRobotInfo:

    def test_log_robot_info_queries_dashboard(self):
        """_log_robot_info reads model, serial, version, mode, safety."""
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.dashboard = MagicMock(spec=DashboardClient)
        b.dashboard.connected = True
        b.dashboard.get_robot_model.return_value = "UR30"
        b.dashboard.get_serial_number.return_value = "123456"
        b.dashboard.get_polyscope_version.return_value = "5.14"
        b.dashboard.get_robot_mode.return_value = "RUNNING"
        b.dashboard.get_safety_mode.return_value = "NORMAL"

        b._log_robot_info()

        b.dashboard.get_robot_model.assert_called_once()
        b.dashboard.get_serial_number.assert_called_once()
        b.dashboard.get_polyscope_version.assert_called_once()

    def test_log_robot_info_no_dashboard(self):
        """_log_robot_info does nothing if dashboard is None."""
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.dashboard = None

        b._log_robot_info()  # should not raise

    def test_log_robot_info_disconnected_dashboard(self):
        """_log_robot_info does nothing if dashboard is disconnected."""
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.dashboard = MagicMock(spec=DashboardClient)
        b.dashboard.connected = False

        b._log_robot_info()
        b.dashboard.get_robot_model.assert_not_called()

    def test_log_robot_info_connection_error(self):
        """_log_robot_info handles ConnectionError gracefully."""
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.dashboard = MagicMock(spec=DashboardClient)
        b.dashboard.connected = True
        b.dashboard.get_robot_model.side_effect = ConnectionError("lost")

        b._log_robot_info()  # should not raise


# ===================================================================
# _dashboard_auto_start_sequence()
# ===================================================================

class TestDashboardAutoStart:

    def _make_bridge_with_dashboard(self):
        b = Bridge(ur_host="127.0.0.1", enable_dashboard=True,
                   dashboard_auto_start=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.dashboard = MagicMock(spec=DashboardClient)
        b.dashboard.connected = True
        return b

    def test_auto_start_requires_remote_control(self):
        """Auto-start aborts if not in remote control mode."""
        b = self._make_bridge_with_dashboard()
        b.dashboard.is_in_remote_control.return_value = False

        b._dashboard_auto_start_sequence()

        b.dashboard.load_program.assert_not_called()
        b.dashboard.play.assert_not_called()

    def test_auto_start_powers_on_if_off(self):
        """Auto-start powers on robot if in POWER_OFF mode."""
        b = self._make_bridge_with_dashboard()
        b.dashboard.is_in_remote_control.return_value = True
        b.dashboard.get_robot_mode.return_value = "POWER_OFF"
        b.dashboard.load_program.return_value = "Loading program"
        b.dashboard.play.return_value = "Starting program"

        with patch("bridge.bridge_daemon.time.sleep"):
            b._dashboard_auto_start_sequence()

        b.dashboard.power_on.assert_called_once()
        b.dashboard.brake_release.assert_called_once()
        b.dashboard.load_program.assert_called_once()
        b.dashboard.play.assert_called_once()

    def test_auto_start_skips_power_on_if_running(self):
        """Auto-start skips power on when robot is already RUNNING."""
        b = self._make_bridge_with_dashboard()
        b.dashboard.is_in_remote_control.return_value = True
        b.dashboard.get_robot_mode.return_value = "RUNNING"
        b.dashboard.load_program.return_value = "Loading program"
        b.dashboard.play.return_value = "Starting program"

        b._dashboard_auto_start_sequence()

        b.dashboard.power_on.assert_not_called()
        b.dashboard.load_program.assert_called_once()
        b.dashboard.play.assert_called_once()

    def test_auto_start_handles_connection_error(self):
        """Auto-start handles ConnectionError gracefully."""
        b = self._make_bridge_with_dashboard()
        b.dashboard.is_in_remote_control.side_effect = ConnectionError("lost")

        b._dashboard_auto_start_sequence()  # should not raise

    def test_auto_start_noop_if_no_dashboard(self):
        """Auto-start does nothing when dashboard is None."""
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.dashboard = None

        b._dashboard_auto_start_sequence()  # should not raise

    def test_auto_start_noop_if_disconnected(self):
        """Auto-start does nothing when dashboard is disconnected."""
        b = self._make_bridge_with_dashboard()
        b.dashboard.connected = False

        b._dashboard_auto_start_sequence()
        b.dashboard.is_in_remote_control.assert_not_called()


# ===================================================================
# _tick() with watchdog trigger
# ===================================================================

class TestWatchdogInTick:

    @staticmethod
    def _make_triggered_watchdog():
        """Create a mock Watchdog that reports as triggered."""
        from bridge.watchdog import Watchdog
        mock_wd = MagicMock(spec=Watchdog)
        mock_wd.is_triggered = True
        return mock_wd

    def test_tick_watchdog_triggered_stops_extrusion(self, bridge, make_cmd):
        """Watchdog trigger in _tick() stops extrusion and sets error state."""
        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=10.0)
        bridge.rtde.read_commands.return_value = cmd
        bridge.watchdog = self._make_triggered_watchdog()

        with patch.object(bridge, "_stop_extrusion") as mock_stop, \
             patch.object(bridge, "_report_status"), \
             patch.object(bridge, "_watchdog_recovery"):
            bridge._tick()

        mock_stop.assert_called_once()

    def test_tick_watchdog_triggered_sets_fault(self, bridge, make_cmd):
        """Watchdog trigger sets fault=True and ERR_COMMS_LOST."""
        cmd = make_cmd()
        bridge.rtde.read_commands.return_value = cmd
        bridge.watchdog = self._make_triggered_watchdog()

        with patch.object(bridge, "_stop_extrusion"), \
             patch.object(bridge, "_report_status"), \
             patch.object(bridge, "_watchdog_recovery"):
            bridge._tick()

        assert bridge.state.fault is True
        assert bridge.state.error_code == config.ERR_COMMS_LOST
        assert bridge.state.status == config.STATUS_ERROR

    def test_tick_watchdog_triggered_annotates_logger(self, make_cmd):
        """Watchdog trigger annotates data logger with 'WATCHDOG'."""
        b = Bridge(ur_host="127.0.0.1", enable_logging=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b.data_logger = MagicMock(spec=DataLogger)
        b.watchdog = self._make_triggered_watchdog()

        cmd = make_cmd()
        b.rtde.read_commands.return_value = cmd

        with patch.object(b, "_stop_extrusion"), \
             patch.object(b, "_report_status"), \
             patch.object(b, "_watchdog_recovery"):
            b._tick()

        b.data_logger.annotate.assert_called_with("WATCHDOG")

    def test_tick_watchdog_triggered_calls_recovery(self, bridge, make_cmd):
        """Watchdog trigger calls _watchdog_recovery."""
        cmd = make_cmd()
        bridge.rtde.read_commands.return_value = cmd
        bridge.watchdog = self._make_triggered_watchdog()

        with patch.object(bridge, "_stop_extrusion"), \
             patch.object(bridge, "_report_status"), \
             patch.object(bridge, "_watchdog_recovery") as mock_recovery:
            bridge._tick()

        mock_recovery.assert_called_once()


# ===================================================================
# _watchdog_recovery()
# ===================================================================

class TestWatchdogRecovery:

    def test_recovery_waits_for_fresh_data(self, bridge, make_cmd):
        """Recovery loop exits when watchdog is no longer triggered."""
        from bridge.watchdog import Watchdog
        bridge._running = True
        mock_wd = MagicMock(spec=Watchdog)
        # First call: triggered=True (still stale), second: False (fresh)
        type(mock_wd).is_triggered = property(
            lambda self: mock_wd._is_triggered_values.pop(0)
        )
        mock_wd._is_triggered_values = [False]  # after feed, clear
        bridge.watchdog = mock_wd

        fresh_cmd = make_cmd()
        bridge.rtde.read_commands.return_value = fresh_cmd

        with patch("bridge.bridge_daemon.time.sleep"):
            bridge._watchdog_recovery()

        assert bridge.state.fault is False
        assert bridge.state.error_code == config.ERR_NONE
        assert bridge.state.status == config.STATUS_IDLE

    def test_recovery_connection_error_reconnects(self, bridge):
        """ConnectionError during recovery triggers _connect_all."""
        bridge._running = True
        bridge.rtde.read_commands.side_effect = ConnectionError("lost")

        with patch.object(bridge, "_connect_all") as mock_connect:
            bridge._watchdog_recovery()

        mock_connect.assert_called_once()

    def test_recovery_stops_when_not_running(self, bridge, make_cmd):
        """Recovery exits when _running is False."""
        bridge._running = False
        bridge.watchdog._triggered = True

        bridge._watchdog_recovery()

        bridge.rtde.read_commands.assert_not_called()


# ===================================================================
# _check_dashboard_state()
# ===================================================================

class TestCheckDashboardState:

    def _make_bridge_with_poller(self):
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.dashboard_poller = MagicMock(spec=DashboardPoller)
        b.data_logger = MagicMock(spec=DataLogger)
        return b

    def test_noop_without_poller(self, bridge):
        """_check_dashboard_state does nothing when no poller."""
        bridge.dashboard_poller = None
        bridge._check_dashboard_state()  # should not raise

    def test_program_stopped_disables_stepper(self):
        """Program STOPPED disables stepper when enabled."""
        b = self._make_bridge_with_poller()
        b.state.stepper_enabled = True
        b.dashboard_poller.get_cached_program_state.return_value = "STOPPED"
        b.dashboard_poller.get_cached_safety_mode.return_value = "NORMAL"

        with patch.object(b, "_stop_extrusion") as mock_stop:
            b._check_dashboard_state()

        mock_stop.assert_called_once()

    def test_program_paused_disables_stepper(self):
        """Program PAUSED disables stepper when enabled."""
        b = self._make_bridge_with_poller()
        b.state.stepper_enabled = True
        b.dashboard_poller.get_cached_program_state.return_value = "PAUSED"
        b.dashboard_poller.get_cached_safety_mode.return_value = "NORMAL"

        with patch.object(b, "_stop_extrusion") as mock_stop:
            b._check_dashboard_state()

        mock_stop.assert_called_once()
        b.data_logger.annotate.assert_called_with("UR_PROG_PAUSED")

    def test_program_stopped_annotates_logger(self):
        """Program STOPPED annotates data logger."""
        b = self._make_bridge_with_poller()
        b.state.stepper_enabled = True
        b.dashboard_poller.get_cached_program_state.return_value = "STOPPED"
        b.dashboard_poller.get_cached_safety_mode.return_value = "NORMAL"

        with patch.object(b, "_stop_extrusion"):
            b._check_dashboard_state()

        b.data_logger.annotate.assert_called_with("UR_PROG_STOPPED")

    def test_safety_mode_sets_fault(self):
        """Non-NORMAL safety mode sets fault and disables stepper."""
        b = self._make_bridge_with_poller()
        b.state.stepper_enabled = True
        b.state.fault = False
        b.dashboard_poller.get_cached_program_state.return_value = "PLAYING"
        b.dashboard_poller.get_cached_safety_mode.return_value = "PROTECTIVE_STOP"

        with patch.object(b, "_stop_extrusion"):
            b._check_dashboard_state()

        assert b.state.fault is True
        b.data_logger.annotate.assert_called_with("SAFETY_PROTECTIVE_STOP")

    def test_safety_mode_normal_no_fault(self):
        """NORMAL safety mode does not set fault."""
        b = self._make_bridge_with_poller()
        b.state.fault = False
        b.dashboard_poller.get_cached_program_state.return_value = "PLAYING"
        b.dashboard_poller.get_cached_safety_mode.return_value = "NORMAL"

        b._check_dashboard_state()

        assert b.state.fault is False

    def test_safety_fault_only_fires_once(self):
        """Safety fault is only set once (not re-logged if already faulted)."""
        b = self._make_bridge_with_poller()
        b.state.fault = True  # already faulted
        b.dashboard_poller.get_cached_program_state.return_value = "PLAYING"
        b.dashboard_poller.get_cached_safety_mode.return_value = "PROTECTIVE_STOP"

        b._check_dashboard_state()

        b.data_logger.annotate.assert_not_called()

    def test_program_running_stepper_disabled_no_stop(self):
        """No stop call when program is STOPPED but stepper already disabled."""
        b = self._make_bridge_with_poller()
        b.state.stepper_enabled = False
        b.dashboard_poller.get_cached_program_state.return_value = "STOPPED"
        b.dashboard_poller.get_cached_safety_mode.return_value = "NORMAL"

        with patch.object(b, "_stop_extrusion") as mock_stop:
            b._check_dashboard_state()

        mock_stop.assert_not_called()


# ===================================================================
# _check_stall_status()
# ===================================================================

class TestCheckStallStatus:

    def _make_bridge_with_status_poller(self):
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.status_poller = MagicMock(spec=KlipperStatusPoller)
        b.data_logger = MagicMock(spec=DataLogger)
        return b

    def test_noop_without_poller(self, bridge):
        """_check_stall_status does nothing when no status_poller."""
        bridge.status_poller = None
        bridge._check_stall_status()  # should not raise

    def test_hardware_stall_sets_fault(self):
        """Hardware stall (core1 DIAG) sets ERR_STALL and fault."""
        b = self._make_bridge_with_status_poller()
        b.status_poller.is_hardware_stall.return_value = True
        b.state.error_code = config.ERR_NONE

        b._check_stall_status()

        assert b.state.error_code == config.ERR_STALL
        assert b.state.fault is True
        b.data_logger.annotate.assert_called_with("STALL_HW")

    def test_hardware_stall_only_fires_once(self):
        """Hardware stall detection doesn't re-log if ERR_STALL already set."""
        b = self._make_bridge_with_status_poller()
        b.status_poller.is_hardware_stall.return_value = True
        b.state.error_code = config.ERR_STALL

        b._check_stall_status()

        b.data_logger.annotate.assert_not_called()

    def test_uart_stall_sets_fault(self):
        """UART-polled stall sets ERR_STALL and fault."""
        b = self._make_bridge_with_status_poller()
        b.status_poller.is_hardware_stall.return_value = False
        b.status_poller.is_stalled.return_value = True
        b.state.error_code = config.ERR_NONE

        b._check_stall_status()

        assert b.state.error_code == config.ERR_STALL
        assert b.state.fault is True
        b.data_logger.annotate.assert_called_with("STALL")

    def test_uart_stall_only_fires_once(self):
        """UART stall detection doesn't re-log if ERR_STALL already set."""
        b = self._make_bridge_with_status_poller()
        b.status_poller.is_hardware_stall.return_value = False
        b.status_poller.is_stalled.return_value = True
        b.state.error_code = config.ERR_STALL

        b._check_stall_status()

        b.data_logger.annotate.assert_not_called()

    def test_hardware_stall_takes_priority(self):
        """Hardware stall returns early before UART check."""
        b = self._make_bridge_with_status_poller()
        b.status_poller.is_hardware_stall.return_value = True
        b.state.error_code = config.ERR_NONE

        b._check_stall_status()

        # UART stall not checked because hardware stall returned early
        b.status_poller.is_stalled.assert_not_called()

    def test_no_stall_no_fault(self):
        """No stall detected: no fault or error changes."""
        b = self._make_bridge_with_status_poller()
        b.status_poller.is_hardware_stall.return_value = False
        b.status_poller.is_stalled.return_value = False
        b.state.error_code = config.ERR_NONE
        b.state.fault = False

        b._check_stall_status()

        assert b.state.error_code == config.ERR_NONE
        assert b.state.fault is False


# ===================================================================
# Bridge-computed extrusion rate (Enhancement 4)
# ===================================================================

class TestBridgeComputedExtrusion:

    def test_bridge_mode_uses_tcp_speed(self, make_cmd):
        """extrusion_source=BRIDGE computes rate from tcp_speed * multiplier."""
        b = Bridge(ur_host="127.0.0.1",
                   extrusion_source=config.EXTRUSION_MODE_BRIDGE,
                   extrusion_multiplier=2.0)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True

        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE,
                       tcp_speed=10.0, extrusion_rate=0.0)
        b._process_commands(cmd)

        # rate = tcp_speed(10) * multiplier(2) = 20.0
        call_args = b.klipper.stepper_move.call_args
        speed = call_args[0][2]
        assert speed == 20.0

    def test_bridge_mode_ignores_extrusion_rate_field(self, make_cmd):
        """Bridge mode ignores the extrusion_rate from UR and uses tcp_speed."""
        b = Bridge(ur_host="127.0.0.1",
                   extrusion_source=config.EXTRUSION_MODE_BRIDGE,
                   extrusion_multiplier=1.0)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)

        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE,
                       tcp_speed=15.0, extrusion_rate=99.0)
        rate = b._resolve_extrusion_rate(cmd)
        assert rate == 15.0  # from tcp_speed, not extrusion_rate

    def test_ur_mode_uses_extrusion_rate_field(self, make_cmd):
        """UR mode uses the extrusion_rate register value."""
        b = Bridge(ur_host="127.0.0.1",
                   extrusion_source=config.EXTRUSION_MODE_UR)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)

        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE,
                       tcp_speed=15.0, extrusion_rate=25.0)
        rate = b._resolve_extrusion_rate(cmd)
        assert rate == 25.0


# ===================================================================
# Profile error handling
# ===================================================================

class TestProfileError:

    def test_apply_profile_error_falls_back_to_raw(self, bridge):
        """Profile apply error falls back to raw rate."""
        bridge.active_profile = MagicMock()
        bridge.active_profile.apply.side_effect = ValueError("bad input")

        result = bridge._apply_profile(10.0)

        assert result == 10.0  # raw rate fallback


# ===================================================================
# _tick() with data logger
# ===================================================================

class TestDataLoggerInTick:

    def test_tick_logs_telemetry(self, make_cmd):
        """_tick() calls data_logger.log_tick() with telemetry dict."""
        b = Bridge(ur_host="127.0.0.1", enable_logging=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b.data_logger = MagicMock(spec=DataLogger)
        b.status_poller = None

        cmd = make_cmd(enable=True, mode=config.MODE_EXTRUDE, extrusion_rate=10.0)
        b.rtde.read_commands.return_value = cmd

        b._tick()

        b.data_logger.log_tick.assert_called_once()
        logged_data = b.data_logger.log_tick.call_args[0][0]
        assert "timestamp" in logged_data
        assert "loop_dt_ms" in logged_data
        assert "tick_number" in logged_data
        assert logged_data["mode"] == config.MODE_EXTRUDE

    def test_tick_logs_tmc_status_when_poller_available(self, make_cmd):
        """_tick() includes TMC status from status_poller in log data."""
        b = Bridge(ur_host="127.0.0.1", enable_logging=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b.data_logger = MagicMock(spec=DataLogger)
        b.status_poller = MagicMock(spec=KlipperStatusPoller)
        b.status_poller.get_tmc_status.return_value = {
            "drv_status": {"sg_result": 42, "stst": False}
        }
        b.status_poller.is_stalled.return_value = False
        b.status_poller.is_hardware_stall.return_value = False
        b.status_poller.is_standstill.return_value = False

        cmd = make_cmd()
        b.rtde.read_commands.return_value = cmd

        b._tick()

        logged_data = b.data_logger.log_tick.call_args[0][0]
        assert logged_data["tmc_sg_result"] == 42
        assert logged_data["tmc_standstill"] is False

    def test_tick_connection_error_annotates_logger(self, make_cmd):
        """ConnectionError in _tick() annotates data_logger with RECONNECT."""
        b = Bridge(ur_host="127.0.0.1", enable_logging=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b.data_logger = MagicMock(spec=DataLogger)
        b.rtde.read_commands.side_effect = ConnectionError("lost")

        with patch.object(b, "_connect_all"):
            b._tick()

        b.data_logger.annotate.assert_called_with("RECONNECT")

    def test_tick_estop_annotates_logger(self, make_cmd):
        """E-stop in _tick() annotates data_logger with ESTOP."""
        b = Bridge(ur_host="127.0.0.1", enable_logging=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b.data_logger = MagicMock(spec=DataLogger)

        cmd = make_cmd(estop=True)
        b.rtde.read_commands.return_value = cmd

        b._tick()

        b.data_logger.annotate.assert_called_with("ESTOP")


# ===================================================================
# _report_status() with status_poller
# ===================================================================

class TestReportStatusWithPoller:

    def _make_bridge_with_poller(self):
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.status_poller = MagicMock(spec=KlipperStatusPoller)
        return b

    def test_standstill_reports_zero_rate(self):
        """Standstill flag: actual_rate reported as 0.0."""
        b = self._make_bridge_with_poller()
        b.state.current_rate = 25.0
        b.status_poller.is_standstill.return_value = True
        b.status_poller.is_stalled.return_value = False
        b.status_poller.get_tmc_status.return_value = {"drv_status": {}}

        b._report_status()

        call_kwargs = b.rtde.write_status.call_args[1]
        assert call_kwargs["actual_rate"] == 0.0

    def test_stalled_reports_zero_rate(self):
        """Stalled flag: actual_rate reported as 0.0."""
        b = self._make_bridge_with_poller()
        b.state.current_rate = 25.0
        b.status_poller.is_standstill.return_value = False
        b.status_poller.is_stalled.return_value = True
        b.status_poller.get_tmc_status.return_value = {"drv_status": {}}

        b._report_status()

        call_kwargs = b.rtde.write_status.call_args[1]
        assert call_kwargs["actual_rate"] == 0.0

    def test_moving_reports_commanded_rate(self):
        """Neither standstill nor stalled: actual_rate = commanded rate."""
        b = self._make_bridge_with_poller()
        b.state.current_rate = 25.0
        b.status_poller.is_standstill.return_value = False
        b.status_poller.is_stalled.return_value = False
        b.status_poller.get_tmc_status.return_value = {"drv_status": {}}

        b._report_status()

        call_kwargs = b.rtde.write_status.call_args[1]
        assert call_kwargs["actual_rate"] == 25.0

    def test_stallguard_load_from_tmc_status(self):
        """StallGuard load value comes from sg_result in TMC status."""
        b = self._make_bridge_with_poller()
        b.status_poller.is_standstill.return_value = False
        b.status_poller.is_stalled.return_value = False
        b.status_poller.get_tmc_status.return_value = {
            "drv_status": {"sg_result": 128}
        }

        b._report_status()

        call_kwargs = b.rtde.write_status.call_args[1]
        assert call_kwargs["stallguard_load"] == 128.0

    def test_no_sg_result_reports_zero_load(self):
        """Missing sg_result: stallguard_load is 0.0."""
        b = self._make_bridge_with_poller()
        b.status_poller.is_standstill.return_value = False
        b.status_poller.is_stalled.return_value = False
        b.status_poller.get_tmc_status.return_value = {"drv_status": {}}

        b._report_status()

        call_kwargs = b.rtde.write_status.call_args[1]
        assert call_kwargs["stallguard_load"] == 0.0


# ===================================================================
# stop() with all subsystems active
# ===================================================================

class TestStopWithSubsystems:

    def test_stop_with_status_poller(self):
        """stop() stops the status poller."""
        b = Bridge(ur_host="127.0.0.1", enable_status_poll=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b.status_poller = MagicMock(spec=KlipperStatusPoller)

        b.stop()

        b.status_poller.stop.assert_called_once()

    def test_stop_with_dashboard_poller(self):
        """stop() stops the dashboard poller."""
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b.dashboard_poller = MagicMock(spec=DashboardPoller)

        b.stop()

        b.dashboard_poller.stop.assert_called_once()

    def test_stop_with_data_logger(self):
        """stop() stops the data logger."""
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b.data_logger = MagicMock(spec=DataLogger)

        b.stop()

        b.data_logger.stop.assert_called_once()

    def test_stop_with_sg_accumulator_logs_summary(self):
        """stop() logs StallGuard accumulator summary."""
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b.sg_accumulator = MagicMock(spec=StallGuardAccumulator)
        b.sg_accumulator.get_summary.return_value = {"count": 0}

        b.stop()

        b.sg_accumulator.get_summary.assert_called_once()

    def test_stop_disconnects_dashboard(self):
        """stop() disconnects the dashboard client."""
        b = Bridge(ur_host="127.0.0.1", enable_dashboard=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b.dashboard = MagicMock(spec=DashboardClient)
        b.dashboard.connected = True

        b.stop()

        b.dashboard.disconnect.assert_called_once()

    def test_stop_dashboard_disconnect_error_suppressed(self):
        """stop() suppresses errors from dashboard disconnect."""
        b = Bridge(ur_host="127.0.0.1", enable_dashboard=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b.dashboard = MagicMock(spec=DashboardClient)
        b.dashboard.connected = True
        b.dashboard.disconnect.side_effect = RuntimeError("failed")

        b.stop()  # should not raise


# ===================================================================
# start() with subsystems
# ===================================================================

class TestStartWithSubsystems:

    def test_start_starts_status_poller(self):
        """start() calls status_poller.start()."""
        b = Bridge(ur_host="127.0.0.1", enable_status_poll=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.status_poller = MagicMock(spec=KlipperStatusPoller)

        def tick_then_stop():
            b._running = False

        with patch.object(b, "_connect_all"), \
             patch.object(b, "_tick", side_effect=tick_then_stop), \
             patch("bridge.bridge_daemon.time.sleep"):
            b.start()

        b.status_poller.start.assert_called_once()

    def test_start_starts_data_logger(self):
        """start() calls data_logger.start() when logging is enabled."""
        b = Bridge(ur_host="127.0.0.1", enable_logging=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.data_logger = MagicMock(spec=DataLogger)

        def tick_then_stop():
            b._running = False

        with patch.object(b, "_connect_all"), \
             patch.object(b, "_tick", side_effect=tick_then_stop), \
             patch("bridge.bridge_daemon.time.sleep"):
            b.start()

        b.data_logger.start.assert_called_once()


# ===================================================================
# main() CLI entry point
# ===================================================================

class TestMainCLI:

    def test_main_default_args(self):
        """main() parses default args and creates a Bridge."""
        with patch("bridge.bridge_daemon.Bridge") as MockBridge, \
             patch("bridge.bridge_daemon.signal.signal"), \
             patch("sys.argv", ["bridge_daemon"]):
            mock_bridge = MagicMock()
            MockBridge.return_value = mock_bridge

            main()

            MockBridge.assert_called_once()
            mock_bridge.start.assert_called_once()

    def test_main_dry_run(self):
        """main() passes dry_run=True when --dry-run is given."""
        with patch("bridge.bridge_daemon.Bridge") as MockBridge, \
             patch("bridge.bridge_daemon.signal.signal"), \
             patch("sys.argv", ["bridge_daemon", "--dry-run"]):
            mock_bridge = MagicMock()
            MockBridge.return_value = mock_bridge

            main()

            call_kwargs = MockBridge.call_args[1]
            assert call_kwargs["dry_run"] is True

    def test_main_host_arg(self):
        """main() passes custom host."""
        with patch("bridge.bridge_daemon.Bridge") as MockBridge, \
             patch("bridge.bridge_daemon.signal.signal"), \
             patch("sys.argv", ["bridge_daemon", "--host", "10.0.0.1"]):
            mock_bridge = MagicMock()
            MockBridge.return_value = mock_bridge

            main()

            call_kwargs = MockBridge.call_args[1]
            assert call_kwargs["ur_host"] == "10.0.0.1"

    def test_main_bridge_extrusion_source(self):
        """main() maps --extrusion-source bridge to EXTRUSION_MODE_BRIDGE."""
        with patch("bridge.bridge_daemon.Bridge") as MockBridge, \
             patch("bridge.bridge_daemon.signal.signal"), \
             patch("sys.argv", ["bridge_daemon", "--extrusion-source", "bridge"]):
            mock_bridge = MagicMock()
            MockBridge.return_value = mock_bridge

            main()

            call_kwargs = MockBridge.call_args[1]
            assert call_kwargs["extrusion_source"] == config.EXTRUSION_MODE_BRIDGE

    def test_main_dashboard_auto_implies_dashboard(self):
        """main() --dashboard-auto implies --dashboard."""
        with patch("bridge.bridge_daemon.Bridge") as MockBridge, \
             patch("bridge.bridge_daemon.signal.signal"), \
             patch("sys.argv", ["bridge_daemon", "--dashboard-auto"]):
            mock_bridge = MagicMock()
            MockBridge.return_value = mock_bridge

            main()

            call_kwargs = MockBridge.call_args[1]
            assert call_kwargs["enable_dashboard"] is True
            assert call_kwargs["dashboard_auto_start"] is True

    def test_main_no_watchdog(self):
        """main() --no-watchdog disables watchdog."""
        with patch("bridge.bridge_daemon.Bridge") as MockBridge, \
             patch("bridge.bridge_daemon.signal.signal"), \
             patch("sys.argv", ["bridge_daemon", "--no-watchdog"]):
            mock_bridge = MagicMock()
            MockBridge.return_value = mock_bridge

            main()

            call_kwargs = MockBridge.call_args[1]
            assert call_kwargs["enable_watchdog"] is False

    def test_main_logging_flags(self):
        """main() --log enables logging."""
        with patch("bridge.bridge_daemon.Bridge") as MockBridge, \
             patch("bridge.bridge_daemon.signal.signal"), \
             patch("sys.argv", ["bridge_daemon", "--log"]):
            mock_bridge = MagicMock()
            MockBridge.return_value = mock_bridge

            main()

            call_kwargs = MockBridge.call_args[1]
            assert call_kwargs["enable_logging"] is True

    def test_main_invalid_multiplier(self):
        """main() rejects --extrusion-multiplier <= 0."""
        with patch("sys.argv", ["bridge_daemon", "--extrusion-multiplier", "0"]):
            with pytest.raises(SystemExit):
                main()

    def test_main_sigterm_handler(self):
        """main() registers SIGTERM handler."""
        import signal as sig
        with patch("bridge.bridge_daemon.Bridge") as MockBridge, \
             patch("bridge.bridge_daemon.signal.signal") as mock_signal, \
             patch("sys.argv", ["bridge_daemon"]):
            mock_bridge = MagicMock()
            MockBridge.return_value = mock_bridge

            main()

            # SIGTERM handler was registered
            signal_calls = [c for c in mock_signal.call_args_list
                            if c[0][0] == sig.SIGTERM]
            assert len(signal_calls) == 1

    def test_main_status_interval(self):
        """main() --status-interval passes status_poll_interval to Bridge."""
        with patch("bridge.bridge_daemon.Bridge") as MockBridge, \
             patch("bridge.bridge_daemon.signal.signal"), \
             patch("sys.argv", ["bridge_daemon", "--status-interval", "0.1"]):
            mock_bridge = MagicMock()
            MockBridge.return_value = mock_bridge

            main()

            call_kwargs = MockBridge.call_args[1]
            assert call_kwargs["status_poll_interval"] == 0.1

    def test_main_default_status_interval(self):
        """main() default --status-interval matches config constant."""
        with patch("bridge.bridge_daemon.Bridge") as MockBridge, \
             patch("bridge.bridge_daemon.signal.signal"), \
             patch("sys.argv", ["bridge_daemon"]):
            mock_bridge = MagicMock()
            MockBridge.return_value = mock_bridge

            main()

            call_kwargs = MockBridge.call_args[1]
            assert call_kwargs["status_poll_interval"] == config.STATUS_POLL_INTERVAL


# ===================================================================
# _connect_all with dashboard auto-start
# ===================================================================

class TestConnectAllDashboardAutoStart:

    def test_connect_all_triggers_auto_start(self):
        """_connect_all calls _dashboard_auto_start_sequence when enabled."""
        b = Bridge(ur_host="127.0.0.1", enable_dashboard=True,
                   dashboard_auto_start=True)
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b._status_klipper = MagicMock(spec=KlipperClient)
        b.dashboard = MagicMock(spec=DashboardClient)
        b.dashboard.connected = True
        b._running = True
        b.klipper.get_info.return_value = {"state_message": "ready"}

        with patch("bridge.bridge_daemon.time.sleep"), \
             patch.object(b, "_log_robot_info"), \
             patch.object(b, "_dashboard_auto_start_sequence") as mock_auto:
            b._connect_all()

        mock_auto.assert_called_once()


# ===================================================================
# _watchdog_recovery sleep path
# ===================================================================

class TestWatchdogRecoverySleep:

    def test_recovery_loop_sleeps_between_reads(self):
        """_watchdog_recovery sleeps LOOP_PERIOD between RTDE reads."""
        from bridge.watchdog import Watchdog
        b = Bridge(ur_host="127.0.0.1")
        b.rtde = MagicMock(spec=RTDEClient)
        b.klipper = MagicMock(spec=KlipperClient)
        b.rtde.connected = True
        b.klipper.connected = True
        b._running = True

        # Replace watchdog with a mock that stays triggered once, then clears
        mock_wd = MagicMock(spec=Watchdog)
        call_count = [0]

        def is_triggered_side_effect():
            call_count[0] += 1
            return call_count[0] < 2  # triggered first, then cleared

        type(mock_wd).is_triggered = property(
            lambda self: is_triggered_side_effect()
        )
        b.watchdog = mock_wd
        b.rtde.read_commands.return_value = {"timestamp": 1.0}

        with patch("bridge.bridge_daemon.time.sleep") as mock_sleep:
            b._watchdog_recovery()

        # Sleep was called at least once (between iterations)
        mock_sleep.assert_called_with(config.LOOP_PERIOD)


# ===================================================================
# __main__.py
# ===================================================================

class TestMainModule:

    def test_main_module_calls_main(self):
        """python -m bridge calls main()."""
        with patch("bridge.bridge_daemon.main") as mock_main:
            import importlib
            import bridge.__main__  # noqa: F811
            importlib.reload(bridge.__main__)
            mock_main.assert_called()
