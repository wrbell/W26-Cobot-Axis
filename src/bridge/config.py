"""
W26 Cobot Axis — Bridge Daemon Configuration

RTDE register mappings, connection defaults, and Klipper settings.
Based on reqs/register_allocation.md.
"""

# ---------------------------------------------------------------------------
# Network / connection
# ---------------------------------------------------------------------------
UR30_HOST = "192.168.1.100"          # UR30 controller IP — update for your network
RTDE_PORT = 30004
RTDE_FREQUENCY = 500                 # Hz (e-Series default)

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
