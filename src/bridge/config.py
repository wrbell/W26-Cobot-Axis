"""
W26 Cobot Axis — Bridge Daemon Configuration

RTDE register mappings, connection defaults, and Klipper settings.
Based on docs/register_allocation.md.
"""

# ---------------------------------------------------------------------------
# Network / connection
# ---------------------------------------------------------------------------
UR30_HOST = "192.168.1.100"          # UR30 controller IP — update for your network
RTDE_PORT = 30004
RTDE_FREQUENCY = 500                 # Hz (e-Series default)
RTDE_CONNECT_TIMEOUT = 5.0           # seconds — caps ur_rtde TCP connect (OS default is 60-120s)

KLIPPY_SOCKET = "/tmp/klippy_uds"    # Klipper Unix domain socket

# ---------------------------------------------------------------------------
# RTDE Output Registers  (UR30 → Pi, written by URScript, read by bridge)
# ---------------------------------------------------------------------------
OUTPUT_REGISTERS = {
    "int": [
        "output_int_register_0",      # extrusion mode: 0=off, 1=extrude, 2=retract
    ],
    "double": [
        "output_double_register_0",   # commanded extrusion rate (mm/s)
        "output_double_register_1",   # robot TCP speed magnitude (mm/s)
        "timestamp",                  # UR30 controller timestamp (seconds since boot)
    ],
    "bool": [
        "output_bit_register_64",     # extrusion enable
        "output_bit_register_65",     # emergency stop
        "output_bit_register_66",     # home stepper command
    ],
}

# Friendly names for indexing into received data
class Out:
    MODE = "output_int_register_0"
    EXTRUSION_RATE = "output_double_register_0"
    TCP_SPEED = "output_double_register_1"
    TIMESTAMP = "timestamp"
    ENABLE = "output_bit_register_64"
    ESTOP = "output_bit_register_65"
    HOME = "output_bit_register_66"

# Mode constants
MODE_OFF = 0
MODE_EXTRUDE = 1
MODE_RETRACT = 2

# ---------------------------------------------------------------------------
# RTDE Input Registers  (Pi → UR30, written by bridge, read by URScript)
# ---------------------------------------------------------------------------
INPUT_REGISTERS = {
    "int": [
        "input_int_register_0",       # stepper status: 0=idle, 1=running, 2=error, 3=homing
        "input_int_register_1",       # error code: 0=none, 1=comms_lost, 2=stall, 3=thermal
    ],
    "double": [
        "input_double_register_0",    # actual extrusion rate (mm/s)
        "input_double_register_1",    # StallGuard load value (0-255, from core1 DIAG)
    ],
    "bool": [
        "input_bit_register_64",      # stepper ready
        "input_bit_register_65",      # stepper fault
    ],
}

class In:
    STATUS = "input_int_register_0"
    ERROR_CODE = "input_int_register_1"
    ACTUAL_RATE = "input_double_register_0"
    STALLGUARD_LOAD = "input_double_register_1"
    READY = "input_bit_register_64"
    FAULT = "input_bit_register_65"

# Status constants
STATUS_IDLE = 0
STATUS_RUNNING = 1
STATUS_ERROR = 2
STATUS_HOMING = 3

# Error codes
ERR_NONE = 0
ERR_COMMS_LOST = 1
ERR_STALL = 2
ERR_THERMAL = 3

# ---------------------------------------------------------------------------
# Klipper / stepper
# ---------------------------------------------------------------------------
STEPPER_NAME = "pump"                # matches [manual_stepper pump] in printer.cfg
EXTRUSION_MULTIPLIER = 1.0           # mm extruded per mm/s TCP speed (tune for pump)
MAX_EXTRUSION_RATE = 50.0            # mm/s — safety clamp
DEFAULT_ACCEL = 200                  # mm/s^2

# ---------------------------------------------------------------------------
# Bridge daemon
# ---------------------------------------------------------------------------
LOOP_HZ = 125                        # bridge main loop rate (Hz)
LOOP_PERIOD = 1.0 / LOOP_HZ
RECONNECT_DELAY = 2.0                # seconds before retrying dropped connections
LOG_LEVEL = "INFO"

# ---------------------------------------------------------------------------
# Watchdog (Enhancement 1 — P1)
# ---------------------------------------------------------------------------
WATCHDOG_TIMEOUT = 0.5               # seconds of no new data before triggering
WATCHDOG_ENABLED = True

# ---------------------------------------------------------------------------
# Klipper status polling (Enhancement 2 — P2)
# ---------------------------------------------------------------------------
STATUS_POLL_INTERVAL = 0.05           # seconds between Klipper status queries (20 Hz)
STATUS_POLL_OBJECTS = {
    "tmc2209 manual_stepper pump": None,   # full drv_status
    "stepper_enable": None,                # enabled steppers
}
STALLGUARD_THRESHOLD = 10            # sg_result below this = stall (UART-polled)
STALLGUARD_MONITOR_POLL_OBJECTS = {
    "stallguard_monitor": None,          # core1 DIAG-based stall detection
}

# ---------------------------------------------------------------------------
# Data logging (Enhancement 3 — P3)
# ---------------------------------------------------------------------------
LOG_ENABLED = False                  # enable/disable data logging
LOG_DIR = "/tmp/w26_logs"            # directory for log files
LOG_FILE_PREFIX = "bridge_log"       # prefix for log filenames
LOG_MAX_SIZE_MB = 50                 # rotate after this size
LOG_MAX_FILES = 5                    # keep this many rotated files
LOG_FLUSH_INTERVAL = 1.0            # seconds between forced flushes
LOG_DECIMATION = 1                   # log every Nth tick (1=all, 5=every 5th)

# ---------------------------------------------------------------------------
# Speed-proportional extrusion mode (Enhancement 4 — P4)
# ---------------------------------------------------------------------------
EXTRUSION_MODE_UR = 0               # UR30 computes rate, bridge uses output_double_register_0
EXTRUSION_MODE_BRIDGE = 1           # Bridge computes rate from TCP speed * multiplier
DEFAULT_EXTRUSION_COMP_MODE = EXTRUSION_MODE_UR

# ---------------------------------------------------------------------------
# Extrusion profiles (Enhancement 5 — P5)
# ---------------------------------------------------------------------------
PROFILE_FILE = "profiles.json"       # path to profile JSON (relative to bridge package)
DEFAULT_PROFILE = "linear"

# ---------------------------------------------------------------------------
# Dashboard Server (Enhancement 6 — P6)
# ---------------------------------------------------------------------------
DASHBOARD_PORT = 29999
DASHBOARD_ENABLED = False            # opt-in (not needed for basic operation)
DASHBOARD_POLL_INTERVAL = 2.0       # seconds between state polls
DASHBOARD_TIMEOUT = 5.0             # seconds for command response
UR_PROGRAM_PATH = "/programs/w26_extrusion.urp"  # program to auto-load
DASHBOARD_AUTO_START = False         # automatically load + play UR program on bridge start

# ---------------------------------------------------------------------------
# StallGuard accumulator (Enhancement 7 — P7)
# ---------------------------------------------------------------------------
SG_ACCUMULATOR_DURATION_S = 300.0       # 5 minutes of history
SG_ACCUMULATOR_SAMPLE_RATE_HZ = 20.0   # matches STATUS_POLL_INTERVAL (1/0.05)
