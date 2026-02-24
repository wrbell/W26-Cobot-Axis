"""
Unit tests for W26 bridge daemon configuration module.

Validates register naming conventions, constant sanity, no duplicates,
and cross-references between register dicts and accessor classes.
"""

import re

from bridge.config import (
    DASHBOARD_PORT,
    ERR_COMMS_LOST,
    ERR_NONE,
    ERR_STALL,
    ERR_THERMAL,
    INPUT_REGISTERS,
    KLIPPY_SOCKET,
    LOG_DIR,
    LOG_FILE_PREFIX,
    LOOP_HZ,
    LOOP_PERIOD,
    MAX_EXTRUSION_RATE,
    MODE_EXTRUDE,
    MODE_OFF,
    MODE_RETRACT,
    OUTPUT_REGISTERS,
    RTDE_PORT,
    SG_ACCUMULATOR_DURATION_S,
    SG_ACCUMULATOR_SAMPLE_RATE_HZ,
    STATUS_ERROR,
    STATUS_HOMING,
    STATUS_IDLE,
    STATUS_POLL_INTERVAL,
    STATUS_RUNNING,
    STEPPER_NAME,
    WATCHDOG_TIMEOUT,
    In,
    Out,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten_registers(reg_dict):
    """Return a flat list of all register names from a typed register dict."""
    flat = []
    for names in reg_dict.values():
        flat.extend(names)
    return flat


_OUTPUT_PATTERN = re.compile(
    r"^(output_int_register_\d+|output_double_register_\d+|output_bit_register_\d+|timestamp)$"
)
_INPUT_PATTERN = re.compile(
    r"^(input_int_register_\d+|input_double_register_\d+|input_bit_register_\d+)$"
)


# ---------------------------------------------------------------------------
# Register name format
# ---------------------------------------------------------------------------

class TestRegisterNameFormat:
    def test_output_register_names_match_pattern(self):
        for name in _flatten_registers(OUTPUT_REGISTERS):
            assert _OUTPUT_PATTERN.match(name), f"bad output register name: {name}"

    def test_input_register_names_match_pattern(self):
        for name in _flatten_registers(INPUT_REGISTERS):
            assert _INPUT_PATTERN.match(name), f"bad input register name: {name}"


# ---------------------------------------------------------------------------
# No duplicate registers
# ---------------------------------------------------------------------------

class TestNoDuplicateRegisters:
    def test_output_registers_unique(self):
        flat = _flatten_registers(OUTPUT_REGISTERS)
        assert len(flat) == len(set(flat)), f"duplicate output registers: {flat}"

    def test_input_registers_unique(self):
        flat = _flatten_registers(INPUT_REGISTERS)
        assert len(flat) == len(set(flat)), f"duplicate input registers: {flat}"


# ---------------------------------------------------------------------------
# Accessor classes match register dicts
# ---------------------------------------------------------------------------

class TestAccessorClassesMatchRegisters:
    def test_out_values_in_output_registers(self):
        output_names = set(_flatten_registers(OUTPUT_REGISTERS))
        for attr in dir(Out):
            if attr.startswith("_"):
                continue
            value = getattr(Out, attr)
            assert value in output_names, (
                f"Out.{attr} = {value!r} not found in OUTPUT_REGISTERS"
            )

    def test_in_values_in_input_registers(self):
        input_names = set(_flatten_registers(INPUT_REGISTERS))
        for attr in dir(In):
            if attr.startswith("_"):
                continue
            value = getattr(In, attr)
            assert value in input_names, (
                f"In.{attr} = {value!r} not found in INPUT_REGISTERS"
            )


# ---------------------------------------------------------------------------
# Sane numeric constants
# ---------------------------------------------------------------------------

class TestNumericConstants:
    def test_loop_hz_positive(self):
        assert LOOP_HZ > 0

    def test_loop_period_positive(self):
        assert LOOP_PERIOD > 0

    def test_loop_period_matches_hz(self):
        assert LOOP_PERIOD == 1.0 / LOOP_HZ

    def test_watchdog_timeout_positive(self):
        assert WATCHDOG_TIMEOUT > 0

    def test_status_poll_interval_positive(self):
        assert STATUS_POLL_INTERVAL > 0

    def test_max_extrusion_rate_positive(self):
        assert MAX_EXTRUSION_RATE > 0

    def test_rtde_port_in_valid_range(self):
        assert 1 <= RTDE_PORT <= 65535

    def test_dashboard_port_in_valid_range(self):
        assert 1 <= DASHBOARD_PORT <= 65535


# ---------------------------------------------------------------------------
# Mode / status / error constants are distinct
# ---------------------------------------------------------------------------

class TestDistinctEnumConstants:
    def test_modes_distinct(self):
        modes = {MODE_OFF, MODE_EXTRUDE, MODE_RETRACT}
        assert len(modes) == 3

    def test_status_constants_distinct(self):
        statuses = {STATUS_IDLE, STATUS_RUNNING, STATUS_ERROR, STATUS_HOMING}
        assert len(statuses) == 4

    def test_error_constants_distinct(self):
        errors = {ERR_NONE, ERR_COMMS_LOST, ERR_STALL, ERR_THERMAL}
        assert len(errors) == 4


# ---------------------------------------------------------------------------
# StallGuard accumulator constants
# ---------------------------------------------------------------------------

class TestSGAccumulatorConstants:
    def test_duration_positive(self):
        assert SG_ACCUMULATOR_DURATION_S > 0

    def test_sample_rate_positive(self):
        assert SG_ACCUMULATOR_SAMPLE_RATE_HZ > 0

    def test_capacity_is_positive_integer(self):
        capacity = int(SG_ACCUMULATOR_DURATION_S * SG_ACCUMULATOR_SAMPLE_RATE_HZ)
        assert capacity > 0
        assert capacity == SG_ACCUMULATOR_DURATION_S * SG_ACCUMULATOR_SAMPLE_RATE_HZ


# ---------------------------------------------------------------------------
# String constants not empty
# ---------------------------------------------------------------------------

class TestStringConstants:
    def test_stepper_name_non_empty(self):
        assert isinstance(STEPPER_NAME, str) and len(STEPPER_NAME) > 0

    def test_klippy_socket_non_empty(self):
        assert isinstance(KLIPPY_SOCKET, str) and len(KLIPPY_SOCKET) > 0

    def test_log_dir_non_empty(self):
        assert isinstance(LOG_DIR, str) and len(LOG_DIR) > 0

    def test_log_file_prefix_non_empty(self):
        assert isinstance(LOG_FILE_PREFIX, str) and len(LOG_FILE_PREFIX) > 0
