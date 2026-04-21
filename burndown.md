# Burndown Checklist: Apr 12 -- Apr 24

Sequential task list from today to final presentation. Check off as you go.
Cross-references `todo.md` (master tracker) and design docs for details.

**Hard deadlines:**
- ~~Apr 2: Analysis assignment (motor load + ramp sim) -- PAST DUE, submit ASAP~~
- Apr 23: Final report (PDF, max 2000 words)
- Apr 24: Oral presentation + design defense (6:30--9:30 PM)

---

## Day 0: Apr 12 (Sat) -- Software Prep

### Repo Cleanup
- [x] Merge PR #8 (pre-commit config fix)
- [x] Merge PR #6 (actions/download-artifact 4->8)
- [x] Merge PR #7 (actions/upload-artifact 4->7)
- [x] Merge PR #9 (codecov/codecov-action 5->6) -- auto-merged by dependabot workflow

### Bug Fixes (code changes required before hardware)
- [x] **Fix `SYNC=0` in `stepper_move()`** -- `src/bridge/klipper_client.py:150` -- append `SYNC=0` to G-code string. Without this, the bridge main loop blocks for the entire move duration at 125 Hz.
- [x] **Fix `SYNC=0` in `stepper_set_position()`** -- `src/bridge/klipper_client.py:157` -- same issue, add `SYNC=0` for consistency.
- [x] Update affected tests in `src/bridge/tests/` to expect `SYNC=0` in commands.
- [x] Run full test suite: `python -m pytest src/bridge/tests/ -v` (must stay at 479+ tests, 100% coverage).
- [x] Commit fix to main.

### Flash SD Card
- [ ] Download MainsailOS image (mainsailos.xyz).
- [ ] Flash to microSD with Raspberry Pi Imager.
- [ ] Configure: hostname `w26-pi`, user `pi`, enable SSH, set Wi-Fi/ethernet for lab network.

### Gather Hardware
- [ ] Raspberry Pi 4B + power supply (5.1V/3A USB-C).
- [ ] SKR Pico V1.0 + USB-A to Micro-USB cable.
- [ ] 24V power supply (or UR controller power block).
- [ ] Stepper motor (confirm received / available from instructor).
- [ ] DIAG jumper for SKR Pico E-stepper header.
- [ ] Ethernet cable + gigabit switch (for UR30 connection).
- [ ] Multimeter (for coil identification and current checks).

---

## Day 1: Apr 13 (Sun) -- Pi Boot + Klipper

### Stage 1: First Boot
Ref: `docs/dev_bench_guide.md`

- [ ] Insert SD card, connect ethernet, power on Pi.
- [ ] SSH in: `ssh pi@w26-pi.local`
- [ ] Verify services: `systemctl status klipper moonraker`
- [ ] Verify Mainsail UI loads: `http://w26-pi.local` (errors OK, no printer.cfg yet).
- [ ] Run system updates: `sudo apt update && sudo apt upgrade -y`

### Stage 2: Deploy + Flash Firmware
Ref: `deploy.sh` (11-step script)

- [ ] Clone repo: `git clone https://github.com/wrbell/W26-Cobot-Axis.git ~/W26-Cobot-Axis`
- [ ] Run full deploy: `cd ~/W26-Cobot-Axis && bash deploy.sh`
  - Installs system deps, Python deps (ur_rtde may take 10-15 min on ARM).
  - Deploys printer.cfg, moonraker.conf, mainsail.cfg.
  - Builds + flashes Klipper firmware to SKR Pico (hold BOOTSEL, plug USB, copy .uf2).
  - Installs w26-bridge systemd service.
  - Auto-detects and updates MCU serial path in printer.cfg.
- [ ] Verify Klipper ready: `journalctl -u klipper -n 20` -- look for "Printer is ready".
- [ ] Verify Mainsail shows green status at `http://w26-pi.local`.
- [ ] Verify StallGuard module: `curl http://localhost:7125/printer/objects/query?stallguard_monitor`

### Stage 3: First Stepper Motion
Ref: `docs/config_guide.md` Section 2

- [ ] Identify motor coil pairs with multimeter (continuity test).
- [ ] Wire stepper to SKR Pico E-axis connector (4 wires).
- [ ] Apply 24V to SKR Pico VIN (**verify polarity first**).
- [ ] Test via Mainsail console:
  ```
  MANUAL_STEPPER STEPPER=pump ENABLE=1
  MANUAL_STEPPER STEPPER=pump SET_POSITION=0
  MANUAL_STEPPER STEPPER=pump MOVE=10 SPEED=5
  ```
- [ ] Verify motor rotates. If wrong direction, flip `dir_pin` polarity in printer.cfg (`!` prefix).
- [ ] Test speeds: 5, 25, 50 mm/s.
- [ ] Disable: `MANUAL_STEPPER STEPPER=pump ENABLE=0`

---

## Day 2: Apr 14 (Mon) -- Motor Tuning + Bridge

### Stage 4: TMC2209 Tuning
Ref: `docs/config_guide.md` Sections 3--5

- [ ] Determine step angle: send `MOVE=40 SPEED=5` -- if shaft does exactly 1 revolution, it's 1.8 deg/step (200 steps/rev). Adjust if not.
- [ ] Start `run_current` at 0.3A, increase in 0.1A increments until motor holds under pump load.
- [ ] Set `hold_current` to 50--70% of `run_current`.
- [ ] Sustained motion test: `MOVE=1000 SPEED=25` (~40s). Monitor TMC2209 temp (target < 80 C).
- [ ] Run `DUMP_TMC STEPPER="manual_stepper pump"` -- verify no error flags.
- [ ] Commit updated printer.cfg with final current settings.

### Calibrate Rotation Distance
Ref: `docs/config_guide.md` Section 4

- [ ] Measure actual pump displacement per motor revolution.
- [ ] Update `rotation_distance` in printer.cfg so MOVE units = volume dispensed.

### Stage 5: Bridge Daemon on Pi
- [ ] Update `src/bridge/config.py:11` with actual UR30 IP (or leave placeholder if no robot yet).
- [ ] Test bridge dry-run: `python3 -m bridge.bridge_daemon --dry-run --log-level DEBUG`
- [ ] Test Klipper connection directly:
  ```python
  from bridge.klipper_client import KlipperClient
  k = KlipperClient("/tmp/klippy_uds")
  k.connect()
  k.stepper_move("pump", 5.0, 10.0)  # motor should move
  k.stepper_disable("pump")
  k.disconnect()
  ```
- [ ] Verify w26-bridge service: `sudo systemctl start w26-bridge && journalctl -u w26-bridge -f`

---

## Day 3: Apr 15 (Tue) -- UR30 Connection

### Stage 6: RTDE Connection
Ref: `docs/design/integration_plan.md` Stage 6

- [ ] Update `src/bridge/config.py:11` with UR30 IP.
- [ ] Verify network: `ping <UR30_IP>` and `nc -zv <UR30_IP> 30004`
- [ ] Test RTDE independently: read output registers, write input registers.
- [ ] Load `src/urscript/extrusion_control.script` onto UR30 teach pendant.
- [ ] Start bridge: `python3 -m bridge.bridge_daemon --host <UR30_IP> --log-level DEBUG`
- [ ] Verify bridge logs show RTDE read/write cycles at 125 Hz.
- [ ] Verify teach pendant shows input register values (status, ready flag).

### Stage 7: End-to-End Smoke Test
Ref: `docs/design/integration_plan.md` Stage 7

- [ ] All services running: Klipper + Moonraker + bridge + URScript.
- [ ] From UR30: enable + mode=EXTRUDE + rate=10.0 --> **stepper moves** (THE MILESTONE).
- [ ] Test speed changes: ramp 0->50 mm/s.
- [ ] Test mode transitions: extrude -> retract -> off.
- [ ] Test e-stop: `output_bit_register_65 = True` --> stepper halts immediately.
- [ ] Verify status feedback on teach pendant.
- [ ] Run `test_basic.script` Sub-tests A--F, I.

---

## Day 4: Apr 16 (Wed) -- URScript + Slicer Integration

### Teach Waypoints + Advanced Tests
Ref: `docs/config_guide.md` Section 8

- [ ] Teach `START_POSE`, `MID_POSE`, `END_POSE` in all 3 URScript files.
- [ ] Sync cross-file values: max speed, accel, extrusion multiplier across printer.cfg / config.py / URScript.
- [ ] Run `test_basic.script` Sub-test G (constant-rate multi-waypoint path).
- [ ] Run `test_basic.script` Sub-test G2 (speed-sync path).

### Stage 7b: Slicer Integration
- [ ] Wrap `src/provided/Mblack0.6mm.script` with `pump_on()`/`pump_off()`.
- [ ] Load wrapped program onto UR30, run with bridge active.
- [ ] Verify pump runs continuously during 776-waypoint path.
- [ ] Run `test_calibration.script` Sub-test A (flow rate linearity).
- [ ] Run `test_calibration.script` Sub-test B2 (constant-rate gravimetric).
- [ ] Tune `EXTRUSION_MULTIPLIER` and retraction parameters.

---

## Day 5--6: Apr 17--18 (Thu--Fri) -- Formal Testing

### TP-01: End-to-End Functional Test (45 min)
Ref: `docs/design/test_procedures.md`

- [ ] All mode transitions: enable -> extrude (5/10/25/50 mm/s) -> retract -> off.
- [ ] Rate clamping: command 75 mm/s, verify clamped to 50.
- [ ] E-stop during motion: stepper halts, status=ERROR on UR30.
- [ ] Recovery from e-stop: clear fault, re-enable.
- [ ] Homing: position zeros, status=IDLE.
- [ ] Record logs + teach pendant screenshots at each step.

### TP-02: Latency Characterization (90 min)
- [ ] Method A (software): RTDE timestamp comparison.
- [ ] Method B (oscilloscope): Probe step pin gpio14, 10 measurements.
- [ ] Method C (step-change): 10->30 mm/s transition, 50 measurements.
- [ ] Compute: mean, std dev, P95, P99, min, max.
- [ ] **Pass: P95 < 20 ms, no outlier > 100 ms.**
- [ ] Generate latency histogram figure for report.

### TP-03: Speed Accuracy (60 min)
- [ ] Measure step frequency at 5/10/20/30/50 mm/s (extrude + retract), 5 readings each.
- [ ] Compute steady-state error (target < 2%).
- [ ] Oscilloscope capture: 10->30, 30->10, 0->50, 50->0 mm/s transitions.
- [ ] Rapid alternation: 10<->30 mm/s at 1 Hz for 10 cycles.

### TP-04: Fault Handling (75 min)
- [ ] TP-04a: Pull ethernet during extrusion -> stepper stops < 2s, auto-reconnect.
- [ ] TP-04b: Block motor shaft -> document open-loop behavior, DUMP_TMC, temp.
- [ ] TP-04c: `kill -9 klippy` during extrusion -> bridge detects, recovers on restart.
- [ ] TP-04d: Pull USB cable -> stepper stops, bridge reports fault, recovers.

### TP-05: Endurance Test (90 min)
- [ ] 60-min continuous run (ramp 20, alternate 15/25, burst 50, ramp down).
- [ ] Temperature readings every 10 min: TMC2209, motor, Pi CPU, RP2040.
- [ ] Zero communication errors in bridge log.
- [ ] Speed drift < 1% from initial measurement.

---

## Day 7: Apr 19 (Sat) -- Analysis + Phase 2/3 Memos

### Motor Analysis Assignment (was due Apr 2 -- submit ASAP)
- [ ] Motor load calculations (MATLAB/Simulink) -- verify stepper not overloaded.
- [ ] Motor ramp simulation -- verify current stays within driver/supply limits.
- [ ] Submit to Canvas.

### Phase 2 Memo Completion (was due Mar 1 -- submit ASAP)
- [ ] Redraw block diagram in draw.io/Visio -> export as Figure 1.
- [ ] Redraw circuit schematic in KiCad/draw.io -> export as Figure 2.
- [ ] Coordinate with Dawood: Section 5 (mechanical concept) + Figures 3--4.
- [ ] Paste memo text from `docs/phase2/memo_draft.md` into Word template.
- [ ] Insert tables + figures, verify <= 5 pages.
- [ ] Export PDF, submit.

### Phase 3 Progress Memo
- [ ] Fill in test results in `docs/phase3/progress_memo_draft.md`.
- [ ] Submit progress memorandum to instructor.

---

## Day 8--10: Apr 20--22 (Sun--Tue) -- Final Report

### Data Processing
- [ ] Compile all test data from TP-01 through TP-05.
- [ ] Generate figures: latency histogram, speed accuracy chart, transient scope captures, temperature vs time.
- [ ] Take system photos (assembled prototype, wiring, running system).

### Write Final Report
Ref: `docs/design/final_report_outline.md`

- [ ] Map to Bolton's 7-step design process.
- [ ] Relate to course topics (control systems, circuits, actuators, MCUs, system models).
- [ ] Include: block diagram, circuit schematic, test results figures, system photo.
- [ ] Team member work listing.
- [ ] References and citations.
- [ ] Stay within 2000 words (figures/tables don't count).
- [ ] Use Word Styles via UMich Office 365.
- [ ] One team member edits entire report for consistency.
- [ ] Attach supplementary materials (code, drawings).

---

## Day 11: Apr 23 (Wed) -- Report Due

- [ ] Final proofread of report.
- [ ] Export to PDF.
- [ ] **Submit final report.**

---

## Day 12: Apr 24 (Thu) -- Presentation Day

### Presentation Prep
Ref: Dr. Pannier's layout guidance in `todo.md`

- [ ] Prepare slides:
  1. Intro
  2. What each component is (Klipper, RTDE, SKR Pico, etc.)
  3. What we built
  4. Why we built it
  5. How we built it
  6. Results / "winning"
- [ ] Practice design defense (expect questions on trade studies, architecture decisions).
- [ ] Prepare prototype for live demonstration.
- [ ] Charge all batteries / verify hardware runs reliably.

### Presentation (6:30--9:30 PM)
- [ ] Deliver presentation.
- [ ] Demo prototype.
- [ ] Design defense.

---

## Optional / Stretch (if time permits)

- [ ] StallGuard hardware validation: stall motor, check Moonraker status object.
- [ ] Tag `v1.0.0` release: push tag, verify release workflow creates GitHub Release with klipper.uf2.
- [ ] Pi400 HMI setup (Mainsail web UI on second Pi for monitoring).
- [ ] URSim smoke test on Windows Docker (validates RTDE path without UR30).
- [ ] Evaluate reducing StallGuard poll rate from 20 Hz to 5 Hz.
- [ ] Merge PR #9 on GitHub if not yet done.

---

## Quick Reference

| Config File | Key Setting | Current Value | Action |
|-------------|------------|---------------|--------|
| `src/bridge/config.py:11` | `UR30_HOST` | `192.168.0.3` | Update to actual UR30 IP |
| `src/klipper/printer.cfg:13` | `[mcu] serial` | `PLACEHOLDER` | Auto-set by `deploy.sh` |
| `src/klipper/printer.cfg:~30` | `rotation_distance` | `40` | Calibrate to pump displacement |
| `src/klipper/printer.cfg:~50` | `run_current` | `0.580` | Tune to motor rating |

| Guide | Location |
|-------|----------|
| Dev bench bring-up | `docs/dev_bench_guide.md` |
| Hardware config & calibration | `docs/config_guide.md` |
| Integration plan (7 stages) | `docs/design/integration_plan.md` |
| Test procedures (TP-01--05) | `docs/design/test_procedures.md` |
| Full task tracker | `todo.md` |
