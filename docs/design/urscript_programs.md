# URScript Test and Calibration Programs -- Design Document

**Project:** W26 Cobot Axis
**Author:** Willem (Software/EE)
**Date:** 2026-02-12
**Status:** Design (pre-implementation)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Register Reference](#2-register-reference)
3. [Shared Helper Functions](#3-shared-helper-functions)
4. [Program 1: System Validation Test](#4-program-1-system-validation-test)
5. [Program 2: Pump Calibration](#5-program-2-pump-calibration)
6. [Open Questions](#6-open-questions)

---

## 1. Overview

This document designs two URScript programs that will run on the UR30 teach pendant:

| Program | Purpose |
|---------|---------|
| **System Validation Test** | Verify every link in the chain (UR30 -> Pi -> SKR Pico -> stepper) works correctly. Exercises each register, mode, and fault path. |
| **Pump Calibration** | Characterize pump output vs. stepper speed so we can set `EXTRUSION_MULTIPLIER` and confirm linear flow behavior. |

Both programs reuse the helper functions already defined in `src/urscript/extrusion_control.script`:

- `set_extrusion_mode(mode)` -- write mode register (0/1/2)
- `set_extrusion_rate(rate_mm_s)` -- write commanded rate with safety clamp
- `set_extrusion_enable(enabled)` -- master enable gate
- `set_estop(active)` -- software emergency stop
- `set_home_command(active)` -- trigger homing
- `update_tcp_speed()` -- write current TCP speed magnitude to register
- `get_stepper_status()` -- read status (0=idle, 1=running, 2=error, 3=homing)
- `get_stepper_error()` -- read error code (0=none, 1=comms_lost, 2=stall, 3=thermal)
- `get_actual_extrusion_rate()` -- read actual rate reported by Klipper
- `is_stepper_ready()` -- read ready flag
- `is_stepper_fault()` -- read fault flag
- `wait_for_stepper_ready(timeout_s)` -- blocking wait with timeout
- `init_registers()` -- zero all output registers
- `extrude_along_path(target_pose, speed, accel)` -- speed-synced extrusion move
- `retract(distance_mm, speed_mm_s)` -- timed retraction

Neither program attempts collision-prone moves. All robot motion uses slow velocities (<=50 mm/s), low accelerations (<=0.5 m/s^2), and short travel distances within a pre-verified safe workspace.

---

## 2. Register Reference

Condensed from `docs/register_allocation.md`. Both programs depend on this mapping.

### Output Registers (UR30 -> Pi)

| Register | Type | Name in Code | Values |
|----------|------|-------------|--------|
| `output_int_register_0` | INT32 | mode | 0=off, 1=extrude, 2=retract |
| `output_double_register_0` | DOUBLE | extrusion_rate | mm/s commanded |
| `output_double_register_1` | DOUBLE | tcp_speed | mm/s magnitude |
| `output_bit_register_64` | BOOL | enable | master gate |
| `output_bit_register_65` | BOOL | estop | software e-stop |
| `output_bit_register_66` | BOOL | home | homing trigger |

### Input Registers (Pi -> UR30)

| Register | Type | Name in Code | Values |
|----------|------|-------------|--------|
| `input_int_register_0` | INT32 | status | 0=idle, 1=running, 2=error, 3=homing |
| `input_int_register_1` | INT32 | error_code | 0=none, 1=comms_lost, 2=stall, 3=thermal |
| `input_double_register_0` | DOUBLE | actual_rate | mm/s from Klipper |
| `input_bit_register_64` | BOOL | ready | stepper ready |
| `input_bit_register_65` | BOOL | fault | fault condition active |

---

## 3. Shared Helper Functions

Both programs will use the helpers from `extrusion_control.script` directly (loaded as a preamble or imported via the teach pendant's script editor). Two additional utility functions are needed.

### 3.1 `log_to_pendant(msg)`

Display a status line on the teach pendant log tab. Uses the built-in `textmsg()` function which writes to the UR log.

```
def log_to_pendant(msg):
    textmsg(msg)
end
```

### 3.2 `assert_status(expected, label)`

Read the stepper status register, compare to an expected value, and display PASS/FAIL.

```
def assert_status(expected, label):
    local actual = get_stepper_status()
    if actual == expected:
        textmsg(str_cat("PASS: ", label))
    else:
        textmsg(str_cat("FAIL: ", label, " expected=", expected, " got=", actual))
    end
end
```

### 3.3 `assert_ready(expected, label)`

Same pattern for the ready flag.

```
def assert_ready(expected, label):
    local actual = is_stepper_ready()
    if actual == expected:
        textmsg(str_cat("PASS: ", label))
    else:
        textmsg(str_cat("FAIL: ", label, " expected=", to_str(expected), " got=", to_str(actual)))
    end
end
```

### 3.4 `assert_fault(expected, label)`

Same pattern for the fault flag.

```
def assert_fault(expected, label):
    local actual = is_stepper_fault()
    if actual == expected:
        textmsg(str_cat("PASS: ", label))
    else:
        textmsg(str_cat("FAIL: ", label, " expected=", to_str(expected), " got=", to_str(actual)))
    end
end
```

---

## 4. Program 1: System Validation Test

### 4.1 Purpose

Confirm the full communication chain is operational before running real deposition paths. The test exercises every output register, reads back every input register, and verifies the system responds correctly to each command type including fault conditions.

A successful run means:

- The RTDE connection between UR30 and Pi is live.
- The bridge daemon is translating commands to Klipper.
- Klipper is driving the SKR Pico MCU and the stepper responds.
- Status feedback propagates back from Klipper through the bridge to the UR30.
- E-stop, enable/disable, and homing work as designed.

### 4.2 Prerequisites

| Requirement | How to Verify |
|-------------|--------------|
| Pi powered and booted | SSH into Pi, or check Moonraker web UI from Pi400 |
| Klipper running and ready | Moonraker dashboard shows "Ready" state, or `curl http://<pi>:7125/printer/info` returns `state: "ready"` |
| Bridge daemon running | `systemctl status bridge` on Pi, or check Pi logs |
| RTDE connection established | Bridge daemon log shows "RTDE connected" |
| SKR Pico connected via USB | `ls /dev/serial/by-id/` on Pi shows the Klipper device |
| Stepper motor wired to SKR Pico E-driver | Physical inspection; motor leads on E-motor connector |
| Robot in a safe configuration | Robot at a known home position, workspace clear, speed slider at 25-50% |
| Teach pendant in manual mode | Allows single-step execution and easy stop |

### 4.3 Procedure

The test is divided into sub-tests. Each sub-test is independent so the operator can skip or re-run individual sections. Between each sub-test there is a 1-second pause for the operator to observe teach pendant output.

#### Sub-test A: Register Initialization

**What it checks:** `init_registers()` zeroes all output registers and the bridge reports idle+ready.

1. Call `init_registers()`.
2. Wait 0.5s for registers to propagate through bridge.
3. Assert `status == 0` (idle).
4. Assert `ready == True`.
5. Assert `fault == False`.
6. Assert `error_code == 0` (none).
7. Log PASS/FAIL for each check.

**Expected result:** All four assertions pass. If ready is False, the bridge daemon may not be running or Klipper is not in "ready" state.

#### Sub-test B: Enable / Disable

**What it checks:** The enable bit gates stepper operation. Enabling with mode=off should not cause motion.

1. `set_extrusion_enable(True)`.
2. Wait 0.2s.
3. Assert `status == 0` (idle) -- stepper should not be moving because mode is still off.
4. `set_extrusion_enable(False)`.
5. Wait 0.2s.
6. Assert `status == 0` (idle).
7. Log PASS/FAIL.

**Expected result:** Stepper remains idle in both cases. The enable bit alone does not start motion.

#### Sub-test C: Extrude Mode (Fixed Rate, No Robot Motion)

**What it checks:** Commanding extrusion at a fixed rate causes the stepper to run. The actual rate register reports a non-zero value.

1. `set_extrusion_enable(True)`.
2. `set_extrusion_mode(1)` (extrude).
3. `set_extrusion_rate(10.0)` (10 mm/s).
4. Wait 2.0s for the stepper to ramp up and stabilize.
5. Read `get_stepper_status()` -- expect 1 (running).
6. Read `get_actual_extrusion_rate()` -- expect a value close to 10.0 (within ~20% tolerance, TBD after calibration).
7. Log both values to teach pendant.
8. `set_extrusion_mode(0)` (off).
9. `set_extrusion_enable(False)`.
10. Wait 1.0s.
11. Assert `status == 0` (idle).
12. Log PASS/FAIL.

**Expected result:** Stepper runs audibly/visibly during step 4. Status reads 1 (running). Actual rate is non-zero and approximately 10 mm/s. After stopping, status returns to 0.

#### Sub-test D: Retract Mode

**What it checks:** Retract mode (mode=2) drives the stepper in the reverse direction.

1. `set_extrusion_enable(True)`.
2. `set_extrusion_mode(2)` (retract).
3. `set_extrusion_rate(5.0)` (5 mm/s).
4. Wait 1.0s -- observe stepper rotation direction (should be opposite to extrude).
5. Read `get_stepper_status()` -- expect 1 (running).
6. `set_extrusion_mode(0)` (off).
7. `set_extrusion_enable(False)`.
8. Wait 0.5s.
9. Assert `status == 0`.
10. Log PASS/FAIL.

**Expected result:** Stepper rotates in reverse direction during step 4. Visual or audible confirmation required from operator. If a pump is attached, retraction direction should relieve pressure (suck back).

#### Sub-test E: Homing

**What it checks:** The home command triggers a homing sequence and the status register transitions through homing (3) back to idle (0).

1. `set_home_command(True)`.
2. `sync()` -- ensure the register write is committed.
3. `set_home_command(False)`.
4. Wait 0.2s.
5. Read `get_stepper_status()` -- may be 3 (homing) if caught quickly, or 0 (idle) if homing completed.
6. Wait 2.0s for homing to complete.
7. Assert `status == 0` (idle).
8. Assert `ready == True`.
9. Log PASS/FAIL.

**Expected result:** The bridge daemon logs "Homing requested" and "Homing complete". Status returns to idle. The current implementation zeros the stepper position without physical motion (no endstop), so this test validates the register handshake only.

#### Sub-test F: E-Stop

**What it checks:** The software emergency stop immediately halts the stepper and transitions the system to an error state.

1. Start extrusion: `set_extrusion_enable(True)`, `set_extrusion_mode(1)`, `set_extrusion_rate(15.0)`.
2. Wait 1.0s -- confirm stepper is running.
3. `set_estop(True)`.
4. Wait 0.5s.
5. Read `get_stepper_status()` -- expect 2 (error).
6. Read `get_stepper_error()` -- log the error code (bridge may report ERR_NONE=0 or specific code depending on implementation).
7. Read `is_stepper_fault()` -- may be True.
8. Log all values.
9. `set_estop(False)`.
10. `init_registers()`.
11. Wait 2.0s for recovery.
12. Read `get_stepper_status()` -- check if system recovers to idle (0).
13. Log PASS/FAIL.

**Expected result:** Stepper stops immediately (within one RTDE cycle, ~2ms). Status goes to error state. After clearing e-stop and reinitializing, the bridge daemon must be restarted or must auto-recover -- this test reveals the recovery behavior.

**Important note on recovery:** The current bridge implementation calls `klipper.emergency_stop()` on e-stop, which puts Klipper into a shutdown state requiring a `FIRMWARE_RESTART` to recover. This sub-test documents whether the operator must manually restart Klipper/bridge after an e-stop. If so, the remaining sub-tests cannot continue without intervention.

#### Sub-test G: Speed-Synchronized Extrusion with Robot Motion

**What it checks:** The full speed-sync loop -- robot moves, TCP speed is written to the register, and extrusion rate tracks proportionally.

**Waypoints:** Two waypoints are needed, defining a short linear path in a safe region of the workspace. These must be taught on the physical robot and will vary per installation. The design specifies placeholder poses.

1. Define `start_pose` and `end_pose` (linear path, ~100mm long).
2. `init_registers()`.
3. Move robot to `start_pose` with `movej()` (joint move, no extrusion).
4. Wait 1.0s.
5. Call `extrude_along_path(end_pose, 0.050, 0.5)` (50 mm/s, 0.5 m/s^2 accel).
6. During motion, the `extrude_along_path` function:
   - Writes TCP speed to `output_double_register_1` each cycle.
   - Computes `rate = tcp_speed * EXTRUSION_MULTIPLIER` and writes to `output_double_register_0`.
   - Checks for stepper faults.
7. After motion completes, read `get_actual_extrusion_rate()` -- should be near zero (robot stopped).
8. Call `retract(2.0, 10.0)` -- 2mm retraction at 10 mm/s.
9. Wait 0.5s.
10. Assert `status == 0`.
11. Log PASS/FAIL.

**Expected result:** Stepper speed ramps up as robot accelerates, holds steady during constant velocity, and ramps down as robot decelerates. If a pump is attached, paste dispenses during the move and retracts at the end.

#### Sub-test H: Fault Handling (Bridge Disconnected)

**What it checks:** What happens when the bridge daemon is not running or loses connection. The UR30 should detect that the stepper is not ready and handle gracefully.

**This sub-test requires manual intervention:** The operator (or a second person at the Pi) must stop the bridge daemon before running this test.

1. Operator stops the bridge daemon on the Pi (`sudo systemctl stop bridge` or Ctrl+C).
2. Wait 3.0s for RTDE timeout.
3. Read `is_stepper_ready()` -- expect False (bridge is no longer writing input registers; stale values depend on RTDE watchdog behavior).
4. Attempt `wait_for_stepper_ready(3.0)` -- expect timeout popup.
5. Log result.
6. Operator restarts the bridge daemon.
7. Wait 5.0s for reconnection.
8. Read `is_stepper_ready()` -- expect True.
9. Log PASS/FAIL.

**Expected result:** With the bridge down, the ready flag goes stale or False. `wait_for_stepper_ready()` times out and displays a popup, preventing motion. After bridge restart, the system recovers.

**RTDE watchdog note:** The RTDE protocol supports a watchdog mechanism. If the external client stops sending data within a configured timeout, the UR controller can reset input registers to zero. Whether this is enabled depends on bridge daemon configuration. This test reveals the actual behavior.

#### Sub-test I: Status Register Readback Display

**What it checks:** All input registers can be read and displayed to the teach pendant for operator verification.

1. `init_registers()`.
2. Read and display every input register:
   - `get_stepper_status()` -> log value and meaning
   - `get_stepper_error()` -> log value and meaning
   - `get_actual_extrusion_rate()` -> log value
   - `is_stepper_ready()` -> log value
   - `is_stepper_fault()` -> log value
3. Enable extrusion briefly, re-read and display.
4. Disable, re-read and display.

**Expected result:** Values change as expected between idle and running states. This sub-test is primarily for operator visibility -- it does not assert pass/fail but gives confidence that all registers are accessible.

### 4.4 Safety

| Concern | Mitigation |
|---------|-----------|
| Robot collision | Sub-test G uses operator-taught waypoints verified as collision-free. All other sub-tests involve no robot motion. |
| Runaway stepper | MAX_EXTRUSION_RATE=50 mm/s is enforced in `set_extrusion_rate()`. E-stop sub-test (F) validates the halt mechanism. |
| Paste spill (if pump attached) | Run Sub-tests A-F without pump connected first. For Sub-test G with pump, place catch tray under nozzle. |
| Speed slider | Set teach pendant speed slider to 25% for first run, increase after confidence. |
| Operator in workspace | Run in manual mode (reduced speed, 3-position enabling device required). |
| Bridge crash during motion | `extrude_along_path()` checks `is_stepper_fault()` each cycle and calls `stopl()` on fault. |

### 4.5 Data Collection

The test program writes results to the teach pendant log via `textmsg()`. The operator can:

1. **Read results on screen:** The teach pendant Log tab shows all `textmsg()` output.
2. **Export logs:** UR controller logs are accessible via SSH at `/programs/log/` or via the Dashboard Server.
3. **Summary:** Count PASS vs. FAIL lines. All sub-tests must pass for system validation.

### 4.6 Failure Modes

| Symptom | Likely Cause | Diagnostic Steps |
|---------|-------------|-----------------|
| Sub-test A fails: ready=False | Bridge daemon not running, or Klipper not ready | SSH to Pi, check `systemctl status bridge` and Moonraker dashboard |
| Sub-test C fails: status stays 0 | Bridge receives command but Klipper does not execute | Check bridge daemon log for errors; check Klipper log for G-code rejections |
| Sub-test C fails: actual_rate=0 | Bridge does not query Klipper status, or Klipper status object not reporting | Bridge daemon TODO: read actual rate from Klipper (see `bridge_daemon.py` line 298) |
| Sub-test D: wrong direction | Dir pin polarity inverted | Swap `dir_pin` polarity in `printer.cfg` (add/remove `!` prefix) |
| Sub-test F: no recovery after e-stop | Klipper entered shutdown state, requires FIRMWARE_RESTART | Document this as expected behavior; operator must restart Klipper after e-stop |
| Sub-test G: extrusion does not track speed | EXTRUSION_MULTIPLIER too low, or bridge not processing TCP speed register | Run calibration program (Program 2) to set correct multiplier |
| Sub-test H: ready stays True after bridge stop | RTDE watchdog not configured; stale register values | Configure RTDE watchdog in bridge daemon, or implement a heartbeat register |
| Any sub-test: RTDE timeout popup | Network issue, wrong IP, or UR controller not serving RTDE | Verify UR30 IP in bridge config, check ethernet cable and switch |

---

## 5. Program 2: Pump Calibration

### 5.1 Purpose

Characterize the pump so we can set `EXTRUSION_MULTIPLIER` (in both `src/urscript/extrusion_control.script` and `src/bridge/config.py`). This program produces the data needed to answer:

1. **What is the relationship between stepper speed (mm/s) and volumetric flow rate?** Is it linear?
2. **What extrusion multiplier maps TCP speed to correct deposition rate?** (`EXTRUSION_MULTIPLIER = desired_rate / tcp_speed`)
3. **How effective is retraction at stopping flow?** What retraction distance and speed minimize ooze?
4. **What is the actual end-to-end latency?** How long after a speed command does the flow rate visibly change?

### 5.2 Prerequisites

All prerequisites from the validation test, plus:

| Requirement | How to Verify |
|-------------|--------------|
| Pump physically connected to stepper | Motor shaft coupled to pump input |
| Pump primed with paste (or test fluid) | No air in fluid path, nozzle producing flow when stepper runs |
| Scale or graduated cylinder available | For measuring dispensed volume/weight per run |
| Stopwatch or timer | For latency measurement (Sub-test D). Alternatively use teach pendant `get_steptime()` timing. |
| Catch tray under nozzle | Prevent mess during calibration |
| Clean nozzle tip | Ensure consistent bead formation |
| System validation test (Program 1) passed | Full chain verified operational |

### 5.3 Procedure

#### Sub-test A: Flow Rate vs. Stepper Speed (Linearity)

**What it measures:** Dispensed volume at each of several fixed stepper speeds. Determines whether flow is proportional to stepper speed and identifies any dead zone or saturation.

**Method:**

1. Define a speed array: `[2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0]` mm/s.
2. For each speed in the array:
   a. Tare the scale (or note graduated cylinder level).
   b. `init_registers()`.
   c. `set_extrusion_enable(True)`.
   d. `set_extrusion_mode(1)` (extrude).
   e. `set_extrusion_rate(speed)`.
   f. Wait exactly 10.0s (or use a configurable `DISPENSE_TIME` constant).
   g. `set_extrusion_mode(0)`.
   h. `set_extrusion_enable(False)`.
   i. Wait 2.0s for dripping to stop.
   j. Record dispensed mass (grams) or volume (mL) -- operator reads from scale/cylinder and notes on paper or enters into a teach pendant popup.
   k. Log the commanded speed and `get_actual_extrusion_rate()` to the teach pendant.
   l. Pause 5.0s between runs for the operator to reset the measurement apparatus.
3. After all speeds: `init_registers()`.

**Data to record per speed level:**

| Field | Source | Units |
|-------|--------|-------|
| Commanded speed | Program constant | mm/s |
| Actual rate (Klipper) | `get_actual_extrusion_rate()` | mm/s |
| Dispense time | Program constant (10s) | s |
| Dispensed mass | Operator (scale reading) | g |
| Dispensed volume | Computed from mass and paste density, or direct cylinder reading | mL |
| Flow rate | volume / time | mL/s |

**Expected result:** A linear or near-linear relationship between commanded speed and flow rate. If the pump has a dead zone (no flow below a threshold speed), that threshold speed is identified.

**Post-processing:** Plot flow rate vs. commanded speed. The slope of the best-fit line gives the pump's volumetric constant. Combined with the desired bead geometry and TCP speed, this determines `EXTRUSION_MULTIPLIER`:

```
EXTRUSION_MULTIPLIER = (desired_bead_cross_section_mm2 * 1.0) / (pump_volumetric_constant_mm3_per_mm_s)
```

The exact formula depends on pump type (syringe vs. peristaltic vs. progressive cavity) and will be finalized when the pump hardware is received.

#### Sub-test B: Speed-Synced Extrusion with Gravimetric Check

**What it measures:** Whether the speed-synchronized extrusion (`extrude_along_path`) deposits the correct amount of material during a known-length robot move.

**Method:**

1. Define `start_pose` and `end_pose` (straight line, known length L mm -- measure with a ruler or read from UR30 kinematics).
2. Compute expected dispense: `expected_volume = L * bead_cross_section_mm2` (if known) or simply weigh the output.
3. Tare scale, position catch tray under path.
4. Move robot to `start_pose` via `movej()`.
5. Call `extrude_along_path(end_pose, 0.030, 0.5)` (30 mm/s, 0.5 m/s^2).
6. Call `retract(2.0, 10.0)`.
7. Record dispensed mass.
8. Repeat at different speeds: 10, 20, 30, 50 mm/s.
9. For each speed, log: TCP speed, path length, dispensed mass, EXTRUSION_MULTIPLIER used.

**Expected result:** Dispensed mass scales linearly with path length and is consistent across TCP speeds (because the speed-sync loop adjusts extrusion rate). If mass varies with TCP speed, the multiplier or latency compensation needs adjustment.

#### Sub-test C: Retraction Effectiveness

**What it measures:** How much retraction distance and speed is needed to cleanly stop flow after extrusion ends.

**Method:**

1. Define retraction test parameters:

   | Trial | Retraction Distance (mm) | Retraction Speed (mm/s) |
   |-------|-------------------------|------------------------|
   | 1 | 0.0 (no retraction) | -- |
   | 2 | 0.5 | 5.0 |
   | 3 | 1.0 | 5.0 |
   | 4 | 2.0 | 10.0 |
   | 5 | 3.0 | 10.0 |
   | 6 | 5.0 | 20.0 |

2. For each trial:
   a. Move robot to start_pose.
   b. Extrude at 20 mm/s for 5.0s (fixed rate, no robot motion -- isolate retraction behavior).
   c. `set_extrusion_mode(0)`.
   d. Immediately call `retract(distance, speed)`.
   e. Wait 5.0s.
   f. Observe and record: time until dripping stops, total post-extrusion drip mass.
   g. Log trial parameters to teach pendant.

3. The trial with shortest "drip time" and least post-extrusion mass wins.

**Expected result:** No retraction (trial 1) produces the most ooze. Increasing retraction distance reduces ooze up to a point, after which further retraction sucks air into the nozzle (undesirable). The optimal retraction parameters are the smallest values that produce clean stops.

**Data to record per trial:**

| Field | Source | Units |
|-------|--------|-------|
| Retraction distance | Program constant | mm |
| Retraction speed | Program constant | mm/s |
| Time until drip stops | Operator stopwatch | s |
| Post-extrusion drip mass | Scale | g |
| Air ingestion observed | Operator visual (yes/no) | -- |

#### Sub-test D: Latency Measurement

**What it measures:** The time delay between a speed command change on the UR30 and an observable change in flow rate at the nozzle. This characterizes the end-to-end latency empirically (compare against the ~8ms estimate in `docs/latency_analysis.md`).

**Method 1: Software timing (coarse, ~2ms resolution)**

1. Start extrusion at 0 mm/s (enabled, mode=extrude, rate=0).
2. Wait 1.0s for steady state.
3. Record `t0 = get_steptime()` (UR controller time).
4. `set_extrusion_rate(20.0)` -- step change from 0 to 20 mm/s.
5. Poll `get_actual_extrusion_rate()` every `sync()` cycle until it exceeds 1.0 mm/s.
6. Record `t1 = get_steptime()`.
7. Latency = accumulated cycles * cycle_time (2ms per sync cycle on UR30).
8. Repeat 10 times, compute mean and standard deviation.
9. Log all values to teach pendant.

**Method 2: Hardware timing (precise, requires oscilloscope) -- Phase 4**

1. Connect oscilloscope Channel 1 to a UR30 digital output.
2. Connect oscilloscope Channel 2 to the SKR Pico STEP pin (gpio14).
3. In URScript: toggle the digital output at the same instant the speed command is written.
4. Measure time from digital output edge to first step pulse on the oscilloscope.
5. This gives the true end-to-end latency including Klipper's buffer.

Method 1 is available immediately (no extra hardware). Method 2 is planned for Phase 4 formal testing.

**Expected result (Method 1):** Latency of 4-20ms (2-10 sync cycles). The actual_rate register update depends on the bridge daemon's status reporting frequency (currently 125 Hz = 8ms period), so measured latency will be quantized to ~8ms increments. True motor response may be faster than what the register readback shows.

**Expected result (Method 2):** Latency of 5-20ms for the first step pulse, plus ~100ms for steady-state speed if Klipper's lookahead buffer is full. During continuous streaming (steady-state operation), speed changes should propagate within ~8ms.

### 5.4 Safety

All safety mitigations from the validation test apply, plus:

| Concern | Mitigation |
|---------|-----------|
| Paste overflow | Use a large catch tray. Sub-test A dispenses up to 50 mm/s * 10s = 500mm of material per run; ensure container is adequate. |
| Nozzle clog | If flow stops unexpectedly, abort test and clean nozzle before continuing. Do not increase speed to force a clog -- this risks bursting connections. |
| Hot paste (if heated) | Wear appropriate PPE. Ensure tray can handle paste temperature. |
| Repeated start/stop cycling | Sub-test C cycles the pump 6 times. Allow 5s between trials for motor/driver cooling. Monitor TMC2209 temperature if StallGuard feedback is available. |

### 5.5 Data Collection

Calibration data is collected in two ways:

1. **Teach pendant log:** All `textmsg()` output is recorded in the UR controller log. Export via SSH or USB for post-processing.

2. **Manual data sheet:** The operator records scale readings and visual observations on a paper data sheet (or digital spreadsheet) since the teach pendant cannot read a scale automatically.

A suggested data sheet template:

```
W26 Pump Calibration Data Sheet
Date: ___________  Operator: ___________
Paste material: ___________  Paste density: ___________ g/mL
Nozzle diameter: ___________ mm
Ambient temperature: ___________ C

Sub-test A: Flow Rate vs. Speed
Trial | Speed (mm/s) | Duration (s) | Mass (g) | Volume (mL) | Flow (mL/s) | Actual Rate (mm/s)
------+-------------+-------------+---------+------------+------------+-------------------
  1   |     2.0     |    10.0     |         |            |            |
  2   |     5.0     |    10.0     |         |            |            |
  3   |    10.0     |    10.0     |         |            |            |
  4   |    15.0     |    10.0     |         |            |            |
  5   |    20.0     |    10.0     |         |            |            |
  6   |    30.0     |    10.0     |         |            |            |
  7   |    40.0     |    10.0     |         |            |            |
  8   |    50.0     |    10.0     |         |            |            |

Sub-test C: Retraction Effectiveness
Trial | Retract Dist (mm) | Retract Speed (mm/s) | Drip Time (s) | Drip Mass (g) | Air? (Y/N)
------+-------------------+---------------------+---------------+---------------+-----------
  1   |       0.0         |        --           |               |               |
  2   |       0.5         |       5.0           |               |               |
  3   |       1.0         |       5.0           |               |               |
  4   |       2.0         |      10.0           |               |               |
  5   |       3.0         |      10.0           |               |               |
  6   |       5.0         |      20.0           |               |               |

Sub-test D: Latency
Trial | Latency (ms)
------+-------------
  1   |
  2   |
  3   |
...   |
 10   |
Mean: _____ ms   Std Dev: _____ ms
```

### 5.6 Expected Results and Using the Data

#### Determining EXTRUSION_MULTIPLIER

From Sub-test A, compute the pump's flow constant:

```
K_pump = mean(flow_rate_mL_s / commanded_speed_mm_s)
```

Then, given the desired bead cross-section area A (mm^2) at TCP speed v (mm/s):

```
required_flow = A * v   (mm^3/s = mL/s * 1000)
required_stepper_speed = required_flow / K_pump
EXTRUSION_MULTIPLIER = required_stepper_speed / v
```

For the initial case where we want stepper speed to simply equal TCP speed (1:1 mapping):

```
EXTRUSION_MULTIPLIER = 1.0
```

Then adjust based on observed bead quality.

#### Confirming Linearity

Plot flow rate vs. commanded speed from Sub-test A. If the relationship is linear (R^2 > 0.95), a single multiplier is sufficient. If non-linear, the bridge daemon may need a lookup table or polynomial mapping instead of a simple multiplier.

#### Setting Retraction Parameters

From Sub-test C, select the retraction distance and speed that produce clean stops without air ingestion. Update:
- `retract()` call parameters in production URScript programs
- Optionally add `RETRACT_DISTANCE` and `RETRACT_SPEED` constants to `src/bridge/config.py`

#### Validating Latency

From Sub-test D, compare measured latency against the ~8ms estimate in `docs/latency_analysis.md`. If measured latency is significantly higher (>20ms), investigate:
- Bridge daemon processing time (profiling)
- Klipper lookahead buffer size
- USB serial throughput

### 5.7 Failure Modes

| Symptom | Likely Cause | Diagnostic Steps |
|---------|-------------|-----------------|
| No flow at any speed | Pump not primed, nozzle clogged, stepper not coupled to pump | Verify motor shaft turns (visual); check coupling; prime pump |
| Flow at high speeds only | Dead zone / static friction in pump | Note threshold speed; may need minimum speed parameter in bridge config |
| Non-linear flow (saturates at high speed) | Pump cavitation, paste too viscous at speed, or stepper missing steps | Reduce max speed; check TMC2209 for stall events; try lower viscosity fluid |
| Flow continues after stop (excessive ooze) | Pressure in fluid path, no retraction | Increase retraction distance (Sub-test C); add dwell time before retraction |
| Inconsistent mass between identical trials | Air bubbles in paste, pump priming issue, scale drift | Re-prime pump, degas paste, tare scale between runs |
| Measured latency >> 20ms | Klipper buffer delay, bridge daemon backlog | Reduce Klipper lookahead; profile bridge daemon; check for Python GC pauses |
| Stepper stalls at high rate | Insufficient motor current, excessive load | Increase `run_current` in printer.cfg (check thermal limits); reduce max speed |
| Actual rate register always 0 | Bridge daemon not reading Klipper status | Known limitation: `bridge_daemon.py` line 298 has TODO for actual rate readback; fix before calibration |

---

## 6. Open Questions

These items need resolution before or during implementation:

| # | Question | Depends On | Impact |
|---|----------|-----------|--------|
| 1 | What pump type will be used (syringe, peristaltic, progressive cavity)? | Hardware procurement (Dawood) | Determines flow constant, retraction behavior, dead zone characteristics |
| 2 | What is the paste density and viscosity? | Material specification | Needed to convert mass measurements to volumetric flow rate |
| 3 | Does the bridge daemon recover automatically after e-stop, or must Klipper be restarted? | Bridge daemon testing | Affects Sub-test F procedure and production e-stop handling |
| 4 | Is the RTDE watchdog configured? What happens to input registers when the bridge stops sending? | Bridge daemon RTDE configuration | Affects Sub-test H and safety during bridge crashes |
| 5 | Can `get_actual_extrusion_rate()` return meaningful data? The bridge daemon currently writes `current_rate` (the commanded rate) rather than the Klipper-reported actual rate (TODO on line 298). | Bridge daemon development | Affects Sub-tests C, D, and all calibration data that relies on actual rate readback |
| 6 | What are safe waypoints for Sub-test G and Sub-test B? | Physical robot installation, workspace survey | Must be taught on the actual hardware before running |
| 7 | What bead cross-section is desired for the target application? | Application requirements | Needed to compute final EXTRUSION_MULTIPLIER |

---

*This document was prepared as part of the W26 Cobot Axis project (ME 472, Winter 2026). It is a design document -- no implementation code is included. Implementation will follow once the design is reviewed and open questions are resolved.*
