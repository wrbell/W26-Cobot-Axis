# Bridge Daemon Enhancement Designs

**Project:** W26 Cobot Axis
**Author:** Willem (Software/EE)
**Date:** 2026-02-12
**Status:** Design (pre-implementation)
**Scope:** Six enhancements to `src/bridge/` for Phase 3-4

---

## Table of Contents

1. [Klipper Status Subscription](#1-klipper-status-subscription)
2. [Speed-Proportional Extrusion Mode](#2-speed-proportional-extrusion-mode)
3. [Data Logging](#3-data-logging)
4. [Watchdog Timer](#4-watchdog-timer)
5. [Configurable Extrusion Profiles](#5-configurable-extrusion-profiles)
6. [Dashboard Server Client](#6-dashboard-server-client)
7. [Implementation Priority and Dependencies](#7-implementation-priority-and-dependencies)

---

## 1. Klipper Status Subscription

### Purpose

The bridge currently reports **commanded rate** as the "actual rate" to the UR30 (see `bridge_daemon.py` line 298: `actual_rate=self.state.current_rate` with the comment `# TODO: read from Klipper`). This means the UR30 has no visibility into what the stepper is actually doing. If Klipper rejects a move, decelerates due to acceleration limits, or encounters an error, the UR30 would still see the old commanded rate. Real actual-rate feedback is needed for closed-loop quality control and for Phase 4 test/reporting (commanded vs actual comparison).

### Research: Available Klipper Status Objects

Klipper exposes status objects via the `objects/query` and `objects/subscribe` API methods on the Unix socket. The relevant objects for this project are:

**`manual_stepper pump`** -- The `[manual_stepper]` module in Klipper (source: `klippy/extras/manual_stepper.py`) does **not** expose a `get_status` method in mainline Klipper. This means there is no subscribable velocity field on `manual_stepper pump`. The `MANUAL_STEPPER` G-code command tracks `commanded_pos` internally but does not publish it as a status object.

**`motion_report`** -- Available automatically when any stepper config section is defined. Exposes:
- `live_position`: interpolated toolhead position at current time (list of floats)
- `live_velocity`: requested toolhead velocity in mm/s at current time (float)
- `live_extruder_velocity`: requested extruder velocity in mm/s at current time (float)

However, `live_extruder_velocity` tracks the **extruder** (from `[extruder]` config), not a `[manual_stepper]`. With `kinematics: none` and no `[extruder]` section, `live_extruder_velocity` will be 0.0. Similarly, `live_velocity` tracks the toolhead, which with `kinematics: none` has no axes. These fields are not useful for `[manual_stepper]`.

**`tmc2209 manual_stepper pump`** -- Exposes TMC2209 driver status:
- `drv_status`: driver status register flags (e.g., `ola`, `olb`, `s2ga`, `s2gb`, `ot`, `otpw`, `t120`, `t143`, `t150`, `t157`, `cs_actual`, `stealth`, `stst`, `sg_result`)
- `mcu_phase_offset`, `phase_offset_position`
- `run_current`, `hold_current`

The `sg_result` (StallGuard) field in `drv_status` provides a torque proxy. The `stst` flag indicates standstill. These are useful for stall detection and diagnostic reporting.

**`stepper_enable`** -- Exposes `steppers` dict showing which steppers are enabled.

### Design Decision: Polling vs Subscription

Given that `[manual_stepper]` does not expose velocity in Klipper's status system, there are two strategies:

**Strategy A -- Periodic position polling (recommended):** Query `manual_stepper pump` position by sending `MANUAL_STEPPER STEPPER=pump` (with no MOVE/SET_POSITION/ENABLE param, this queries and returns current position via G-code response). Differentiate position over time to compute velocity:

```
velocity = (pos_current - pos_previous) / dt
```

However, this requires parsing G-code text responses, which is fragile.

**Strategy B -- TMC2209 status + commanded rate (recommended for MVP):** Accept that true measured velocity is not directly available from Klipper for `[manual_stepper]`. Instead:
1. Report **commanded rate** (current behavior) as the primary rate signal.
2. Supplement with TMC2209 `stst` (standstill) and `sg_result` (StallGuard) to detect when the stepper has **stalled** or **stopped**, in which case report actual rate as 0.0.
3. Use `stepper_enable` to confirm the stepper is actually enabled.

**Strategy C -- Custom klippy extra (future):** Write a small klippy extra Python module (`klippy/extras/pump_status.py`) that wraps `manual_stepper` and exposes a proper `get_status` returning `{'position': ..., 'velocity': ...}`. This provides clean subscribable data but requires modifying the Klipper installation.

### Interface

**New config values in `config.py`:**

```python
# Status polling
STATUS_POLL_INTERVAL = 0.25       # seconds between Klipper status queries
STATUS_POLL_OBJECTS = {
    "tmc2209 manual_stepper pump": None,  # full drv_status
    "stepper_enable": None,               # enabled steppers
}
```

**No new RTDE registers.** The existing `input_double_register_0` (actual extrusion rate) is already allocated. The existing `input_int_register_1` (error code) will carry `ERR_STALL` when detected.

**New CLI arg:**
- `--no-status-poll` -- disable Klipper status polling (for environments where TMC2209 UART is unavailable)

### Architecture

**New module: `src/bridge/klipper_status.py`**

```
class KlipperStatusPoller:
    """Periodically queries Klipper status objects and caches results."""

    def __init__(self, klipper_client: KlipperClient, poll_interval: float)
    def start() -> None          # begin polling in background thread
    def stop() -> None           # stop polling
    def get_tmc_status() -> dict # latest TMC2209 drv_status
    def is_stepper_enabled(name: str) -> bool
    def is_stalled() -> bool     # True if sg_result below threshold
    def is_standstill() -> bool  # True if stst flag set
```

**Integration into `Bridge` class (`bridge_daemon.py`):**

- `Bridge.__init__`: Create `KlipperStatusPoller` instance.
- `Bridge._connect_all`: Call `status_poller.start()` after Klipper connection.
- `Bridge._report_status`: Replace `actual_rate=self.state.current_rate` with logic:
  ```python
  if self.status_poller.is_standstill() or self.status_poller.is_stalled():
      actual_rate = 0.0
  else:
      actual_rate = self.state.current_rate  # commanded rate as best estimate
  ```
- `Bridge._tick`: After `_process_commands`, check `is_stalled()`. If stalled, set `self.state.error_code = config.ERR_STALL` and `self.state.fault = True`.
- `Bridge.stop`: Call `status_poller.stop()`.

### Data Flow

```
KlipperStatusPoller (background thread, every 250ms)
    |
    |  objects/query {"tmc2209 manual_stepper pump": null, "stepper_enable": null}
    v
Klipper (klippy) --> JSON response with drv_status
    |
    v
Cached in KlipperStatusPoller._last_tmc_status
    |
    v (read by main loop)
Bridge._report_status()
    |
    v
RTDEClient.write_status(actual_rate=..., fault=is_stalled)
    |
    v
UR30 reads input_double_register_0 and input_bit_register_65
```

### Error Handling

| Condition | Handling |
|-----------|----------|
| Klipper query times out | Log warning, continue with stale data, set a `stale_count` counter |
| Klipper returns error | Log error, mark data as unavailable, fall back to commanded rate |
| TMC2209 UART not configured | `objects/query` returns error for `tmc2209 manual_stepper pump`, poller disables TMC queries and logs a warning |
| Polling thread crashes | Catch all exceptions in thread, log, attempt restart after delay |
| StallGuard threshold ambiguity | Configurable threshold in `config.py` (`STALLGUARD_THRESHOLD = 10`), default conservative |

### Dependencies

- No new Python libraries. Uses existing `KlipperClient.query_status()`.
- Klipper must have `[tmc2209 manual_stepper pump]` configured (already in `printer.cfg`).
- Python `threading` module (already in stdlib, already imported in `klipper_client.py`).

---

## 2. Speed-Proportional Extrusion Mode

### Purpose

Currently, the UR30 computes the extrusion rate in URScript (`extrusion_rate = tcp_speed * EXTRUSION_MULTIPLIER`) and writes it to `output_double_register_0`. The bridge reads this rate and passes it to Klipper. This works but has drawbacks:

1. **URScript computation overhead:** The 500 Hz control loop on the UR30 must compute the extrusion rate every cycle. URScript is interpreted and relatively slow.
2. **Tuning friction:** Changing the extrusion multiplier requires modifying and re-deploying the URScript program.
3. **No bridge-side profile support:** Non-linear rate mappings (feature 5) cannot be applied if the UR30 computes the rate.

The alternative: the UR30 sends only its raw TCP speed via `output_double_register_1`, and the bridge computes the extrusion rate using a configurable multiplier (and, in the future, a non-linear profile from feature 5).

Both modes should be supported, selectable at runtime.

### Interface

**New config values in `config.py`:**

```python
# Extrusion computation mode
EXTRUSION_MODE_UR = 0        # UR30 computes rate, bridge uses output_double_register_0
EXTRUSION_MODE_BRIDGE = 1    # Bridge computes rate from TCP speed * multiplier
DEFAULT_EXTRUSION_COMP_MODE = EXTRUSION_MODE_UR
```

**New RTDE output register (optional, for runtime switching):**

Use a bit from the existing reserved range: `output_bit_register_67` -- "use bridge-computed extrusion rate." When TRUE, the bridge ignores `output_double_register_0` and instead computes rate from `output_double_register_1` (TCP speed) times `EXTRUSION_MULTIPLIER`. When FALSE (default), the bridge uses the UR30-supplied rate from `output_double_register_0`.

Alternatively, this can be a CLI argument (`--bridge-extrusion`) or config value without using a register, keeping the register space unchanged. For MVP, the CLI approach is simpler.

**New CLI args:**

```
--extrusion-source {ur,bridge}   Select extrusion rate source (default: ur)
--extrusion-multiplier FLOAT     mm extruded per mm/s TCP speed (default: 1.0)
```

**Updated register allocation (if register-based switching is implemented):**

| Register | Type | Purpose |
|----------|------|---------|
| `output_bit_register_67` | BOOL | Extrusion computation mode: FALSE=UR-computed, TRUE=bridge-computed |

Add to `config.py`:

```python
class Out:
    ...
    BRIDGE_EXTRUSION_MODE = "output_bit_register_67"
```

### Architecture

**Modifications to `Bridge._process_commands` in `bridge_daemon.py`:**

The existing method reads `cmd["extrusion_rate"]` directly. Add a computation step:

```python
def _resolve_extrusion_rate(self, cmd: dict) -> float:
    """Determine extrusion rate based on computation mode."""
    if self.extrusion_source == config.EXTRUSION_MODE_BRIDGE:
        tcp_speed = cmd["tcp_speed"]  # mm/s from output_double_register_1
        raw_rate = tcp_speed * self.extrusion_multiplier
    else:
        raw_rate = cmd["extrusion_rate"]  # mm/s from output_double_register_0

    # Apply profile mapping (feature 5 hook -- identity for now)
    mapped_rate = self._apply_profile(raw_rate)

    # Clamp to safety limit
    return max(0.0, min(mapped_rate, config.MAX_EXTRUSION_RATE))
```

Replace the existing rate clamping in `_process_commands` with a call to `_resolve_extrusion_rate`.

**New attributes in `Bridge.__init__`:**

```python
self.extrusion_source = config.DEFAULT_EXTRUSION_COMP_MODE
self.extrusion_multiplier = config.EXTRUSION_MULTIPLIER
```

These are set from CLI args in `main()`.

### Data Flow

**UR-computed mode (existing, default):**
```
UR30 URScript:
  extrusion_rate = tcp_speed * multiplier
  write_output_float_register(0, extrusion_rate)
      |
      v
Bridge reads output_double_register_0
      |
      v
Clamp + send to Klipper
```

**Bridge-computed mode (new):**
```
UR30 URScript:
  tcp_speed = norm(get_actual_tcp_speed())
  write_output_float_register(1, tcp_speed)
      |
      v
Bridge reads output_double_register_1
      |
      v
rate = tcp_speed * extrusion_multiplier
      |
      v (optional: apply profile from feature 5)
Clamp + send to Klipper
```

### Error Handling

| Condition | Handling |
|-----------|----------|
| TCP speed register reads 0.0 in bridge mode | Normal -- stepper stops (deadband applies) |
| TCP speed register is stale (UR30 not writing) | Handled by watchdog (feature 4) |
| Extrusion multiplier is 0.0 or negative | Validate at startup, reject with error |
| Mode switch during active extrusion | If using register-based switching, the bridge checks the mode bit each tick. A mode change mid-extrusion is safe because the rate is recomputed every tick (8ms at 125 Hz). No special transition logic needed. |

### Dependencies

- No new libraries.
- If register-based switching: update `OUTPUT_REGISTERS` and `Out` class in `config.py`, update RTDE recipe setup, update URScript to write the new register.
- If CLI-based switching: no RTDE or URScript changes.

---

## 3. Data Logging

### Purpose

Phase 4 requires quantitative test data: commanded vs actual extrusion rates, latency measurements, fault events. The bridge daemon is the ideal point to capture this data since it sees both the RTDE commands and the Klipper responses. A structured CSV log enables post-hoc analysis in Excel, MATLAB, or Python (pandas/matplotlib) for the final report.

### Interface

**New config values in `config.py`:**

```python
# Data logging
LOG_ENABLED = False                   # enable/disable data logging
LOG_DIR = "/tmp/w26_logs"             # directory for log files
LOG_FILE_PREFIX = "bridge_log"        # prefix for log filenames
LOG_MAX_SIZE_MB = 50                  # rotate after this size
LOG_MAX_FILES = 5                     # keep this many rotated files
LOG_FLUSH_INTERVAL = 1.0             # seconds between forced flushes
LOG_DECIMATION = 1                    # log every Nth tick (1=all, 5=every 5th)
```

**New CLI args:**

```
--log              Enable data logging to CSV
--log-dir PATH     Log output directory (default: /tmp/w26_logs)
--log-decimate N   Log every Nth tick (default: 1, i.e., all ticks)
```

### Log Format

**Filename pattern:** `bridge_log_YYYYMMDD_HHMMSS.csv`

**CSV columns:**

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `timestamp` | float | `time.monotonic()` | Monotonic clock (seconds since boot) |
| `wall_clock` | str | `time.strftime` | Human-readable wall clock (ISO 8601) |
| `tick_number` | int | counter | Sequential tick counter |
| `loop_dt_ms` | float | computed | Actual loop iteration time in ms |
| `mode` | int | RTDE output | Extrusion mode (0/1/2) |
| `enable` | bool | RTDE output | Extrusion enable flag |
| `commanded_rate` | float | RTDE or computed | Extrusion rate sent to Klipper (mm/s) |
| `tcp_speed` | float | RTDE output | Robot TCP speed (mm/s) |
| `actual_rate` | float | Klipper status or commanded | Rate reported back to UR30 (mm/s) |
| `status` | int | bridge state | Bridge status code |
| `error_code` | int | bridge state | Error code |
| `stepper_enabled` | bool | bridge state | Stepper enable state |
| `tmc_sg_result` | int | Klipper TMC status | StallGuard result (if available, else -1) |
| `tmc_standstill` | bool | Klipper TMC status | TMC standstill flag |
| `rtde_read_us` | float | measured | Time to read RTDE registers (microseconds) |
| `klipper_cmd_us` | float | measured | Time to send Klipper command (microseconds) |
| `notes` | str | events | Event annotations (e.g., "ESTOP", "RECONNECT", "MODE_CHANGE") |

**Example row:**
```csv
12345.678,2026-03-15T14:30:01.234,50000,8.1,1,True,25.3,100.5,25.3,1,0,True,45,False,120,450,
```

### Architecture

**New module: `src/bridge/data_logger.py`**

```
class DataLogger:
    """CSV data logger with file rotation and buffered writes."""

    def __init__(self, log_dir: str, prefix: str, max_size_mb: int, max_files: int)
    def start() -> None              # create log file, write header
    def stop() -> None               # flush and close
    def log_tick(data: dict) -> None  # write one row (called from main loop)
    def annotate(note: str) -> None   # add a note to the next row
    def _rotate() -> None             # rotate files when size limit reached
    def _flush() -> None              # periodic flush to disk
```

**Integration into `Bridge` class:**

- `Bridge.__init__`: Create `DataLogger` instance if `--log` is specified.
- `Bridge.start`: Call `data_logger.start()`.
- `Bridge._tick`: After processing, call `data_logger.log_tick(...)` with all measured values. Wrap RTDE reads and Klipper commands with `time.perf_counter()` to measure latencies.
- `Bridge.stop`: Call `data_logger.stop()`.
- On significant events (ESTOP, reconnect, mode change): call `data_logger.annotate("EVENT_NAME")`.

**Tick measurement structure:**

```python
def _tick(self) -> None:
    t0 = time.perf_counter()
    cmd = self.rtde.read_commands()
    t1 = time.perf_counter()

    self._process_commands(cmd)
    t2 = time.perf_counter()

    self._report_status()
    t3 = time.perf_counter()

    if self.data_logger:
        self.data_logger.log_tick({
            "timestamp": time.monotonic(),
            "wall_clock": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tick_number": self._tick_count,
            "loop_dt_ms": (t3 - t0) * 1000,
            "mode": cmd["mode"],
            "enable": cmd["enable"],
            "commanded_rate": self.state.current_rate,
            "tcp_speed": cmd["tcp_speed"],
            "actual_rate": self.state.actual_rate,
            "status": self.state.status,
            "error_code": self.state.error_code,
            "stepper_enabled": self.state.stepper_enabled,
            "tmc_sg_result": ...,  # from status poller
            "tmc_standstill": ...,
            "rtde_read_us": (t1 - t0) * 1e6,
            "klipper_cmd_us": (t2 - t1) * 1e6,
        })
```

### File Rotation

Use Python `os.path.getsize()` to check file size before each write. When the file exceeds `LOG_MAX_SIZE_MB`, rename the current file to `bridge_log_YYYYMMDD_HHMMSS.1.csv` (shifting existing rotated files up), open a new file with a fresh header. Delete files beyond `LOG_MAX_FILES`.

This is intentionally simpler than Python's `logging.handlers.RotatingFileHandler` because the logger writes structured CSV, not freeform text.

### Performance Considerations

At 125 Hz with all columns, each row is approximately 200 bytes. That is 25 KB/s, or 90 MB/hour. At `LOG_MAX_SIZE_MB = 50` with `LOG_MAX_FILES = 5`, maximum disk usage is 250 MB. The `LOG_DECIMATION` parameter allows reducing this -- at decimation=5 (25 Hz effective), disk usage drops to 18 MB/hour.

Buffered I/O with periodic flush (`LOG_FLUSH_INTERVAL = 1.0s`) avoids blocking the main loop on disk writes. The `csv.writer` module handles quoting and escaping.

### Error Handling

| Condition | Handling |
|-----------|----------|
| Log directory does not exist | Create it with `os.makedirs(log_dir, exist_ok=True)` |
| Disk full | Catch `OSError`, log warning, disable data logging, continue bridge operation |
| Write fails | Catch exception, increment error counter, skip row. After 10 consecutive failures, disable logger. |
| File rotation fails | Log error, continue writing to current file |

### Dependencies

- `csv` module (stdlib).
- `os` and `os.path` (stdlib).
- No external libraries.

---

## 4. Watchdog Timer

### Purpose

If the UR30 program pauses, stops, or the RTDE connection silently degrades (data stops updating but the TCP connection stays alive), the bridge must detect this and safely disable the stepper. Without a watchdog, the stepper could continue running at the last commanded rate indefinitely.

The RTDE protocol does not signal program pause/stop via the data registers. The `runtime_state` field in RTDE output does indicate program state, but the current bridge does not subscribe to it. A simpler approach: detect when register values stop changing.

### Interface

**New config values in `config.py`:**

```python
# Watchdog
WATCHDOG_TIMEOUT = 0.5               # seconds of no new data before triggering
WATCHDOG_STALE_FIELD = "tcp_speed"    # field to monitor for staleness
WATCHDOG_ENABLED = True
```

**No new RTDE registers.** The watchdog monitors existing registers.

**No new CLI args** (controlled via config). Optionally:
```
--no-watchdog    Disable the watchdog timer
```

### Staleness Detection Strategy

Two complementary detection methods:

**Method 1 -- Timestamp-based:** Track `time.monotonic()` of the last `_tick` that received a **changed** value in any monitored register. If `current_time - last_change_time > WATCHDOG_TIMEOUT`, trigger.

**Method 2 -- Value-based:** Compare current register values to previous. If `tcp_speed` and `extrusion_rate` are **both** unchanged for `WATCHDOG_TIMEOUT` seconds while `enable` is TRUE and `mode` is not OFF, this is suspicious. A legitimately constant speed during a straight-line move is normal, so this method alone is insufficient. Combine with Method 1: if RTDE `read_commands()` returns the **exact same data object** (all fields identical) for `WATCHDOG_TIMEOUT` seconds, treat as stale.

**Recommended approach: Method 1 + RTDE timestamp.** The UR30 RTDE protocol includes a `timestamp` field (time since controller boot). If this field stops incrementing, the data is definitively stale. Add `timestamp` to the output recipe:

```python
# In config.py OUTPUT_REGISTERS:
"double": [
    "output_double_register_0",   # commanded extrusion rate
    "output_double_register_1",   # TCP speed
    "timestamp",                  # UR30 controller timestamp (seconds since boot)
]
```

If `timestamp` is unchanged between two consecutive reads, the data is stale (the RTDE stream has frozen).

### Architecture

**New class in `src/bridge/bridge_daemon.py` (or separate `src/bridge/watchdog.py`):**

```
class Watchdog:
    """Detects stale RTDE data and triggers safe shutdown."""

    def __init__(self, timeout: float)
    def feed(self, cmd: dict) -> None     # call each tick with new command data
    def is_triggered(self) -> bool         # True if data is stale
    def reset(self) -> None                # reset after recovery
```

Internal state:
- `_last_timestamp`: last seen UR30 `timestamp` value
- `_last_feed_time`: `time.monotonic()` of last changed data
- `_triggered`: bool flag

**Integration into `Bridge._tick`:**

```python
def _tick(self) -> None:
    cmd = self.rtde.read_commands()

    # Feed the watchdog
    self.watchdog.feed(cmd)
    if self.watchdog.is_triggered:
        log.warning("Watchdog triggered — RTDE data stale for %.1fs", config.WATCHDOG_TIMEOUT)
        self._stop_extrusion()
        self.state.status = config.STATUS_ERROR
        self.state.error_code = config.ERR_COMMS_LOST
        self.state.fault = True
        self._report_status()
        # Enter recovery: wait for fresh data
        self._watchdog_recovery()
        return

    self._process_commands(cmd)
    self._report_status()
```

**Recovery path (`_watchdog_recovery`):**

1. Disable stepper (safe state).
2. Continue reading RTDE in a polling loop.
3. When `timestamp` changes (fresh data arrives), reset watchdog.
4. Clear fault state, resume normal `_tick` loop.
5. The stepper does NOT auto-re-enable -- the UR30 must re-assert `enable=True` to restart extrusion. This prevents unexpected motion on recovery.

### Data Flow

```
_tick() called at 125 Hz
    |
    v
rtde.read_commands() --> cmd dict with timestamp
    |
    v
watchdog.feed(cmd)
    |
    +--> Compare cmd["timestamp"] to _last_timestamp
    |    If changed: update _last_feed_time, _last_timestamp
    |    If unchanged: check if (now - _last_feed_time) > WATCHDOG_TIMEOUT
    |
    +--> If stale: set _triggered = True
    |
    v
Bridge checks watchdog.is_triggered
    |
    +--> If triggered: stop extrusion, report error, enter recovery
    +--> If not triggered: proceed with _process_commands
```

### Edge Cases

| Condition | Handling |
|-----------|----------|
| UR30 program is running but robot is stationary (tcp_speed=0, rate=0) | Not triggered: `timestamp` continues to increment even when robot is idle |
| RTDE TCP connection drops | Already handled by existing `ConnectionError` catch in `_tick`. Watchdog is a supplementary check for silent failures. |
| UR30 in protective stop | `timestamp` may still update. Bridge should also check `robot_mode` or `safety_mode` RTDE fields if available (stretch goal). |
| Watchdog triggers during dry-run | Still triggers (dry-run affects Klipper commands, not RTDE reads). In stub mode, `_stub_commands()` returns the same data every tick. Add an exception: disable watchdog in stub mode. |
| False positive during slow update | `WATCHDOG_TIMEOUT = 0.5s` means 250 identical RTDE packets at 500 Hz before triggering. A legitimate scenario where all registers are truly identical for 0.5s is unlikely during active extrusion. |

### Dependencies

- Add `"timestamp"` to `OUTPUT_REGISTERS["double"]` in `config.py`.
- Update `RTDEClient.read_commands()` to include `timestamp` in returned dict.
- Update `RTDEClient._stub_commands()` to return an incrementing timestamp (use `time.monotonic()`).
- No external libraries.

---

## 5. Configurable Extrusion Profiles

### Purpose

The current extrusion rate mapping is linear: `rate = tcp_speed * EXTRUSION_MULTIPLIER`. Real pump systems often have non-linear flow characteristics:

- **Progressive cavity pumps:** Flow rate may scale with a polynomial of RPM.
- **Syringe pumps:** Plunger friction changes with fill level.
- **Peristaltic pumps:** Flow pulsation requires compensation curves.
- **Material-dependent:** Metal paste viscosity varies with temperature and shear rate.

Configurable profiles allow tuning the rate mapping without modifying code, and support switching between profiles for different materials or pump types.

### Profile Format

Profiles are defined in a JSON file. Each profile has a name and a mapping function specification.

**Profile file: `src/bridge/profiles.json`**

```json
{
  "profiles": {
    "linear": {
      "type": "linear",
      "multiplier": 1.0,
      "offset": 0.0,
      "description": "Simple linear: rate = speed * multiplier + offset"
    },
    "polynomial": {
      "type": "polynomial",
      "coefficients": [0.0, 0.8, 0.005],
      "description": "Quadratic: rate = 0.005*speed^2 + 0.8*speed + 0.0"
    },
    "lookup_table": {
      "type": "lookup",
      "points": [
        [0.0, 0.0],
        [10.0, 8.5],
        [20.0, 18.0],
        [30.0, 26.5],
        [40.0, 34.0],
        [50.0, 40.0]
      ],
      "interpolation": "linear",
      "description": "Calibrated lookup table with linear interpolation"
    },
    "piecewise_linear": {
      "type": "piecewise",
      "breakpoints": [
        {"speed": 0.0, "rate": 0.0},
        {"speed": 5.0, "rate": 3.0},
        {"speed": 20.0, "rate": 18.0},
        {"speed": 50.0, "rate": 42.0}
      ],
      "description": "Piecewise linear with breakpoints"
    }
  },
  "active_profile": "linear"
}
```

### Profile Types

**Linear** (`type: "linear"`):
```
rate = speed * multiplier + offset
```
Parameters: `multiplier` (float), `offset` (float, default 0.0).

**Polynomial** (`type: "polynomial"`):
```
rate = coefficients[0] + coefficients[1]*speed + coefficients[2]*speed^2 + ...
```
Parameters: `coefficients` (list of floats, index = power).

**Lookup table** (`type: "lookup"`):
```
rate = interpolate(speed, points)
```
Parameters: `points` (list of `[speed, rate]` pairs, sorted by speed), `interpolation` ("linear" or "nearest").

**Piecewise linear** (`type: "piecewise"`):
Equivalent to lookup table but with named breakpoints. Syntactic convenience.

### Interface

**New config values in `config.py`:**

```python
# Extrusion profiles
PROFILE_FILE = "profiles.json"        # path to profile JSON (relative to bridge package)
DEFAULT_PROFILE = "linear"
```

**New CLI args:**

```
--profile NAME         Select active extrusion profile (default: from profiles.json)
--profile-file PATH    Path to profiles JSON file
```

### Architecture

**New module: `src/bridge/extrusion_profile.py`**

```
class ExtrusionProfile:
    """Base class for extrusion rate mapping functions."""
    def apply(self, speed: float) -> float: ...
    def validate(self) -> None: ...

class LinearProfile(ExtrusionProfile):
    def __init__(self, multiplier: float, offset: float = 0.0)

class PolynomialProfile(ExtrusionProfile):
    def __init__(self, coefficients: list[float])

class LookupProfile(ExtrusionProfile):
    def __init__(self, points: list[tuple[float, float]], interpolation: str = "linear")

def load_profiles(path: str) -> dict[str, ExtrusionProfile]:
    """Load all profiles from JSON file, return dict of name -> profile."""

def get_profile(profiles: dict, name: str) -> ExtrusionProfile:
    """Get a specific profile by name, raise if not found."""
```

**Integration into `Bridge`:**

- `Bridge.__init__`: Load profiles from file. Select active profile from CLI arg or JSON `active_profile`.
- `Bridge._apply_profile(raw_rate: float) -> float`: Delegates to `self.active_profile.apply(raw_rate)`. This is the hook called from `_resolve_extrusion_rate` (feature 2).
- The profile is applied **after** the rate source selection (UR-computed or bridge-computed) and **before** the safety clamp.

**Rate computation pipeline (with features 2 and 5):**

```
Input speed (from UR30 or TCP speed)
    |
    v
[Feature 2: source selection] --> raw_rate
    |
    v
[Feature 5: profile mapping] --> mapped_rate = profile.apply(raw_rate)
    |
    v
[Safety clamp] --> final_rate = clamp(mapped_rate, 0, MAX_EXTRUSION_RATE)
    |
    v
Klipper MANUAL_STEPPER command
```

### Lookup Table Interpolation

For `LookupProfile`, linear interpolation between points:

```python
def apply(self, speed: float) -> float:
    if speed <= self.points[0][0]:
        return self.points[0][1]
    if speed >= self.points[-1][0]:
        return self.points[-1][1]
    # Find bracketing points
    for i in range(len(self.points) - 1):
        x0, y0 = self.points[i]
        x1, y1 = self.points[i + 1]
        if x0 <= speed <= x1:
            t = (speed - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
```

For speeds outside the table range, clamp to the nearest endpoint value (no extrapolation).

### Error Handling

| Condition | Handling |
|-----------|----------|
| Profile file not found | Log warning, fall back to `LinearProfile(multiplier=EXTRUSION_MULTIPLIER)` |
| Profile file invalid JSON | Log error with parse details, fall back to linear |
| Requested profile name not in file | Log error, fall back to linear |
| Polynomial produces negative rate | `apply()` returns `max(0.0, result)` |
| Lookup table not sorted | `validate()` checks sort order at load time, raises `ValueError` |
| Lookup table has duplicate speeds | `validate()` rejects, logs error |
| Profile produces rate above MAX_EXTRUSION_RATE | Handled by downstream safety clamp (not profile's responsibility) |

### Dependencies

- `json` module (stdlib).
- `bisect` module (stdlib, optional optimization for lookup table search).
- No external libraries. Intentionally avoids `numpy`/`scipy` to keep the deployment lightweight.

---

## 6. Dashboard Server Client

### Purpose

The UR30 Dashboard Server (port 29999) provides high-level robot lifecycle management: power on/off, brake release, program load/play/stop, mode queries, safety status. Integrating a Dashboard Server client into the bridge daemon enables:

1. **Startup automation:** The bridge can power on the robot, release brakes, and load the extrusion URScript program automatically.
2. **State monitoring:** Query `robotmode`, `programState`, and `safetymode` to detect when the robot enters protective stop, powers off, or the program ends.
3. **Graceful shutdown:** Stop the UR30 program when the bridge shuts down.
4. **Diagnostic information:** Read serial number, robot model, and software version for logging.

This complements RTDE (which handles real-time data exchange) with management-plane functionality.

### Research: Dashboard Server Protocol

The Dashboard Server is a text-based TCP protocol on port 29999. Commands are plain ASCII strings terminated by `\n`. Responses are single-line ASCII strings terminated by `\n`.

**Relevant commands for W26 (e-Series / UR30):**

| Command | Response | Description |
|---------|----------|-------------|
| `robotmode` | `Robotmode: RUNNING` | Current robot mode (NO_CONTROLLER, DISCONNECTED, CONFIRM_SAFETY, BOOTING, POWER_OFF, POWER_ON, IDLE, BACKDRIVE, RUNNING) |
| `programState` | `PLAYING` or `STOPPED` or `PAUSED` | Current program execution state |
| `running` | `Program running: true` | Whether a program is currently executing |
| `safetymode` | `Safetymode: NORMAL` | Safety mode (NORMAL, REDUCED, PROTECTIVE_STOP, RECOVERY, SAFEGUARD_STOP, SYSTEM_EMERGENCY_STOP, ROBOT_EMERGENCY_STOP, VIOLATION, FAULT) |
| `get robot model` | `UR30` | Robot model string |
| `get serial number` | `20XXXXXXXXXX` | Robot serial number |
| `PolyscopeVersion` | `5.x.x` | Software version |
| `load <program.urp>` | `Loading program: ...` | Load a program from the robot filesystem |
| `play` | `Starting program` | Start loaded program |
| `stop` | `Stopped` | Stop running program |
| `pause` | `Pausing program` | Pause running program |
| `power on` | `Powering on` | Power on the robot arm |
| `brake release` | `Brake releasing` | Release brakes after power on |
| `power off` | `Powering off` | Power off the robot arm |
| `shutdown` | `Shutting down` | Shut down the controller |
| `popup <message>` | `showing popup` | Show a popup on the teach pendant |
| `close popup` | `closing popup` | Close the current popup |
| `close safety popup` | `closing safety popup` | Close a safety popup |
| `unlock protective stop` | `Protective stop releasing` | Unlock after protective stop |
| `is in remote control` | `true` or `false` | Whether the robot is in remote control mode |

**Important constraint:** Many commands (play, stop, load, power on, etc.) require the robot to be in **Remote Control mode** (set on the teach pendant). If not in remote mode, the commands will be rejected.

### Interface

**New config values in `config.py`:**

```python
# Dashboard Server
DASHBOARD_PORT = 29999
DASHBOARD_ENABLED = False             # opt-in (not needed for basic operation)
DASHBOARD_POLL_INTERVAL = 2.0        # seconds between state polls
DASHBOARD_TIMEOUT = 5.0              # seconds for command response
UR_PROGRAM_PATH = "/programs/w26_extrusion.urp"  # program to auto-load (if auto-start enabled)
DASHBOARD_AUTO_START = False          # automatically load + play UR program on bridge start
```

**New CLI args:**

```
--dashboard           Enable Dashboard Server integration
--dashboard-auto      Auto-start UR program on bridge startup (implies --dashboard)
--ur-program PATH     URScript program path on robot filesystem
```

### Architecture

**New module: `src/bridge/dashboard_client.py`**

```
class DashboardClient:
    """TCP client for UR30 Dashboard Server (port 29999)."""

    def __init__(self, host: str, port: int = 29999, timeout: float = 5.0)

    # Connection
    def connect(self) -> None
    def disconnect(self) -> None
    @property
    def connected(self) -> bool

    # Low-level
    def send_command(self, command: str) -> str  # send command, return response line

    # Status queries (read-only, safe to call anytime)
    def get_robot_mode(self) -> str          # "RUNNING", "IDLE", "POWER_OFF", etc.
    def get_program_state(self) -> str       # "PLAYING", "STOPPED", "PAUSED"
    def is_running(self) -> bool             # True if program is executing
    def get_safety_mode(self) -> str         # "NORMAL", "PROTECTIVE_STOP", etc.
    def get_robot_model(self) -> str         # "UR30"
    def get_serial_number(self) -> str
    def get_polyscope_version(self) -> str
    def is_in_remote_control(self) -> bool

    # Control commands (require remote control mode)
    def load_program(self, path: str) -> str
    def play(self) -> str
    def stop(self) -> str
    def pause(self) -> str
    def power_on(self) -> str
    def brake_release(self) -> str
    def power_off(self) -> str
    def popup(self, message: str) -> str
    def close_popup(self) -> str
    def close_safety_popup(self) -> str
    def unlock_protective_stop(self) -> str
```

**Protocol implementation notes:**

The Dashboard Server is simple enough that no external library is needed. A plain TCP socket with `socket.makefile()` for line-based read/write is sufficient:

```python
def connect(self) -> None:
    self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._sock.settimeout(self._timeout)
    self._sock.connect((self._host, self._port))
    self._file = self._sock.makefile("rw", buffering=1)
    # Read and discard the welcome banner
    self._banner = self._file.readline().strip()

def send_command(self, command: str) -> str:
    self._file.write(command + "\n")
    self._file.flush()
    return self._file.readline().strip()
```

**Integration into `Bridge`:**

- `Bridge.__init__`: Create `DashboardClient` if `--dashboard` is specified.
- `Bridge._connect_all`: Connect Dashboard Server after RTDE. If `--dashboard-auto`:
  1. Check `is_in_remote_control()`. If not, log error and skip auto-start.
  2. Check `get_robot_mode()`. If `POWER_OFF`, call `power_on()` then `brake_release()` with appropriate waits.
  3. Call `load_program(config.UR_PROGRAM_PATH)`.
  4. Call `play()`.
- **Background poller (optional):** A thread that polls `get_program_state()` and `get_safety_mode()` every `DASHBOARD_POLL_INTERVAL` seconds. If the program stops or the robot enters protective stop, the bridge is notified.

**Integration with watchdog (feature 4):**

The Dashboard Server poller can supplement the watchdog. If `get_program_state()` returns `"STOPPED"` or `"PAUSED"`, the bridge knows the UR30 program is no longer running and should disable the stepper, even before the RTDE watchdog triggers. This provides faster detection of program stop events.

```python
# In Bridge._tick or a periodic check:
if self.dashboard and self.dashboard.connected:
    prog_state = self.dashboard_poller.get_cached_program_state()
    if prog_state in ("STOPPED", "PAUSED") and self.state.stepper_enabled:
        log.warning("UR30 program %s — disabling stepper", prog_state)
        self._stop_extrusion()
```

### Data Flow

```
Bridge startup
    |
    v
DashboardClient.connect() --> TCP port 29999
    |
    v (if auto-start)
power_on() --> brake_release() --> load_program() --> play()
    |
    v
Background poller thread (every 2s)
    |
    +--> get_program_state() --> cache
    +--> get_safety_mode() --> cache
    +--> get_robot_mode() --> cache
    |
    v (read by main loop)
Bridge._tick() checks cached program state
    |
    v (on shutdown)
DashboardClient: stop() --> power_off() (optional) --> disconnect()
```

### Error Handling

| Condition | Handling |
|-----------|----------|
| Dashboard connection refused | Log warning, disable Dashboard features, bridge continues (Dashboard is optional) |
| Dashboard connection drops | Log warning, attempt reconnect on next poll cycle |
| Command returns unexpected response | Log the raw response for debugging, treat as failure |
| Robot not in remote control mode | `is_in_remote_control()` returns False. Log error, skip control commands, continue status polling. |
| Auto-start fails (program not found) | Log error with program path, continue without auto-start |
| Safety mode is not NORMAL | Log the safety mode, set `self.state.fault = True`, send popup with diagnostic message |
| Power-on sequence interrupted | Timeout after configurable wait (e.g., 30s for brake release). Log and continue. |

### Dependencies

- `socket` module (stdlib).
- No external libraries.
- UR30 must be on the same network as the Pi.
- For control commands: UR30 must be in Remote Control mode (teach pendant setting).

---

## 7. Implementation Priority and Dependencies

### Dependency Graph

```
Feature 4 (Watchdog) -----> standalone, no dependencies
Feature 1 (Klipper Status) --> standalone, no dependencies
Feature 6 (Dashboard) -----> standalone, supplements Feature 4
Feature 2 (Speed-Prop) ----> standalone
Feature 5 (Profiles) -------> integrates into Feature 2's rate pipeline
Feature 3 (Data Logging) --> depends on all others for data to log
```

### Recommended Implementation Order

| Priority | Feature | Rationale |
|----------|---------|-----------|
| 1 | **Watchdog Timer** (4) | Safety-critical. Must be in place before any hardware testing. |
| 2 | **Klipper Status Subscription** (1) | Needed for accurate feedback and stall detection. Required for meaningful data logging. |
| 3 | **Data Logging** (3) | Essential for Phase 4 test data. Should be available before integration testing begins. |
| 4 | **Speed-Proportional Mode** (2) | Core functionality improvement. Simplifies URScript and enables profile support. |
| 5 | **Extrusion Profiles** (5) | Builds on feature 2. Needed for pump calibration during Phase 3. |
| 6 | **Dashboard Server** (6) | Nice-to-have for automation. Lowest priority but useful for Phase 4 testing workflow. |

### Estimated Effort

| Feature | Estimated LOC | Estimated Time |
|---------|---------------|----------------|
| Watchdog | ~80 | 2 hours |
| Klipper Status | ~120 | 3 hours |
| Data Logging | ~150 | 3 hours |
| Speed-Proportional | ~50 | 1.5 hours |
| Extrusion Profiles | ~180 | 4 hours |
| Dashboard Client | ~200 | 4 hours |
| **Total** | **~780** | **~17.5 hours** |

### Files Modified or Created

| File | Action | Features |
|------|--------|----------|
| `src/bridge/config.py` | Modify | All (new constants) |
| `src/bridge/bridge_daemon.py` | Modify | All (integration points) |
| `src/bridge/rtde_client.py` | Modify | 4 (add timestamp to recipe) |
| `src/bridge/klipper_client.py` | No changes | -- |
| `src/bridge/klipper_status.py` | **Create** | 1 |
| `src/bridge/watchdog.py` | **Create** | 4 |
| `src/bridge/data_logger.py` | **Create** | 3 |
| `src/bridge/extrusion_profile.py` | **Create** | 5 |
| `src/bridge/profiles.json` | **Create** | 5 |
| `src/bridge/dashboard_client.py` | **Create** | 6 |
| `docs/register_allocation.md` | Modify | 2 (if register-based mode switching), 4 (timestamp field) |

### New Module Summary

```
src/bridge/
    __init__.py          (existing)
    __main__.py          (existing)
    bridge_daemon.py     (existing, modified)
    config.py            (existing, modified)
    klipper_client.py    (existing, unchanged)
    rtde_client.py       (existing, modified)
    klipper_status.py    (NEW - feature 1)
    watchdog.py          (NEW - feature 4)
    data_logger.py       (NEW - feature 3)
    extrusion_profile.py (NEW - feature 5)
    profiles.json        (NEW - feature 5)
    dashboard_client.py  (NEW - feature 6)
```

---

*Design document for W26 Cobot Axis bridge daemon enhancements.*
*All features target Phase 3 implementation, Phase 4 testing.*
