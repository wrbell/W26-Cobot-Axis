# Hardware-In-The-Loop (HITL) Integration Plan

**W26 Cobot Axis -- ME472 Mechatronics Capstone**
**Author:** Willem (Software/EE)
**Date:** 2026-02-24
**Status:** Pre-hardware (all software mock-tested, 479 tests passing, 100% coverage)

---

## Table of Contents

1. [Overview and Scope](#1-overview-and-scope)
2. [Integration Stage Amendments](#2-integration-stage-amendments)
3. [TP-06: StallGuard Validation Test](#3-tp-06-stallguard-validation-test)
4. [Updated TP-04b Note](#4-updated-tp-04b-note)
5. [Integration Timeline](#5-integration-timeline)
6. [Dev Bench Setup — URSim on Windows](#6-dev-bench-setup--ursim-on-windows)
7. [Deploy Workflow](#7-deploy-workflow)
8. [Risk and Fallback](#8-risk-and-fallback)

---

## 1. Overview and Scope

### Purpose

All bridge daemon, Klipper status, and RTDE client software has been written and tested against mocks (479 tests passing, 100% coverage, clean ruff lint). This document bridges the gap between mock-tested software and real hardware by:

1. Extending the existing 8-stage integration plan (`docs/design/integration_plan.md`) with StallGuard firmware overlay steps at each relevant stage.
2. Adding a formal test procedure (TP-06) for StallGuard validation, following the format of TP-01 through TP-05 in `docs/design/test_procedures.md`.
3. Mapping StallGuard bring-up onto the Week 9--11 schedule from `schedule.md`.

### Relationship to Existing Documents

This document is an **addendum**, not a replacement. It assumes the reader has access to:

| Document | What It Provides |
|----------|------------------|
| `docs/design/integration_plan.md` | Base 8-stage hardware bring-up sequence (Stages 1--8) |
| `docs/design/test_procedures.md` | Formal test procedures TP-01 through TP-05 |
| `src/klipper_mods/README.md` | Build and deploy instructions for StallGuard firmware overlay |
| `docs/register_allocation.md` | RTDE register mapping (including `input_double_register_1` for StallGuard load) |
| `schedule.md` | Accelerated project schedule (Weeks 9--11 = Phase 3 build) |

### Hardware Prerequisites

All items from the integration plan equipment checklist, **plus:**

- **DIAG jumper** installed on the SKR Pico E-stepper header (connects TMC2209 DIAG output to gpio16)
- **Oscilloscope** (2 channels) for DIAG pin and step pin measurements
- **Soft clamp or manual grip** for motor blocking during stall tests
- **IR thermometer** for motor temperature monitoring

---

## 2. Integration Stage Amendments

The following amendments add StallGuard overlay work to the existing integration plan stages. Each amendment specifies exactly where the new steps slot in relative to the base plan.

### Stage 2 Amendment: SKR Pico Firmware — Apply StallGuard Overlay

**Insert after:** Stage 2, step 6 ("Restart Klipper") in `integration_plan.md`.

**Additional steps:**

1. **Copy firmware overlay sources** into the Klipper tree:
   ```bash
   KLIPPER=~/klipper
   cp ~/W26-Cobot-Axis/src/klipper_mods/stallguard_shared.h  $KLIPPER/src/rp2040/
   cp ~/W26-Cobot-Axis/src/klipper_mods/core1_stallguard.c   $KLIPPER/src/rp2040/
   cp ~/W26-Cobot-Axis/src/klipper_mods/stallguard_command.c $KLIPPER/src/rp2040/
   ```

2. **Patch the Klipper Makefile** — add source files to the rp2040 build:
   ```makefile
   src-y += rp2040/core1_stallguard.c
   src-y += rp2040/stallguard_command.c
   ```

3. **Patch `main.c`** — launch core1 before Klipper's scheduler:
   ```c
   extern void core1_launch(void);
   // In armcm_main(), immediately before sched_main():
   core1_launch();
   ```

4. **Rebuild and reflash** the firmware:
   ```bash
   cd $KLIPPER
   make clean && make
   # Enter BOOTSEL, flash klipper.uf2, verify USB serial enumerates
   ```

5. **Install the klippy extras module:**
   ```bash
   cp ~/W26-Cobot-Axis/src/klipper_mods/klippy_extras/stallguard_monitor.py \
      $KLIPPER/klippy/extras/
   ```

6. **Add `[stallguard_monitor]` section** to `printer.cfg`:
   ```ini
   [stallguard_monitor]
   poll_interval: 0.05
   ```

7. **Restart Klipper** and verify the overlay loaded:
   ```bash
   sudo systemctl restart klipper
   curl http://localhost:7125/printer/objects/query?stallguard_monitor
   ```

**Verification:**

- `stallguard_query` command responds via Moonraker API.
- Response shows `stall_active: false`, `stall_count: 0`, `last_stall_ticks: 0`.
- Even without the DIAG jumper installed yet, the query must succeed (stall_count stays 0).
- `/tmp/klippy.log` contains `StallGuard monitor started` with no errors.

**If overlay does not compile:** Fall back to base Klipper firmware (revert `Makefile` and `main.c` edits, rebuild). The system works without StallGuard — the bridge daemon handles `_stallguard_available = False` gracefully (see `src/bridge/klipper_status.py:146`).

---

### Stage 3 Amendment: Stepper Motion — DIAG Jumper and GPIO Verification

**Insert after:** Stage 3, step 5 ("Observe the motor") in `integration_plan.md`.

**Additional steps:**

1. **Install the DIAG jumper** on the SKR Pico E-stepper header.
   - This connects the TMC2209 DIAG output to gpio16.
   - The pin is active-low: HIGH = no stall, LOW = stall detected.

2. **Verify gpio16 is not floating.** Run a TMC2209 status dump:
   ```
   DUMP_TMC STEPPER="manual_stepper pump"
   ```
   The `drv_status` register should show a `diag` field. With the motor idle and no stall, DIAG should be HIGH (not asserted).

3. **Baseline stall test.** With the motor running at 20 mm/s:
   - Manually block the motor shaft with a soft grip.
   - Query `stallguard_monitor` via Moonraker:
     ```bash
     curl http://localhost:7125/printer/objects/query?stallguard_monitor
     ```
   - Expected: `stall_active: true`, `stall_count: 1`.
   - Release the motor. Query again: `stall_active: false`, `stall_count` still 1.

4. **Send `stallguard_clear`** via Moonraker custom G-code or klippy console. Query again: `stall_count: 0`.

**If DIAG jumper is not available:** Skip these steps; gpio16 will float. Core1's 16-iteration debounce (~1.3 us) prevents spurious triggers from floating pin noise, but stall detection will not function until the jumper is installed.

---

### Stage 4 Amendment: TMC2209 Tuning — StallGuard Threshold Characterization

**Insert after:** Stage 4, step 7 ("Test StealthChop vs SpreadCycle") in `integration_plan.md`.

**Additional steps:**

1. **Set initial threshold.** In `printer.cfg`:
   ```ini
   [tmc2209 manual_stepper pump]
   driver_SGTHRS: 100
   ```
   Restart Klipper after editing.

2. **Run at each operating speed** (5, 10, 20, 30, 50 mm/s) for 30 seconds per speed:
   ```
   MANUAL_STEPPER STEPPER=pump MOVE=1000 SPEED=<speed>
   ```

3. **Record `sg_result` at each speed** by querying the TMC2209 status:
   ```bash
   curl "http://localhost:7125/printer/objects/query?tmc2209%20manual_stepper%20pump"
   ```
   Record `sg_result` from the `drv_status` field. Also query `stallguard_monitor` to check for false stall triggers.

4. **Build characterization table:**

   | Speed (mm/s) | SGTHRS=50 sg_result | SGTHRS=100 sg_result | SGTHRS=150 sg_result | False stall? |
   |--------------|---------------------|----------------------|----------------------|--------------|
   | 5            |                     |                      |                      |              |
   | 10           |                     |                      |                      |              |
   | 20           |                     |                      |                      |              |
   | 30           |                     |                      |                      |              |
   | 50           |                     |                      |                      |              |

5. **Select threshold** that avoids false positives at all operating speeds but reliably catches real stalls at 20 mm/s (the primary operating speed).

6. **Update `driver_SGTHRS`** in `printer.cfg` with the chosen value and commit.

---

### Stage 5 Amendment: Bridge Daemon — StallGuard Status Verification

**Insert after:** Stage 5, step 5 ("Verify the bridge daemon's command translation") in `integration_plan.md`.

**Additional steps:**

1. **Verify `stallguard_monitor` appears in Klipper status objects.** The bridge daemon's `KlipperStatusPoller` (`src/bridge/klipper_status.py`) queries `stallguard_monitor` alongside `tmc2209 manual_stepper pump` and `stepper_enable`:
   ```python
   # klipper_status.py:170 — queries "stallguard_monitor": None
   ```
   Run the bridge daemon with `--log-level DEBUG` and confirm log output includes stallguard monitor data.

2. **Verify `is_hardware_stall()` works.** With the motor running at 20 mm/s, block the shaft. Check the bridge daemon log for:
   ```
   WARNING: Hardware stall detected (core1 DIAG pin)
   ```
   This message comes from `bridge_daemon.py:438` (`_check_stall_status()`).

3. **Verify `input_double_register_1` updates on the UR30 side.** The bridge writes `stallguard_load` (TMC2209 `sg_result` as a float) to `input_double_register_1` via `rtde.write_status()` (`bridge_daemon.py:640`). On the teach pendant (or via `test_rtde.py`), read `input_float_register(1)` and confirm a non-zero value during motor operation.

4. **Test hardware stall priority.** Block the motor and verify:
   - Bridge log shows `"Hardware stall detected (core1 DIAG pin)"` **before** any `"Stepper stall detected (StallGuard below threshold)"` message.
   - `state.error_code` is set to `ERR_STALL` (value 2) by the hardware path first.
   - The UART-polled `is_stalled()` path (`klipper_status.py:81`) would be slower (~250ms) but the hardware path (`is_hardware_stall()`, `klipper_status.py:105`) wins.

---

### New Stage 5b: StallGuard End-to-End Validation

**Insert between:** Stage 5 and Stage 6 in `integration_plan.md`.

**Goal:** Validate the full StallGuard detection chain from DIAG pin hardware assertion through to UR30 RTDE register update.

**Estimated time:** 1--2 hours

**Prerequisites:**
- Stages 1--5 complete (including all StallGuard amendments above)
- DIAG jumper installed
- `[stallguard_monitor]` active with tuned `driver_SGTHRS`
- Bridge daemon running with status polling enabled

**Procedure:**

1. **Full-chain stall test.** Motor at 20 mm/s. Block motor shaft.
   - Verify detection chain: core1 DIAG detect -> `stallguard_query` -> klippy `stallguard_monitor` status -> bridge daemon `_check_stall_status()` -> RTDE `write_status(error_code=ERR_STALL)` -> UR30 reads `input_int_register_1 = 2`.

2. **Measure detection latency.** Time from DIAG pin assertion to RTDE register update.
   - Use oscilloscope on gpio16 (DIAG) to capture the assertion edge.
   - Log bridge daemon timestamp when `ERR_STALL` is written.
   - Expected: < 100 ms (50 ms klippy poll interval + 8 ms bridge cycle).

3. **Verify URScript functions.** On the UR30 teach pendant:
   - `check_stallguard()` returns -1 during active stall (see `extrusion_control.script:97`).
   - `get_stallguard_load()` returns the `sg_result` value (see `extrusion_control.script:91`).

4. **Test stall recovery.** Release motor. Clear fault (disable/re-enable extrusion on UR30). Resume extrusion.
   - `check_stallguard()` returns 1 (ok) after recovery.
   - `sg_result` returns to normal (non-zero) values.

**Verification:**

- Full chain from hardware DIAG to UR30 registers works within < 100 ms.
- URScript helper functions return correct values.
- System recovers cleanly from stall condition.

---

## 3. TP-06: StallGuard Validation Test

| Field | Value |
|-------|-------|
| **Test ID** | TP-06 |
| **Name** | StallGuard Validation Test |
| **Objective** | Verify that the core1 DIAG-based stall detection correctly detects motor stalls, reports them through the full communication chain, and enables safe recovery. Validate detection latency, threshold tuning, and dual-path (hardware DIAG vs UART-polled) priority. |
| **Estimated Duration** | 60 minutes |

### 6.1 Equipment

| Item | Purpose |
|------|---------|
| UR30 + teach pendant | Issue extrusion commands; read RTDE input registers |
| Pi (headless) | Run bridge daemon and Klipper with StallGuard overlay |
| SKR Pico + stepper motor + pump | Actuator under test |
| Oscilloscope (2 channels, >= 1 MHz) | CH1: gpio16 (DIAG pin); CH2: gpio14 (step pin) |
| Oscilloscope probes (2x, 10x) | 3.3V logic-level signals |
| Soft clamp or manual grip | Motor blocking for stall injection |
| IR thermometer | Motor temperature monitoring |
| Pi400 or laptop | SSH for log monitoring; Mainsail web UI |

### 6.2 Prerequisites

- Stages 1--5 of `integration_plan.md` complete (base system working end-to-end).
- All Stage 2--5 amendments from Section 2 of this document applied.
- DIAG jumper installed on SKR Pico E-stepper header.
- `[stallguard_monitor]` section in `printer.cfg` with `poll_interval: 0.05`.
- StallGuard firmware overlay flashed (core1_stallguard.c and stallguard_command.c compiled in).
- Bridge daemon running with status polling enabled (`--no-status-poll` NOT set).
- `driver_SGTHRS` set to the value determined during Stage 4 amendment tuning.

### 6.3 Procedure -- Part A: DIAG Pin Verification (Hardware Layer)

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Motor idle. Query `stallguard_monitor` via Moonraker API: `curl http://localhost:7125/printer/objects/query?stallguard_monitor` | `stall_active: false`, `stall_count: 0`, `last_stall_ticks: 0` | API response JSON |
| 2 | Connect scope CH1 to gpio16 (DIAG pin). Verify pin is HIGH (pulled up, no stall). | Steady HIGH ~3.3V | Scope screenshot: `TP06A_step2_diag_idle.png` |
| 3 | Run motor at 20 mm/s: `MANUAL_STEPPER STEPPER=pump MOVE=1000 SPEED=20`. Monitor gpio16 on scope. | Pin stays HIGH during normal operation | Scope trace: `TP06A_step3_diag_running.png` |
| 4 | Block motor shaft with soft grip. Observe scope. | gpio16 drops LOW within microseconds of stall. | Scope capture with time cursor measuring assertion delay: `TP06A_step4_diag_stall.png` |
| 5 | Query `stallguard_monitor` again. | `stall_active: true`, `stall_count: 1`, `last_stall_ticks > 0` | API response JSON |
| 6 | Release motor shaft. Wait 1 second. Query again. | `stall_active: false` (DIAG de-asserts when motor moves freely). `stall_count` still 1. | API response JSON |
| 7 | Block motor shaft again. Query. | `stall_count: 2` | Verify cumulative counting |
| 8 | Send `stallguard_clear` command (via Moonraker or klippy console). Query. | `stall_count: 0` | Verify clear works |

### 6.4 Procedure -- Part B: Detection Latency Measurement

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Set scope to single-shot trigger on gpio16 falling edge (DIAG assertion). Arm scope. | Scope armed | -- |
| 2 | Motor running at 20 mm/s. Block shaft. | Scope captures DIAG assertion edge. | Scope capture: `TP06B_trial<N>.png` |
| 3 | Simultaneously, log bridge daemon timestamps for when `ERR_STALL` is written to RTDE. Run bridge with `--log-level DEBUG`; grep for `"Hardware stall detected"`. | Timestamp logged in bridge log. | Bridge log excerpt |
| 4 | Compute latency: DIAG assertion (scope) to bridge `ERR_STALL` write (log timestamp). | < 100 ms (50 ms klippy poll + 8 ms bridge cycle) | Latency value (ms) |
| 5 | Repeat 10 times: release motor, wait 5 seconds, re-stall. Compute mean, P95, and max latency. | All 10 measurements < 100 ms. Mean < 70 ms. | Latency table (10 rows + stats) |

**Latency data sheet:**

| Trial | DIAG Assert Time | Bridge ERR_STALL Time | Latency (ms) | Notes |
|-------|------------------|-----------------------|---------------|-------|
| 1     |                  |                       |               |       |
| 2     |                  |                       |               |       |
| ...   |                  |                       |               |       |
| 10    |                  |                       |               |       |
| **Mean** | | | | |
| **P95** | | | | |
| **Max** | | | | |

### 6.5 Procedure -- Part C: Threshold Tuning

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Set `driver_SGTHRS: 50` (low sensitivity) in `printer.cfg`. Restart Klipper. Run motor at 5, 10, 20, 30, 50 mm/s for 30 seconds each. Record `sg_result` at each speed via Moonraker API. | No false stall triggers. `sg_result` varies with speed. | Speed vs sg_result table |
| 2 | Set `driver_SGTHRS: 100`. Restart Klipper. Repeat same speed sweep. | Possibly false triggers at low speeds. | Speed vs sg_result table |
| 3 | Set `driver_SGTHRS: 150` (high sensitivity). Restart Klipper. Repeat. | Likely false triggers at low and medium speeds. | Speed vs sg_result table |
| 4 | At chosen threshold, verify real stalls are still detected: block motor at 20 mm/s. | `stall_active: true`, `ERR_STALL` reported in bridge log. | Bridge log excerpt |
| 5 | Document chosen threshold value and rationale. | -- | Written notes |

**Threshold characterization data sheet:**

| Speed (mm/s) | SGTHRS=50 sg_result | False stall? | SGTHRS=100 sg_result | False stall? | SGTHRS=150 sg_result | False stall? |
|--------------|---------------------|--------------|----------------------|--------------|----------------------|--------------|
| 5            |                     |              |                      |              |                      |              |
| 10           |                     |              |                      |              |                      |              |
| 20           |                     |              |                      |              |                      |              |
| 30           |                     |              |                      |              |                      |              |
| 50           |                     |              |                      |              |                      |              |

### 6.6 Procedure -- Part D: Dual-Path Priority Verification

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Motor at 20 mm/s. Bridge running with status polling enabled. Confirm normal operation in bridge log. | Bridge log shows RUNNING status, no errors. | Bridge log |
| 2 | Block motor shaft. Start stopwatch. | Stall detected via hardware DIAG (core1) first. Bridge log shows `"Hardware stall detected (core1 DIAG pin)"` BEFORE any `"Stepper stall detected (StallGuard below threshold)"` entry. | Bridge log with timestamps |
| 3 | Check that `ERR_STALL` was set by the hardware path, not the UART path. | Log confirms hardware stall message (`bridge_daemon.py:438`) appeared first. Bridge annotated `STALL_HW` (not `STALL`). | Bridge log grep for `STALL_HW` vs `STALL` |
| 4 | Disable StallGuard overlay: remove `[stallguard_monitor]` from `printer.cfg`, restart Klipper. Bridge daemon will set `_stallguard_available = False` (see `klipper_status.py:148`). Block motor again at 20 mm/s. | UART-polled stall detection kicks in as fallback (~250 ms). `ERR_STALL` still reported but with higher latency. Log shows `"Stepper stall detected (StallGuard below threshold)"` instead. | Compare timestamps: hardware path vs UART-only path |
| 5 | Re-enable `[stallguard_monitor]` in `printer.cfg` and restart Klipper to restore full functionality. | `stallguard_monitor` available again. | API query confirms |

### 6.7 Procedure -- Part E: Full-Chain RTDE Verification

| Step | Action | Expected Result | Record |
|------|--------|-----------------|--------|
| 1 | Motor at 20 mm/s, system stable. On UR30 teach pendant, read `input_float_register(1)` (stallguard_load register, per `register_allocation.md`). | Non-zero `sg_result` value (healthy motor, typical range 50--255). | Register value |
| 2 | Block motor shaft. Read `input_float_register(1)` again within 1 second. | Value drops toward 0.0 (stall = low load reading). | Register value |
| 3 | Check `input_int_register(1)` on UR30 (error code). | = 2 (`ERR_STALL`, per `config.py`) | Register value |
| 4 | Check `input_bit_register(65)` on UR30 (fault flag). | = True | Register value |
| 5 | In URScript, call `check_stallguard()` (see `extrusion_control.script:97`). | Returns -1 (stall: `sg < 10`). | URScript output |
| 6 | Release motor. Clear fault: set `output_bit_register_64 = False` then `True` (disable/re-enable extrusion). Resume extrusion at 20 mm/s. | System recovers. `check_stallguard()` returns 1 (ok). `input_int_register(1)` = 0 (no error). `input_bit_register(65)` = False. | URScript output; teach pendant registers |

### 6.8 Pass/Fail Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| DIAG pin asserts on stall | gpio16 goes LOW within 10 us of mechanical stall | Pin stays HIGH during stall |
| Core1 updates shared SRAM | `stallguard_query` shows `stall_active: true`, `stall_count` increments | `stall_active` stays false |
| Detection latency (DIAG to RTDE) < 100 ms | All 10 measurements below 100 ms | Any measurement > 100 ms |
| Detection latency mean < 70 ms | Mean of 10 trials < 70 ms | Mean exceeds 70 ms |
| No false positives at chosen threshold | 30-second run at all speeds (5--50 mm/s) with zero false `stall_active` assertions | Any false trigger |
| Hardware path takes priority over UART | Bridge log shows hardware stall detected before UART-polled stall | UART stall detected first |
| UR30 receives ERR_STALL + fault flag | Teach pendant shows `error_code = 2`, `fault = True` | Registers not updated |
| URScript `check_stallguard()` returns -1 on stall | Function returns -1 during active stall | Wrong return value |
| Recovery after stall + clear | System accepts new commands, `sg_result` returns to normal range | System stuck in fault state |
| `stallguard_clear` resets counter | `stall_count` returns to 0 after clear command | Counter not reset |

### 6.9 Data Recorded

- **Oscilloscope captures:** DIAG pin assertion waveforms (Parts A, B). File naming: `TP06<part>_step<N>.png`.
- **Latency measurements:** 10-trial table with mean, P95, and max (Part B).
- **Threshold characterization:** Speed vs `sg_result` table at three threshold values (Part C).
- **Bridge daemon log excerpts:** Hardware vs UART stall detection order with timestamps (Part D).
- **UR30 teach pendant register screenshots:** `input_int_register_1`, `input_float_register_1`, `input_bit_register_65` during stall and recovery (Part E).
- **Chosen StallGuard threshold value** with written justification.

---

## 4. Updated TP-04b Note

The existing TP-04b (Stepper Stall, `test_procedures.md` Section 6.3) was written pre-StallGuard as a baseline test. Its "Expected Behavior" section states:

> "Without StallGuard configured (MVP scope), the stepper is open-loop and will not detect a stall."

Now that the StallGuard firmware overlay and klippy extras are implemented, the following note should be appended to TP-04b:

> **Update (2026-02-24):** With StallGuard firmware overlay installed and `[stallguard_monitor]` active, this test should now show stall detection. Refer to **TP-06** (in `docs/design/hitl_plan.md`) for detailed StallGuard-specific validation. The pass criterion "stall detected and reported" in TP-04b step 7 now applies by default (no longer a stretch goal). The hardware DIAG path via core1 provides detection within ~60 ms, compared to the ~250 ms UART-polled fallback.

---

## 5. Integration Timeline

Maps the StallGuard amendments onto the existing Week 9--11 schedule from `schedule.md` and `integration_plan.md`.

| Week | Day | Base Integration (from integration_plan.md) | StallGuard Overlay (this document) |
|------|-----|----------------------------------------------|------------------------------------|
| 9 (Mar 2--8) | Day 1 | Stage 1: Flash Pi, Klipper, Moonraker | -- |
| 9 | Day 1--2 | Stage 2: Build firmware, flash SKR Pico | **Stage 2 amendment:** Apply firmware overlay, install klippy extras, verify `stallguard_query` responds |
| 9 | Day 2--3 | Stage 3: Wire stepper, test motion | **Stage 3 amendment:** Install DIAG jumper, verify gpio16, baseline stall test |
| 9 | Day 3--4 | Stage 4: TMC2209 current/thermal tuning | **Stage 4 amendment:** Tune `driver_SGTHRS` threshold at 5/10/20/30/50 mm/s |
| 9 | Day 4--5 | Stage 5: Bridge daemon + Klipper | **Stage 5 amendment:** Verify `stallguard_load` in RTDE, hardware stall priority |
| 9 | Day 5 | Buffer for troubleshooting | **Stage 5b:** StallGuard end-to-end validation |
| 10 (Mar 9--15) | Open | Stage 6: RTDE connection to UR30 | TP-06 Part E: full-chain RTDE register verification |
| 10--11 | Open | Stage 7: End-to-end under robot motion | TP-06 complete (all Parts A--E) |
| 11 (Mar 16--22) | Open | Stage 8: Pi400 HMI setup | Monitor `sg_result` in Mainsail dashboard; verify stallguard_monitor appears in web UI |

**Week 9 exit criteria (amended):** Base criteria from `integration_plan.md` plus: StallGuard firmware overlay flashed, DIAG jumper installed, `stallguard_query` responds correctly, `driver_SGTHRS` threshold selected, and bridge daemon reports hardware stall events.

**Weeks 10--11 exit criteria (amended):** Base criteria plus: TP-06 complete (all parts pass), latency < 100 ms confirmed, UR30 registers updated on stall, recovery procedure validated.

---

## 6. Dev Bench Setup — URSim on Windows

This section describes a **development bench** that lets us test the full RTDE communication chain using a Windows laptop running URSim instead of the physical UR30 robot arm. The dev bench is independent of StallGuard — it validates the bridge daemon ↔ UR controller link.

### 6.1 Topology

```
Windows Laptop (x86-64)          Raspberry Pi              SKR Pico (RP2040)
┌──────────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Docker Desktop      │    │  Klipper host     │    │  Klipper MCU     │
│  └─ URSim container  │◄──►│  Bridge daemon    │◄──►│  TMC2209 driver  │
│     (UR30 model)     │RTDE│  Moonraker        │USB │  Core1 StallGuard│
│     port 30004       │TCP │  klippy extras    │    │  DIAG on gpio16  │
└──────────────────────┘    └──────────────────┘    └──────────────────┘
        │ Ethernet              │ Ethernet              │ stepper wires
        └───────────────────────┘                       │
              gigabit switch or direct                   ▼
                                                    Stepper Motor
```

### 6.2 Windows URSim Setup

1. Install Docker Desktop on Windows (x86-64, WSL2 backend).
2. Pull and run URSim:
   ```bash
   docker run --rm -d \
     -e ROBOT_MODEL=UR30 \
     -p 30004:30004 -p 29999:29999 -p 5900:5900 -p 6080:6080 \
     --name ursim \
     universalrobots/ursim_e-series
   ```
3. Access teach pendant via browser at `http://localhost:6080` (noVNC).
4. Power on the virtual robot in the teach pendant.
5. Verify RTDE port is listening: `Test-NetConnection localhost -Port 30004`

### 6.3 Network Configuration

- Windows and Pi must be on the same LAN (or connected via direct ethernet cable).
- Find Windows IP: `ipconfig` → note IPv4 address (e.g., `192.168.1.100`).
- Find Pi IP: `hostname -I` on Pi (e.g., `192.168.1.50`).
- Bridge daemon config: point `--host` at the Windows IP where URSim listens.

**Bridge daemon launch for dev bench:**

```bash
# On Pi — point bridge at Windows URSim instead of real UR30
python -m bridge --host <WINDOWS_IP>
```

Or create a systemd override:

```bash
sudo systemctl edit w26-bridge
# Add under [Service]:
# ExecStart=
# ExecStart=/home/pi/klippy-env/bin/python -m bridge --host <WINDOWS_IP>
```

### 6.4 What Can Be Tested with URSim

| Test | URSim? | Notes |
|------|--------|-------|
| RTDE connection + register exchange | Yes | Full RTDE protocol support |
| Bridge reads UR output registers | Yes | URSim sends real register values |
| Bridge writes input registers | Yes | URSim receives and displays them |
| URScript `extrusion_control.script` | Yes | Load via teach pendant, run against bridge |
| StallGuard DIAG detection (core1) | N/A | Pi + SKR Pico side, independent of UR |
| StallGuard → RTDE → URSim display | Yes | End-to-end: stall motor → see fault on teach pendant |
| Stepper motion commands from UR | Yes | URScript sends rate → bridge → Klipper → motor moves |
| Latency measurement (RTDE round-trip) | Yes | Measure on bridge side |

### 6.5 What Cannot Be Tested with URSim

- Real robot motion (obviously).
- Physical tool attachment / end effector.
- Power from UR controller power block (use a bench supply for 24V).
- Real-time safety behaviors (e-stop chain).

### 6.6 Dev Bench Test Sequence

Stages 1--4 need only Pi + SKR Pico. URSim joins at Stage 5.

| Stage | What | Equipment | Deploy Step |
|-------|------|-----------|-------------|
| 1 | Flash MainsailOS to Pi SD card | Pi, SD card | Manual |
| 2 | Run `deploy.sh` on Pi (full install) | Pi + network | `bash deploy.sh` |
| 3 | Verify Klipper + SKR Pico USB link | Pi + SKR Pico | Check `ls /dev/serial/by-id/` |
| 4 | Test stepper motion + StallGuard DIAG | Pi + SKR Pico + stepper | `MANUAL_STEPPER STEPPER=pump SPEED=20 MOVE=100` |
| 5 | Start URSim on Windows | Windows laptop | `docker run ...` (see Section 6.2) |
| 6 | Point bridge at URSim, verify RTDE | Pi + Windows | `dev-sync.sh` then restart bridge |
| 7 | Load URScript on teach pendant, test extrusion commands | Windows (noVNC) | Manual via browser |
| 8 | Full chain: URScript → bridge → Klipper → motor; stall → fault on teach pendant | All three | TP-06 Parts D+E adapted for URSim |

---

## 7. Deploy Workflow

Two deployment paths exist depending on the task:

### 7.1 Full Deploy (`deploy.sh`)

Used for initial setup or after firmware changes. Takes several minutes (apt, pip, firmware build).

```bash
# Full deploy including StallGuard overlay
bash deploy.sh

# Skip firmware flash (config/service changes only)
bash deploy.sh --skip-flash

# Skip StallGuard overlay (base Klipper only)
bash deploy.sh --skip-stallguard
```

StallGuard overlay (Step 6b) copies C/H files into the Klipper tree, patches `Makefile` and `main.c` idempotently, and installs the klippy extras module. Step 7's firmware build then compiles the overlay in.

### 7.2 Iterative Dev Sync (`scripts/dev-sync.sh`)

Used during active development for fast code-change cycles. Runs in under 5 seconds on LAN.

```bash
# Sync to default Pi (pi@raspberrypi.local)
bash scripts/dev-sync.sh

# Sync to specific Pi
bash scripts/dev-sync.sh pi@192.168.1.50
```

This rsyncs `src/` to the Pi, restarts `w26-bridge`, copies `stallguard_monitor.py` into klippy extras, and restarts Klipper. Does **not** rebuild firmware — use full `deploy.sh` for firmware changes.

### 7.3 When to Use Which

| Scenario | Tool |
|----------|------|
| First-time Pi setup | `deploy.sh` |
| Changed C firmware files | `deploy.sh` (needs rebuild) |
| Changed bridge Python code | `dev-sync.sh` |
| Changed `printer.cfg` | `dev-sync.sh` |
| Changed `stallguard_monitor.py` | `dev-sync.sh` |
| Changed `deploy.sh` itself | `deploy.sh` |

---

## 8. Risk and Fallback

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| DIAG jumper not installed | Low | Medium -- gpio16 floats, core1 may see spurious transitions | Core1 firmware includes 16-iteration debounce (~1.3 us). Without the jumper, the pull-up resistor on gpio16 keeps it HIGH, but noise could cause false edges. **Fallback:** System works without jumper; StallGuard simply never triggers. |
| StallGuard firmware overlay does not compile | Low | Medium -- no hardware-speed stall detection | **Fallback:** Revert `Makefile` and `main.c` patches, rebuild base Klipper firmware. Bridge daemon falls back to UART-only stall detection via `is_stalled()` (TMC2209 `sg_result` polled at ~4 Hz by `KlipperStatusPoller`). `_stallguard_available` auto-sets to `False` on query error (`klipper_status.py:148`). |
| False positives at all operating speeds | Medium | Medium -- StallGuard unusable for this motor/pump combination | Lower `driver_SGTHRS` value. If no clean threshold exists at any value, disable StallGuard (`[stallguard_monitor]` removed from `printer.cfg`) and rely on UART-polled `sg_result` only (4 Hz but still functional). |
| Core1 conflicts with Klipper scheduler on core0 | Low | High -- Klipper step timing corrupted | Core1 uses only SIO registers and shared SRAM under spinlock #16 — it should not affect core0's timer interrupts. **Fallback:** Back out the `main.c` patch (remove `core1_launch()` call), rebuild without core1. Lose hardware-speed DIAG detection but keep klippy extras polling via UART. |
| Latency exceeds 100 ms target | Medium | Low -- detection still works, just slower than desired | Profile the chain: check if klippy `poll_interval` (50 ms) is the bottleneck. Reduce to 25 ms (`poll_interval: 0.025`) at the cost of higher CPU usage. Check bridge `LOOP_HZ` (125 Hz = 8 ms period). |
| TMC2209 DIAG output not connected on SKR Pico rev | Low | High -- hardware does not support the feature | Verify the SKR Pico V1.0 schematic shows DIAG routed to the jumper header. If not connected, StallGuard overlay is inoperable — fall back to UART-only path. |
| URSim Docker container won't start on Windows | Low | Low -- dev bench convenience only | Verify Docker Desktop uses WSL2 backend. Try `docker pull universalrobots/ursim_e-series` manually. Alternatively, install URSim natively via the UR offline simulator installer. Does not block hardware testing. |
| Windows firewall blocks RTDE port 30004 | Medium | Low -- easy to fix | Add inbound rule: `netsh advfirewall firewall add rule name="URSim RTDE" dir=in action=allow protocol=TCP localport=30004`. Or temporarily disable firewall for testing. |
