"""
Unit tests for bridge.bridge_daemon — Bridge and BridgeState.

Tests command translation, e-stop handling, mode switching, rate clamping,
homing, reconnection logic, status reporting, shutdown, dry-run mode,
and main loop mechanics.

All external I/O (RTDEClient, KlipperClient, time) is mocked.
"""

import time as real_time

import pytest
from unittest.mock import patch

from bridge import config


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
        )

    def test_stop_disconnects_both_clients(self, bridge):
        """stop() disconnects both RTDE and Klipper."""
        bridge.stop()
        bridge.rtde.disconnect.assert_called_once()
        bridge.klipper.disconnect.assert_called_once()

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
