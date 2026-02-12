# Phase 4 Test Procedures — W26 Cobot Axis

**Project:** W26 Cobot Axis -- UR30 External Stepper Axis for Metal Paste Dispensing
**Course:** ME 472 -- Mechatronics, Winter 2026, University of Michigan
**Team:** Willem (Software/EE), Dawood (Mechanical)
**Date:** 2026-02-12
**Status:** Planning (pre-hardware)

---

## Table of Contents

1. [Overview](#1-overview)
2. [General Test Conditions](#2-general-test-conditions)
3. [TP-01: End-to-End Functional Test](#3-tp-01-end-to-end-functional-test)
4. [TP-02: Latency Characterization](#4-tp-02-latency-characterization)
5. [TP-03: Accuracy Test](#5-tp-03-accuracy-test)
6. [TP-04: Fault Handling Test](#6-tp-04-fault-handling-test)
7. [TP-05: Endurance Test](#7-tp-05-endurance-test)
8. [Data Collection Plan](#8-data-collection-plan)
9. [Test Schedule](#9-test-schedule)
10. [Appendix A: Equipment List](#appendix-a-equipment-list)
11. [Appendix B: Data Sheet Templates](#appendix-b-data-sheet-templates)

---

## 1. Overview

This document defines formal test procedures for Phase 4 (Test and Reporting) of the W26 Cobot Axis project. The tests verify that the system meets the performance requirements established in the problem analysis (`docs/problem_analysis.md`) and validate the latency predictions from `docs/latency_analysis.md`.

### Requirements Traceability

| Requirement | Source | Verified By |
|-------------|--------|-------------|
| End-to-end command latency < 20 ms typical | Problem analysis, Section 3.1 | TP-02 |
| Extrusion rate tracks TCP speed | Problem analysis, Section 1 | TP-01, TP-03 |
| Stepper responds to all RTDE commands (extrude, retract, stop, e-stop, home) | Register allocation, all registers | TP-01 |
| Safe behavior on RTDE disconnect (F1) | Problem analysis, Section 4 | TP-04a |
| Safe behavior on stepper stall (F2) | Problem analysis, Section 4 | TP-04b |
| Safe behavior on Klipper crash (F4) | Problem analysis, Section 4 | TP-04c |
| Safe behavior on USB disconnect (F5) | Problem analysis, Section 4 | TP-04d |
| Thermal stability during extended operation | Problem analysis, Section 4 (F6) | TP-05 |
| System operates within 2A continuous at 24V | Problem analysis, Section 6.2 | TP-05 |

### Test Environment

All testing takes place in the ME 472 robotics lab with the assembled W26 system:

```
UR30 Robot Controller  --RTDE/TCP-IP-->  Pi (Klipper host + RTDE bridge)  --USB Serial-->  SKR Pico  -->  Stepper Motor  -->  Pump
                        (gigabit switch)
```

---

## 2. General Test Conditions

### 2.1 Pre-Test Checklist

Before beginning any test procedure, verify all of the following:

- [ ] UR30 powered on, brakes released, in Remote mode
- [ ] Pi powered and running (Klipper host + Moonraker + bridge daemon)
- [ ] SKR Pico connected via USB, Klipper firmware responding (`FIRMWARE_RESTART` succeeds)
- [ ] Stepper motor connected to SKR Pico E-axis driver output
- [ ] Ethernet cable between UR30 and Pi through gigabit switch
- [ ] Bridge daemon running: `systemctl status bridge-daemon` or `python -m bridge --host <UR30_IP>`
- [ ] URScript extrusion_control.script loaded on UR30 teach pendant
- [ ] Klipper reports "Ready" state (check via Mainsail or `curl http://localhost:7125/printer/info`)
- [ ] Pi400 connected to same network for monitoring (optional but recommended)
- [ ] Ambient temperature recorded
- [ ] All cable connections mechanically secured

### 2.2 Safety Precautions

- The UR30 must remain in collaborative mode with force-limited stopping enabled at all times.
- Keep the UR30 teach pendant within reach with the emergency stop button accessible.
- The software e-stop (`output_bit_register_65`) is a secondary stop mechanism. The teach pendant hardware e-stop is the primary safety control.
- During fault injection tests (TP-04), the robot must be stationary or moving at reduced speed (< 50 mm/s).
- When blocking the motor shaft (TP-04b), use a soft clamp or manual grip. Do not use rigid fixturing that could damage the coupling.

### 2.3 Data Recording Conventions

- All timestamps in UTC or local time with timezone noted.
- All speeds in mm/s.
- All temperatures in degrees Celsius.
- All latencies in milliseconds.
- Photographs of oscilloscope captures saved as PNG with test ID in filename.
- Bridge daemon logs saved with `--log-level DEBUG` for all tests.
- File naming: `<test_id>_<date>_<run_number>.<ext>` (e.g., `TP02_20260325_run1.csv`).

---

## 3. TP-01: End-to-End Functional Test

| Field | Value |
|-------|-------|
| **Test ID** | TP-01 |
| **Name** | End-to-End Functional Test |
| **Objective** | Verify that the complete communication chain (UR30 -> RTDE -> Pi bridge -> Klipper -> SKR Pico -> stepper) is functional: the UR30 can command extrusion and the stepper motor responds at the correct speed and direction. |
| **Estimated Duration** | 45 minutes |

### 3.1 Equipment

| Item | Purpose |
|------|---------|
| UR30 + teach pendant | Issue extrusion commands via URScript |
| Pi (headless) | Run bridge daemon and Klipper |
| SKR Pico + stepper motor + pump | Actuator under test |
| Pi400 or laptop | SSH into Pi for log monitoring; Mainsail web UI |
| Tachometer or rotary encoder (optional) | Independently verify motor RPM if available |
| Ruler or calipers | Verify linear displacement if pump produces measurable output |

### 3.2 Setup

1. Complete the pre-test checklist (Section 2.1).
2. Start the bridge daemon with debug logging: `python -m bridge --host <UR30_IP> --log-level DEBUG`
3. Open a second SSH session to the Pi and run: `tail -f /var/log/bridge-daemon.log` (or wherever logs are directed).
4. Open Mainsail web UI on Pi400 to monitor Klipper state.
5. On the UR30 teach pendant, load `extrusion_control.script`.

### 3.3 Procedure

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | On the UR30, write `output_bit_register_64 = True` (enable) and `output_int_register_0 = 0` (mode OFF). Verify bridge receives the enable signal. | Bridge log shows "enable=True, mode=OFF". Stepper does not move. `input_bit_register_64` (ready) reads True on the teach pendant. | Screenshot of bridge log |
| 2 | Set `output_int_register_0 = 1` (EXTRUDE) and `output_double_register_0 = 5.0` (5 mm/s). | Stepper begins rotating in the forward (extrude) direction. Bridge log shows "RUNNING" status and rate = 5.0. | Observe motor rotation direction; record bridge log |
| 3 | Increase rate to 10.0 mm/s by writing `output_double_register_0 = 10.0`. | Stepper accelerates smoothly to the new speed. No stuttering or stalling. | Bridge log; visual observation |
| 4 | Increase rate to 25.0 mm/s. | Stepper reaches 25 mm/s. Bridge log confirms rate update. | Bridge log |
| 5 | Increase rate to 50.0 mm/s (maximum configured limit). | Stepper reaches 50 mm/s. No stall. | Bridge log |
| 6 | Set rate to 75.0 mm/s (above `MAX_EXTRUSION_RATE`). | Bridge clamps rate to 50.0 mm/s. Log shows clamping. Motor speed does not exceed 50 mm/s equivalent. | Bridge log showing clamped value |
| 7 | Set `output_int_register_0 = 2` (RETRACT), rate = 10.0 mm/s. | Stepper reverses direction (retract). Bridge log shows mode=RETRACT. | Observe reversal; bridge log |
| 8 | Set `output_int_register_0 = 0` (OFF). | Stepper decelerates and stops. Bridge reports status=IDLE. | Bridge log |
| 9 | Set `output_bit_register_65 = True` (E-STOP) while motor is running at 25 mm/s. | Stepper stops immediately. Bridge sends `emergency_stop()` to Klipper. Status = ERROR. | Bridge log; observe immediate stop |
| 10 | Clear e-stop: set `output_bit_register_65 = False`, then `output_bit_register_64 = False` then `True` (re-enable). Send home command: `output_bit_register_66 = True`. | Bridge performs homing (position zero). Status returns to IDLE. System accepts new extrusion commands. | Bridge log; verify recovery |
| 11 | Disable extrusion: set `output_bit_register_64 = False`. | Stepper stops if running. Bridge reports ready=False. | Bridge log |

### 3.4 Pass/Fail Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| Stepper responds to all mode commands (extrude, retract, off) | Motor moves in correct direction for each mode | Motor does not move, moves in wrong direction, or does not stop |
| Rate clamping enforced | Rate above 50 mm/s is clamped; motor does not exceed configured max | Motor runs at unclamped rate |
| E-stop halts motor | Motor stops within 100 ms of e-stop command | Motor continues running after e-stop |
| Status registers update correctly | `input_int_register_0` reflects IDLE, RUNNING, ERROR, HOMING as appropriate | Status does not update or shows incorrect values |
| Ready and fault flags correct | Ready=True when system is operational; Fault=True during error conditions | Flags stuck or inverted |
| System recovers from e-stop | After clearing e-stop and re-enabling, system accepts new commands | System remains in error state after recovery procedure |

### 3.5 Data Recorded

- Bridge daemon log (full debug output for the session).
- Mainsail/Klipper status screenshots at each step.
- Teach pendant screenshots showing register values at key steps.
- Video of stepper motor (optional, for final presentation).
- Any anomalies observed (noise, vibration, missed steps).

---

## 4. TP-02: Latency Characterization

| Field | Value |
|-------|-------|
| **Test ID** | TP-02 |
| **Name** | Latency Characterization |
| **Objective** | Measure the actual end-to-end latency from UR30 register write to first stepper motor step pulse. Compare against the 20 ms requirement and the 8 ms typical prediction from `docs/latency_analysis.md`. |
| **Estimated Duration** | 90 minutes |

### 4.1 Equipment

| Item | Purpose |
|------|---------|
| UR30 + teach pendant | Generate timestamped RTDE commands |
| Pi (headless) | Run bridge daemon with timestamp instrumentation |
| SKR Pico + stepper motor | Generate step pulses |
| Oscilloscope (2+ channels, >= 1 MHz bandwidth) | Capture step pin transitions; trigger on command events |
| Oscilloscope probes (2x) | CH1: step pin (gpio14 on SKR Pico); CH2: trigger signal |
| Logic analyzer (optional, Saleae or similar) | Alternative to oscilloscope for digital signal capture; supports protocol decode |
| Jumper wires | Connect probe to step pin test point |
| Pi400 or laptop | SSH for log analysis |

### 4.2 Setup

1. Complete the pre-test checklist (Section 2.1).
2. **Instrument the bridge daemon for latency measurement.** Before running the bridge, enable the data logging enhancement (see `todo.md` -- "Add data logging"). The bridge should log a `time.monotonic()` timestamp each time it sends a Klipper `MANUAL_STEPPER MOVE` command. If the logging enhancement is not yet implemented, add a temporary `print(f"CMD_SENT,{time.monotonic()}")` line in `_set_extrusion()`.
3. **Connect oscilloscope CH1** to the SKR Pico step pin (gpio14, active on the E-axis stepper output header). Use a 10x probe. The step pin pulses HIGH for each microstep.
4. **Connect oscilloscope CH2** (trigger) to a GPIO pin on the Pi that the bridge daemon toggles when it sends a command. Alternatively, use the RTDE timestamp method described below.
5. Set oscilloscope trigger to CH2 rising edge (or CH1 rising edge if only measuring from first step pulse).
6. Set oscilloscope timebase to 5 ms/div (50 ms window).
7. Start the bridge daemon with `--log-level DEBUG`.
8. Prepare the latency test URScript program (see Section 4.3.1).

### 4.3 Measurement Methods

#### 4.3.1 Method A: RTDE Timestamp Comparison (Software-Only)

This method measures latency entirely in software using timestamps on both ends.

**URScript side:** Write a timestamp to `output_double_register_1` at the moment the extrusion command is issued:

```
# In the UR30 test program:
write_output_float_register(1, get_controller_time())  # timestamp at command issue
write_output_integer_register(0, 1)                     # mode = EXTRUDE
write_output_float_register(0, 10.0)                    # rate = 10.0 mm/s
```

**Bridge side:** Record `time.monotonic()` when the Klipper command is sent. The difference between the Klipper command timestamp and the UR30 controller timestamp (converted via RTDE clock synchronization) gives the command-to-bridge latency.

**Limitation:** This does not capture the Klipper-to-step-pulse latency. It measures segments 1-3 only (UR30 to bridge to klippy socket write).

#### 4.3.2 Method B: Oscilloscope on Step Pin (Hardware Measurement)

This method captures the full end-to-end latency including Klipper motion planning and MCU step execution.

**Procedure:**

1. Start with the stepper idle (mode = OFF, rate = 0).
2. Configure the oscilloscope in single-shot trigger mode, trigger on CH1 (step pin) rising edge.
3. Arm the oscilloscope.
4. On the UR30, send an extrusion command (mode = EXTRUDE, rate = 20 mm/s). Simultaneously, the bridge daemon logs the exact `time.monotonic()` of the Klipper command send.
5. The oscilloscope captures the first step pulse.
6. Measure the time between the trigger event (first step pulse) and correlate with the bridge daemon log timestamp.

**For a self-contained hardware measurement:** If a spare GPIO pin on the Pi is available, toggle it HIGH at the exact moment the bridge sends the Klipper command. Connect this GPIO to oscilloscope CH2. The time from CH2 rising edge to CH1 first rising edge is the Klipper-through-stepper latency (segments 4-6 in the latency analysis).

#### 4.3.3 Method C: Step-Change Response (Recommended Primary Method)

This method measures latency through repeated speed step-changes, which is the most operationally representative test.

**Procedure:**

1. Start the stepper at a steady rate of 10 mm/s (mode = EXTRUDE).
2. Wait for steady-state (5 seconds).
3. Command a step change to 30 mm/s.
4. The oscilloscope (set to trigger on frequency change) or logic analyzer captures the change in step pulse frequency.
5. The bridge daemon logs the exact timestamp of the speed change command.
6. Latency = time from bridge command to observed frequency change on the step pin.
7. Repeat 50 times with 2-second intervals between step changes (alternating between 10 and 30 mm/s).

### 4.4 Procedure (Full Test Sequence)

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Verify oscilloscope setup: probe on step pin, correct trigger configuration. Run stepper at 10 mm/s and confirm step pulses are visible on scope. | Clean square wave pulses visible at expected frequency. | Scope screenshot of steady-state waveform |
| 2 | **Cold-start latency (Method B):** With stepper idle, arm scope in single-shot mode. Command extrusion at 20 mm/s from UR30. | Scope captures first step pulse. | Scope capture with time cursor measurement; bridge daemon timestamp |
| 3 | Repeat cold-start measurement 10 times (stop stepper, wait 3 seconds, re-command). | 10 latency measurements. | Tabulate all 10 values |
| 4 | **Step-change latency (Method C):** Run stepper at 10 mm/s steady-state. Execute 50 speed step-changes (10 <-> 30 mm/s) at 2-second intervals. | For each change, record latency from command to observed frequency change. | CSV file: `[trial, command_timestamp, response_timestamp, latency_ms]` |
| 5 | **Segment-by-segment (Method A):** Log RTDE round-trip times and bridge processing times from the bridge daemon log over 1000 cycles. | Per-segment latency breakdown. | Bridge log parsed into CSV |
| 6 | **High-rate streaming:** Run stepper at 50 mm/s with small speed perturbations (+/- 2 mm/s) at 125 Hz (every bridge cycle). Monitor for any missed commands or jitter. | Step frequency tracks commanded speed without dropout. | Scope capture; bridge log |
| 7 | Collect all data and compute statistics. | Statistical summary available. | See Section 4.5 |

### 4.5 Statistical Analysis

Compute the following from the 50+ measurements collected in Step 4:

| Statistic | Formula | Acceptance |
|-----------|---------|------------|
| Mean latency | Sum(latency_i) / N | Report value; compare to 8 ms prediction |
| Standard deviation | sqrt(Sum((latency_i - mean)^2) / (N-1)) | Report value |
| Minimum | min(latency_i) | Report value |
| Maximum | max(latency_i) | Must be < 50 ms |
| 95th percentile | Sort ascending, value at index ceil(0.95 * N) | Must be < 20 ms |
| 99th percentile | Value at index ceil(0.99 * N) | Report value |
| Histogram | Bin latencies in 1 ms bins from 0 to 50 ms | Generate figure for report |

### 4.6 Pass/Fail Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| 95th percentile latency < 20 ms | Measured P95 is below 20 ms | P95 exceeds 20 ms |
| Mean latency within prediction range | Mean is between 3 ms and 13 ms (analysis range) | Mean outside predicted range by more than 2x |
| No latency outliers > 100 ms | All measurements below 100 ms | Any single measurement exceeds 100 ms |
| Cold-start latency characterized | 10 cold-start measurements recorded | Fewer than 10 measurements or data not recorded |

### 4.7 Data Recorded

- Oscilloscope screen captures (PNG) for representative latency measurements.
- CSV file of all latency measurements: `[trial, type, command_timestamp_ms, response_timestamp_ms, latency_ms]`.
- Bridge daemon log with timestamps for all commands sent.
- Per-segment latency breakdown (RTDE, bridge processing, Klipper, USB, MCU).
- Histogram figure (generated in Python/MATLAB for the final report).
- Summary statistics table.

---

## 5. TP-03: Accuracy Test

| Field | Value |
|-------|-------|
| **Test ID** | TP-03 |
| **Name** | Speed Accuracy and Transient Response Test |
| **Objective** | Quantify the accuracy of the stepper motor speed relative to the commanded speed across the operating range. Measure steady-state error and transient response to step changes in speed. |
| **Estimated Duration** | 60 minutes |

### 5.1 Equipment

| Item | Purpose |
|------|---------|
| UR30 + teach pendant | Issue speed setpoint commands |
| Pi (headless) | Run bridge daemon |
| SKR Pico + stepper motor | Actuator under test |
| Oscilloscope or logic analyzer | Measure step pulse frequency to derive actual motor speed |
| Frequency counter (optional) | More precise frequency measurement than oscilloscope |
| Pi400 or laptop | SSH for log monitoring |

### 5.2 Speed-to-Frequency Relationship

The relationship between commanded speed (mm/s) and step pulse frequency depends on the Klipper configuration:

```
step_frequency (Hz) = speed (mm/s) / rotation_distance (mm/rev) * microsteps_per_rev
                    = speed / 40.0 * 3200
                    = speed * 80
```

| Speed (mm/s) | Expected Step Frequency (Hz) |
|---------------|------------------------------|
| 5.0 | 400 |
| 10.0 | 800 |
| 20.0 | 1,600 |
| 30.0 | 2,400 |
| 50.0 | 4,000 |

Note: `rotation_distance = 40` and `microsteps = 16` from `src/klipper/printer.cfg`. Adjust this table if the configuration changes after pump characterization.

### 5.3 Setup

1. Complete the pre-test checklist (Section 2.1).
2. Connect oscilloscope CH1 to the step pin (gpio14).
3. Set oscilloscope to frequency measurement mode (auto-measure) or use a frequency counter.
4. Start the bridge daemon with `--log-level DEBUG`.
5. Prepare a test URScript program that commands specific speed setpoints in sequence.

### 5.4 Procedure: Steady-State Accuracy

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Command extrusion at **5.0 mm/s**. Wait 10 seconds for steady state. | Step frequency stabilizes. | Measured frequency (Hz); computed actual speed (mm/s) |
| 2 | Record step frequency over a 5-second window (measure 5 consecutive 1-second frequency counts). | Five frequency readings. | Mean, std dev of 5 readings |
| 3 | Command extrusion at **10.0 mm/s**. Wait 10 seconds. Repeat frequency measurement. | Step frequency doubles from Step 1. | Same as above |
| 4 | Command extrusion at **20.0 mm/s**. Wait 10 seconds. Measure. | Frequency consistent with 20 mm/s. | Same |
| 5 | Command extrusion at **30.0 mm/s**. Wait 10 seconds. Measure. | Frequency consistent with 30 mm/s. | Same |
| 6 | Command extrusion at **50.0 mm/s** (maximum). Wait 10 seconds. Measure. | Frequency consistent with 50 mm/s. No stall. | Same |
| 7 | Repeat steps 1-6 in **retract** direction (mode = 2). | Same frequencies, opposite rotation. | Same |
| 8 | Compute steady-state error for each setpoint: `error = (actual_speed - commanded_speed) / commanded_speed * 100%`. | Tabulate errors. | Error table |

### 5.5 Procedure: Transient Response

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 9 | Run at 10 mm/s steady-state. Command step change to **30 mm/s**. Capture oscilloscope waveform showing frequency transition. | Smooth acceleration from 10 to 30 mm/s. | Scope capture with time cursors; rise time measurement |
| 10 | Measure **rise time** (time from command to reaching 90% of target speed) from the oscilloscope capture. | Rise time consistent with configured acceleration (200 mm/s^2). Expected: (30-10)/200 = 0.1 s = 100 ms for the speed ramp, plus command latency. | Rise time in ms |
| 11 | Command step change from **30 mm/s down to 10 mm/s**. Capture waveform. | Smooth deceleration. | Scope capture; fall time |
| 12 | Command step change from **0 to 50 mm/s** (full-range start). Capture. | Motor accelerates from stop to 50 mm/s. | Scope capture; time to target speed |
| 13 | Command step change from **50 mm/s to 0** (full-range stop via mode = OFF). Capture. | Motor decelerates to stop. No overshoot (stepper motor should not coast). | Scope capture; stopping time |
| 14 | Command rapid alternating speeds: 10 -> 30 -> 10 -> 30 mm/s at 1-second intervals for 10 cycles. | Motor tracks all transitions without stalling or losing steps. | Scope capture; bridge log |

### 5.6 Pass/Fail Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| Steady-state speed error < 2% at all setpoints | All setpoints within 2% of commanded speed | Any setpoint exceeds 2% error |
| Steady-state speed jitter < 1% (std dev / mean) | Coefficient of variation < 0.01 at each setpoint | CV exceeds 0.01 |
| No stall at any commanded speed up to 50 mm/s | Motor runs continuously at all speeds | Motor stalls or skips steps at any speed |
| Transient response: no overshoot | Speed does not exceed target during acceleration | Measured overshoot > 5% of target |
| Motor tracks rapid speed changes without stalling | 10 alternating cycles completed without stall | Stall or step loss during rapid changes |

### 5.7 Data Recorded

- Table: for each speed setpoint, 5 frequency measurements, mean, std dev, computed actual speed, percent error.
- Oscilloscope captures of transient responses (step up, step down, start, stop).
- Rise time and fall time measurements.
- Bridge daemon log for the session.
- Any anomalies (audible resonance at certain speeds, excessive vibration, heating).

---

## 6. TP-04: Fault Handling Test

| Field | Value |
|-------|-------|
| **Test ID** | TP-04 |
| **Name** | Fault Handling and Recovery Test |
| **Objective** | Verify that the system detects and responds safely to the failure modes identified in the problem analysis (F1, F2, F4, F5). For each fault, verify that the stepper stops, an error is reported to the UR30, and the system can recover. |
| **Estimated Duration** | 75 minutes |

### 6.1 General Fault Test Protocol

For each sub-test (TP-04a through TP-04d), the following protocol applies:

1. Start the system in a known-good state: stepper running at 10 mm/s in extrude mode.
2. Verify bridge status is RUNNING, ready=True, fault=False on the UR30 teach pendant.
3. Inject the fault.
4. Observe and record the system response (timing, register values, stepper behavior).
5. Attempt the defined recovery procedure.
6. Verify the system returns to normal operation.
7. Record all data.

---

### 6.2 TP-04a: RTDE Disconnect (Failure Mode F1)

| Field | Value |
|-------|-------|
| **Sub-Test ID** | TP-04a |
| **Failure Mode** | F1 -- Loss of RTDE connection |
| **Injection Method** | Physically disconnect the Ethernet cable between the gigabit switch and the Pi |
| **Estimated Duration** | 15 minutes |

#### Expected Behavior

Per the bridge daemon design (`src/bridge/bridge_daemon.py`, `_tick()` method): when `read_commands()` raises `ConnectionError`, the bridge sets `status = STATUS_ERROR`, `error_code = ERR_COMMS_LOST`, `fault = True`, calls `_try_emergency_stop()` (disables stepper), and enters the reconnection loop (`_connect_all()`).

The stepper should stop within one bridge loop cycle (8 ms at 125 Hz) of the connection loss being detected.

#### Procedure

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Start stepper at 10 mm/s (extrude mode). Confirm RUNNING status on teach pendant. | System running normally. | Bridge log; teach pendant register values |
| 2 | **Disconnect the Ethernet cable** from the Pi's Ethernet port. Start a stopwatch. | Physical cable removal. | Timestamp of disconnection |
| 3 | Observe the stepper motor. | Stepper should stop within approximately 1 second (bridge detects lost connection and disables stepper). | Time from cable pull to stepper stop (visual/audible) |
| 4 | Check bridge daemon log on Pi (via Pi400 SSH or serial console, since Ethernet is down). | Log shows: "Connection lost", status=ERROR, error_code=ERR_COMMS_LOST, fault=True. Reconnection attempts logged every 2 seconds (`RECONNECT_DELAY`). | Bridge log screenshot |
| 5 | Wait 30 seconds with cable disconnected. Confirm stepper remains stopped and bridge continues attempting reconnection. | Stepper stays stopped. Bridge log shows repeated reconnection attempts. | Bridge log |
| 6 | **Reconnect the Ethernet cable.** | Bridge detects reconnection (RTDE `connect()` succeeds). Log shows "RTDE connected". | Timestamp of reconnection; bridge log |
| 7 | On the UR30, clear the fault: set `output_bit_register_64 = False` then `True` (re-enable). | Bridge resumes normal operation. Status returns to IDLE, fault=False, ready=True. | Teach pendant register values |
| 8 | Command extrusion at 10 mm/s. | Stepper resumes normal operation. | Visual confirmation; bridge log |
| 9 | Repeat the entire sequence once more to confirm consistency. | Same behavior on second trial. | Second set of data |

#### Pass/Fail Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| Stepper stops after RTDE disconnect | Motor stops within 2 seconds of cable pull | Motor continues running indefinitely |
| Error code reported | `input_int_register_1 = 1` (ERR_COMMS_LOST) after reconnection | Error code not set or wrong value |
| Fault flag set | `input_bit_register_65 = True` (fault) | Fault flag not set |
| Automatic reconnection | Bridge reconnects when cable is restored | Bridge crashes or does not reconnect |
| Full recovery | System accepts commands after recovery procedure | System remains in error state |

---

### 6.3 TP-04b: Stepper Stall (Failure Mode F2)

| Field | Value |
|-------|-------|
| **Sub-Test ID** | TP-04b |
| **Failure Mode** | F2 -- Stepper motor stall |
| **Injection Method** | Manually block the motor shaft with a soft grip (wear gloves) |
| **Estimated Duration** | 15 minutes |

#### Expected Behavior

Without StallGuard configured (MVP scope), the stepper is open-loop and will not detect a stall. The motor will skip steps, but the bridge daemon will not report an error unless StallGuard is enabled (stretch goal). This test documents the baseline behavior and determines whether StallGuard should be pursued.

If StallGuard is enabled: the TMC2209 DIAG pin triggers, Klipper detects the stall, and the bridge daemon reports `error_code = ERR_STALL (2)`.

#### Procedure

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Start stepper at 10 mm/s. Confirm normal operation. | Motor running smoothly. | Bridge log |
| 2 | **Gradually increase manual resistance** on the motor shaft by gripping it (wear gloves). | Motor begins to struggle; audible change in sound (chopping noise). | Note at what resistance level behavior changes |
| 3 | **Fully block the motor shaft** so it cannot rotate. | Motor stalls. Audible buzzing/humming from energized coils. Bridge daemon continues reporting status=RUNNING (open-loop; it does not know the motor is stalled). | Record: does bridge detect stall? What status is reported? |
| 4 | Check TMC2209 driver status via Klipper: `DUMP_TMC STEPPER=manual_stepper pump` in Mainsail console. | TMC2209 `drv_status` register shows stall/overtemperature flags if applicable. | Screenshot of TMC2209 status |
| 5 | **Release the motor shaft.** | Motor resumes rotation (at the wrong position, since steps were lost). | Observe motor behavior |
| 6 | Stop extrusion (mode = OFF). Set position to zero (home command). Resume extrusion. | System operates normally from new position reference. | Bridge log |
| 7 | If StallGuard is configured: repeat steps 1-6 with `driver_SGTHRS` set in `printer.cfg`. | On stall, Klipper reports stall event. Bridge daemon reports `error_code = 2` (ERR_STALL), `fault = True`. | Bridge log; Klipper log |
| 8 | Record motor temperature after stall test (touch or IR thermometer). | Motor should not be excessively hot (< 60 C after brief stall). | Motor temperature |

#### Pass/Fail Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| Motor does not sustain damage from brief stall | Motor operates normally after stall release | Motor damaged, driver damaged, or fuse blown |
| TMC2209 does not enter thermal shutdown during brief stall | Driver continues operating or recovers from thermal shutdown | Driver permanently faulted |
| System recovers after stall | Commands accepted normally after clearing stall condition | System unresponsive after stall |
| (If StallGuard enabled) Stall detected and reported | error_code = 2, fault = True within 1 second of stall | Stall not detected |

#### Data Recorded

- Bridge daemon log.
- TMC2209 `drv_status` dump before, during, and after stall.
- Motor and driver temperature before and after.
- Whether StallGuard was enabled and its behavior.
- Subjective notes on motor sound and vibration during stall.

---

### 6.4 TP-04c: Klipper Crash (Failure Mode F4)

| Field | Value |
|-------|-------|
| **Sub-Test ID** | TP-04c |
| **Failure Mode** | F4 -- Klipper host software crash |
| **Injection Method** | Kill the klippy process: `sudo systemctl stop klipper` or `sudo kill -9 $(pidof klippy)` |
| **Estimated Duration** | 20 minutes |

#### Expected Behavior

When klippy stops, two things happen:
1. The SKR Pico MCU detects host communication timeout and disables all steppers (Klipper firmware safety feature).
2. The bridge daemon's next Klipper command fails (Unix socket write raises an exception), triggering `ConnectionError` handling: status = ERROR, error_code = ERR_COMMS_LOST, fault = True.

#### Procedure

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Start stepper at 20 mm/s. Confirm normal operation. | Motor running. Bridge status = RUNNING. | Bridge log |
| 2 | From a Pi SSH session, **kill the klippy process**: `sudo kill -9 $(pidof klippy)` | klippy process terminates. | Timestamp of kill command |
| 3 | Observe stepper motor. | Motor stops. The SKR Pico MCU enters shutdown state when it detects host timeout (typically within 1-5 seconds). | Time from kill to motor stop |
| 4 | Check bridge daemon log. | Bridge detects lost klippy connection. Log shows Klipper connection error, status=ERROR, attempts to reconnect. | Bridge log |
| 5 | Check UR30 teach pendant. | `input_int_register_0` = 2 (ERROR), `input_int_register_1` = 1 (comms_lost), `input_bit_register_65` = True (fault). | Teach pendant register values |
| 6 | **Restart Klipper**: `sudo systemctl start klipper`. Wait for Klipper to report "Ready". | Klipper restarts and reconnects to SKR Pico. | Klipper log |
| 7 | Observe bridge daemon log. | Bridge daemon detects klippy is back (reconnection succeeds). Log shows "Klipper connected, state: Ready". | Bridge log |
| 8 | On UR30, clear fault and re-enable. Command extrusion at 10 mm/s. | System resumes normal operation. | Bridge log; teach pendant |
| 9 | Repeat with `sudo systemctl stop klipper` (graceful stop instead of SIGKILL). | Similar behavior but potentially faster shutdown detection. | Compare graceful vs. forced kill behavior |

#### Pass/Fail Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| Stepper stops when klippy crashes | Motor stops within 5 seconds (MCU host timeout) | Motor continues running indefinitely |
| Bridge detects Klipper loss | Error state reported within 2 bridge cycles (16 ms) of next command attempt | Bridge does not detect the failure |
| Error reported to UR30 | Error code and fault flag set on RTDE input registers | UR30 not informed of fault |
| Automatic recovery on Klipper restart | Bridge reconnects to klippy without manual intervention | Bridge requires manual restart |
| Full recovery | System accepts commands after recovery | System remains in error state |

---

### 6.5 TP-04d: USB Disconnect (Failure Mode F5)

| Field | Value |
|-------|-------|
| **Sub-Test ID** | TP-04d |
| **Failure Mode** | F5 -- USB serial disconnect (Pi to SKR Pico) |
| **Injection Method** | Physically disconnect the USB cable between the Pi and the SKR Pico |
| **Estimated Duration** | 20 minutes |

#### Expected Behavior

When the USB cable is disconnected:
1. Klipper loses MCU communication and enters shutdown state, logging "Lost communication with MCU 'mcu'".
2. The bridge daemon's next Klipper command fails, triggering the same error handling as TP-04c.
3. The stepper stops immediately (no power to driver from MCU, and driver enable pin floats/deasserts).

#### Procedure

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Start stepper at 15 mm/s. Confirm normal operation. | Motor running normally. | Bridge log |
| 2 | **Disconnect the USB cable** between the Pi and the SKR Pico. | Physical disconnection. | Timestamp |
| 3 | Observe stepper motor. | Motor stops immediately (driver loses enable signal). | Time from USB pull to motor stop |
| 4 | Check Klipper log (`/var/log/klippy.log` or via Mainsail). | Klipper reports "Lost communication with MCU 'mcu'", enters shutdown state. | Klipper log excerpt |
| 5 | Check bridge daemon log. | Bridge detects Klipper error (shutdown state). Status = ERROR, fault = True. | Bridge log |
| 6 | Check UR30 teach pendant registers. | Error code and fault flag set. | Register values |
| 7 | **Reconnect the USB cable.** | SKR Pico re-enumerates on USB bus. | dmesg output showing USB re-enumeration |
| 8 | Restart Klipper: `sudo systemctl restart klipper` (Klipper does not auto-recover from MCU loss). | Klipper reconnects to SKR Pico, reports "Ready". | Klipper log |
| 9 | Wait for bridge daemon to detect Klipper recovery. Clear fault on UR30 and re-enable. | System resumes normal operation. | Bridge log; teach pendant |
| 10 | Command extrusion at 15 mm/s. | Stepper runs normally. | Confirmation |

#### Pass/Fail Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| Stepper stops on USB disconnect | Motor stops immediately | Motor continues (should be impossible without USB power/signal) |
| Klipper enters shutdown | Klipper log shows MCU communication loss | Klipper does not detect the failure |
| Bridge reports error to UR30 | Error code and fault flag set | UR30 not informed |
| Recovery after USB reconnect + Klipper restart | System fully operational after recovery | System requires full power cycle to recover |

---

## 7. TP-05: Endurance Test

| Field | Value |
|-------|-------|
| **Test ID** | TP-05 |
| **Name** | Endurance / Extended Continuous Run Test |
| **Objective** | Verify that the system operates reliably during an extended continuous run without thermal faults, communication errors, position drift, or degraded performance. |
| **Estimated Duration** | 90 minutes (60-minute run + 30 minutes setup/analysis) |

### 7.1 Equipment

| Item | Purpose |
|------|---------|
| UR30 + teach pendant | Continuous extrusion commands |
| Pi (headless) | Run bridge daemon with data logging |
| SKR Pico + stepper motor | Actuator under test |
| IR thermometer or thermocouple | Measure motor case temperature and TMC2209 temperature |
| Pi400 or laptop | Monitoring via SSH and Mainsail |
| Multimeter with clamp (optional) | Measure 24V rail current draw |
| Timer/clock | Track test duration |

### 7.2 Thermal Monitoring Points

| Component | Measurement Point | Method | Alarm Threshold |
|-----------|-------------------|--------|-----------------|
| TMC2209 driver | IC package or heatsink surface on SKR Pico (E-driver position) | IR thermometer, every 10 minutes | > 100 C (TMC2209 thermal shutdown at ~150 C) |
| Stepper motor case | Motor body surface | IR thermometer, every 10 minutes | > 80 C (typical NEMA 17 limit ~80-100 C) |
| Pi CPU | `vcgencmd measure_temp` via SSH | Software readout, every 10 minutes | > 80 C (throttling threshold) |
| SKR Pico RP2040 | Board surface near RP2040 chip | IR thermometer, every 10 minutes | > 70 C |
| Ambient | Lab room temperature | Thermometer at start and end | Record for reference |

### 7.3 Setup

1. Complete the pre-test checklist (Section 2.1).
2. Start the bridge daemon with data logging enabled (if implemented): `python -m bridge --host <UR30_IP> --log-level INFO`. If CSV logging is not yet implemented, run with `--log-level DEBUG` and parse logs post-test.
3. Prepare a URScript test program that commands continuous extrusion at a representative operating speed (20 mm/s) with periodic speed variations to simulate real deposition:
   - 0:00 - 2:00: Ramp from 0 to 20 mm/s, hold at 20 mm/s
   - 2:00 - 50:00: Alternate between 15 and 25 mm/s every 30 seconds (simulating path corners)
   - 50:00 - 55:00: Run at 50 mm/s (maximum rate stress test)
   - 55:00 - 60:00: Return to 20 mm/s, then ramp to 0 and stop
4. Prepare a data recording sheet (see Appendix B) for temperature readings.

### 7.4 Procedure

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Record initial temperatures of all monitoring points. Record ambient temperature. | Baseline temperatures. | Temperature data sheet, row t=0 |
| 2 | Start the URScript endurance test program. Start a timer. | Motor begins extrusion at programmed profile. Bridge status = RUNNING. | Start timestamp |
| 3 | At **t = 10 min**, measure and record all temperatures. Check bridge daemon log for any warnings or errors. Check Mainsail for Klipper status. | No warnings. Temperatures within limits. | Temperature data sheet, row t=10 |
| 4 | At **t = 20 min**, repeat temperature and log check. | Same. | Row t=20 |
| 5 | At **t = 30 min**, repeat. Additionally, check step frequency with oscilloscope to confirm no speed drift. | Frequency matches commanded speed. No drift. | Row t=30; frequency measurement |
| 6 | At **t = 40 min**, repeat temperature and log check. | Same. | Row t=40 |
| 7 | At **t = 50 min**, the program transitions to 50 mm/s. Monitor temperatures closely (max current draw). | Motor and driver temperatures may rise. Check they remain below alarm thresholds. | Row t=50 |
| 8 | At **t = 55 min**, program returns to 20 mm/s. Temperatures should stabilize or decrease. | Temperatures plateau or decrease. | Row t=55 |
| 9 | At **t = 60 min**, the program stops extrusion. Record final temperatures. | Motor stops. All temperatures below alarm thresholds. | Row t=60 (final) |
| 10 | Immediately after stopping, measure step frequency at 20 mm/s (restart briefly for 10 seconds) and compare to the initial measurement. | Frequency within 1% of initial measurement (no thermal drift in driver). | Frequency comparison |
| 11 | Parse bridge daemon log for: total command count, any error/warning messages, maximum loop time, average loop time. | Zero errors, zero warnings (ideally). Loop times consistently < LOOP_PERIOD (8 ms). | Log statistics |
| 12 | Check RTDE communication statistics: any dropped packets or reconnection events. | Zero reconnections, zero dropped packets. | Bridge log analysis |

### 7.5 Pass/Fail Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| 60-minute continuous run completes | No interruptions, no faults, no manual intervention needed | Test aborted due to thermal fault, communication error, or stall |
| TMC2209 temperature < 100 C throughout | All measurements below 100 C | Any measurement exceeds 100 C |
| Motor temperature < 80 C throughout | All measurements below 80 C | Any measurement exceeds 80 C |
| Pi CPU temperature < 80 C | No thermal throttling | CPU throttled or exceeded 80 C |
| Zero communication errors | Bridge log shows no errors or reconnections during 60-minute run | Any communication error logged |
| No speed drift | Post-test frequency within 1% of initial measurement at same setpoint | Drift exceeds 1% |
| 24V current draw within budget | Measured current stays below 2 A continuous (if measured) | Current exceeds 2 A sustained |

### 7.6 Data Recorded

- Temperature data sheet: all monitoring points at 10-minute intervals (7 readings per point).
- Temperature vs. time plot (for final report figure).
- Bridge daemon log (full session).
- Log statistics: total commands sent, error count, warning count, max/mean loop time.
- Step frequency measurement at start and end.
- 24V current measurement (if available).
- Any observed anomalies (sound, vibration, smell).

---

## 8. Data Collection Plan

### 8.1 Data Summary Across All Tests

| Data Item | Collected In | Format | Purpose in Final Report |
|-----------|-------------|--------|------------------------|
| End-to-end latency measurements (N >= 50) | TP-02 | CSV | Latency histogram figure; statistical summary table |
| Per-segment latency breakdown | TP-02 | Table | Validate analysis predictions; component-level figure |
| Cold-start vs. steady-state latency | TP-02 | Table | Discuss Klipper lookahead buffer effect |
| Steady-state speed accuracy (5 setpoints) | TP-03 | Table | Accuracy table in report |
| Transient response oscilloscope captures | TP-03 | PNG | Step response figure |
| Rise time / fall time measurements | TP-03 | Table | Discuss dynamic performance |
| Fault injection response times | TP-04 | Table | Reliability/safety discussion |
| Fault recovery success/failure | TP-04 | Table | Design validation |
| Temperature vs. time (60-min endurance) | TP-05 | CSV/Table | Thermal profile figure |
| Communication reliability (error count over 60 min) | TP-05 | Scalar | Reliability claim |
| Oscilloscope captures (various) | TP-01 through TP-05 | PNG | Report figures |
| Bridge daemon logs (all tests) | All | Text/CSV | Evidence of system behavior |

### 8.2 Figures Planned for Final Report

| Figure # | Title | Source Test | Type |
|----------|-------|------------|------|
| 1 | System block diagram with data flow | N/A (design) | Block diagram |
| 2 | Latency histogram (end-to-end, N >= 50) | TP-02 | Histogram |
| 3 | Latency breakdown by segment (stacked bar or waterfall) | TP-02 | Bar chart |
| 4 | Speed accuracy: commanded vs. measured (5 setpoints) | TP-03 | Scatter/bar chart |
| 5 | Transient response: step change oscilloscope capture | TP-03 | Scope screenshot |
| 6 | Temperature vs. time during endurance test | TP-05 | Line plot |
| 7 | Photograph of assembled system | N/A (build) | Photo |
| 8 | Circuit schematic | N/A (design) | Schematic |

### 8.3 Tables Planned for Final Report

| Table # | Title | Source |
|---------|-------|--------|
| 1 | System specifications (final measured values) | All tests |
| 2 | Latency statistics (mean, std dev, P95, max) | TP-02 |
| 3 | Predicted vs. measured latency by segment | TP-02 + latency analysis |
| 4 | Steady-state speed accuracy at each setpoint | TP-03 |
| 5 | Fault injection results summary | TP-04 |
| 6 | Endurance test thermal data | TP-05 |
| 7 | Bill of materials | Design phase |
| 8 | RTDE register allocation | Design phase |

### 8.4 Mapping to Course Topics

The final report must relate the project to ME 472 course topics. The test data supports the following connections:

| Course Topic | Project Connection | Supporting Data |
|-------------|-------------------|-----------------|
| **Control systems** | The bridge daemon implements an open-loop speed control system. Latency analysis models the plant delay. Steady-state error and transient response characterize the control performance. If StallGuard is implemented, it closes the loop with torque feedback. | TP-02 (latency = plant delay), TP-03 (steady-state error, transient response) |
| **Actuators** | Stepper motor driven by TMC2209 chopper driver. Microstepping for resolution. Torque-speed characteristics (no-stall region demonstrated in TP-03). Thermal limits characterized in TP-05. | TP-03 (speed range, stall test), TP-04b (stall behavior), TP-05 (thermal) |
| **Sensors / feedback** | RTDE registers as "virtual sensors" providing robot state to the extrusion controller. TMC2209 StallGuard as a stall sensor (stretch goal). Temperature monitoring. | TP-02 (RTDE data flow), TP-04b (StallGuard) |
| **Microcontrollers** | RP2040 on SKR Pico executes Klipper firmware: hardware timer ISRs for step pulse generation, UART for TMC2209 communication, USB for host protocol. | TP-02 (MCU step timing precision), TP-03 (step frequency accuracy) |
| **System models** | The latency analysis (`docs/latency_analysis.md`) is a system model predicting end-to-end delay. Phase 4 tests validate this model against measured data. The extrusion error model (position error = speed change x latency) is validated by combining TP-02 and TP-03 data. | TP-02 (model validation), TP-03 (error model input) |
| **Communication** | RTDE protocol (TCP/IP, 500 Hz), Klipper protocol (Unix socket, JSON + ETX), USB serial (Klipper MCU protocol). Latency measured across each segment. Fault handling for lost communication. | TP-02 (per-segment latency), TP-04a (RTDE loss), TP-04d (USB loss) |
| **Circuits** | 24V to 5.1V buck conversion, TMC2209 H-bridge chopper drive, RP2040 digital I/O. Power budget validated during endurance test. | TP-05 (power draw), design documentation |

---

## 9. Test Schedule

All tests target completion by **March 31, 2026** to allow time for report writing (due April 23).

| Week | Dates | Activity |
|------|-------|----------|
| Week 12 | Mar 23 - 27 | TP-01 (functional), TP-03 (accuracy) -- these require only basic instrumentation |
| Week 12 | Mar 27 - 28 | TP-02 (latency) -- requires oscilloscope setup and multiple measurement runs |
| Week 13 | Mar 30 - 31 | TP-04 (fault handling), TP-05 (endurance) |
| Week 13 | Mar 31 | Data analysis, statistics computation, figure generation |
| Weeks 14-15 | Apr 1 - 22 | Report writing incorporating test results |
| Apr 23 | | Final report submission |
| Apr 24 | | Oral presentation and prototype demonstration |

### Time Contingency

If hardware issues delay Phase 3 integration, the test schedule can be compressed:

- TP-01 and TP-03 can be combined into one session (90 minutes).
- TP-02 can be shortened by reducing the number of latency measurements from 50 to 30 (still statistically meaningful).
- TP-04 sub-tests can run back-to-back (75 minutes total).
- TP-05 can be shortened from 60 minutes to 30 minutes if thermal steady-state is reached earlier.
- Minimum viable test campaign: 1 full day (8 hours) to execute all tests at reduced scope.

---

## Appendix A: Equipment List

| Item | Quantity | Lab / Bring | Notes |
|------|----------|-------------|-------|
| UR30 Robot + controller | 1 | Lab | ME 472 lab equipment |
| UR30 teach pendant | 1 | Lab | Included with UR30 |
| Raspberry Pi (headless, Klipper host) | 1 | Team | Running Klipper + bridge daemon |
| Raspberry Pi 400 (HMI) | 1 | Team | Optional; for SSH and Mainsail monitoring |
| SKR Pico V1.0 | 1 | Team | Flashed with Klipper firmware |
| Stepper motor + pump | 1 | Provided | Specs TBD |
| Gigabit Ethernet switch | 1 | Team | For UR30 <-> Pi connection |
| Ethernet cables (Cat5e/Cat6) | 2-3 | Team | UR30-switch, switch-Pi, switch-Pi400 |
| USB cable (Pi to SKR Pico) | 1 | Team | USB-A to micro-USB |
| 24V power supply / UR30 power block | 1 | Lab | Connected during system assembly |
| Oscilloscope (2+ channel, >= 1 MHz) | 1 | Lab | ME 472 lab equipment or ECE lab |
| Oscilloscope probes (10x) | 2 | Lab | For step pin and trigger |
| IR thermometer | 1 | Lab / borrow | For temperature measurements |
| Multimeter | 1 | Lab | For voltage/current checks |
| Jumper wires / probe hooks | Several | Team | For connecting scope probes to PCB |
| Stopwatch / timer | 1 | Any | Phone timer is sufficient |
| Laptop / workstation | 1 | Team | For data analysis (Python/MATLAB) |

---

## Appendix B: Data Sheet Templates

### B.1 Endurance Test Temperature Log (TP-05)

| Time (min) | TMC2209 (C) | Motor (C) | Pi CPU (C) | RP2040 (C) | Ambient (C) | Speed (mm/s) | Notes |
|------------|-------------|-----------|------------|------------|--------------|--------------|-------|
| 0 | | | | | | 0 (start) | |
| 10 | | | | | | 20 | |
| 20 | | | | | | 20 | |
| 30 | | | | | | 20 | |
| 40 | | | | | | 20 | |
| 50 | | | | | | 50 | |
| 55 | | | | | | 20 | |
| 60 | | | | | | 0 (end) | |

### B.2 Latency Measurement Log (TP-02)

| Trial | Type | Commanded Speed Change (mm/s) | Command Timestamp (ms) | Response Timestamp (ms) | Latency (ms) | Notes |
|-------|------|-------------------------------|------------------------|-------------------------|---------------|-------|
| 1 | cold-start | 0 -> 20 | | | | |
| 2 | cold-start | 0 -> 20 | | | | |
| ... | ... | ... | | | | |
| 11 | step-change | 10 -> 30 | | | | |
| 12 | step-change | 30 -> 10 | | | | |
| ... | ... | ... | | | | |

### B.3 Speed Accuracy Log (TP-03)

| Setpoint (mm/s) | Direction | Freq Reading 1 (Hz) | Freq 2 | Freq 3 | Freq 4 | Freq 5 | Mean Freq (Hz) | Actual Speed (mm/s) | Error (%) |
|-----------------|-----------|---------------------|---------|---------|---------|---------|-----------------|---------------------|-----------|
| 5.0 | Extrude | | | | | | | | |
| 10.0 | Extrude | | | | | | | | |
| 20.0 | Extrude | | | | | | | | |
| 30.0 | Extrude | | | | | | | | |
| 50.0 | Extrude | | | | | | | | |
| 5.0 | Retract | | | | | | | | |
| 10.0 | Retract | | | | | | | | |
| 20.0 | Retract | | | | | | | | |
| 30.0 | Retract | | | | | | | | |
| 50.0 | Retract | | | | | | | | |

### B.4 Fault Handling Summary (TP-04)

| Sub-Test | Fault Injected | Stepper Stopped? | Time to Stop (s) | Error Code Reported | Fault Flag Set | Recovery Successful | Notes |
|----------|---------------|------------------|-------------------|---------------------|----------------|---------------------|-------|
| TP-04a | RTDE disconnect | | | | | | |
| TP-04a (repeat) | RTDE disconnect | | | | | | |
| TP-04b | Stepper stall | | | | | | |
| TP-04c (SIGKILL) | Klipper crash | | | | | | |
| TP-04c (SIGTERM) | Klipper stop | | | | | | |
| TP-04d | USB disconnect | | | | | | |

---

*This document was prepared as part of the W26 Cobot Axis project (ME 472, Winter 2026). Test procedures will be executed during Phase 4 (Weeks 12-13, target completion March 31, 2026). Results will be incorporated into the final report (due April 23, 2026).*
