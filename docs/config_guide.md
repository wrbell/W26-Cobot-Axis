# Hardware Configuration & Calibration Guide

Configure all hardware-dependent parameters after initial bench bring-up. This guide consolidates calibration procedures from `docs/design/stepper_driving.md` (Section 11), `docs/design/integration_plan.md` (Stages 3–4), and adds URScript/bridge tuning into a single ordered workflow.

---

## 1. Overview

**Prerequisite:** System is running per `docs/dev_bench_guide.md` — Klipper ready, bridge connecting, motor spinning with default values.

Three subsystems to configure, **in this order:**

1. **Klipper** (`src/klipper/printer.cfg`) — motor must move correctly first
2. **Bridge daemon** (`src/bridge/config.py` / CLI flags) — safety limits and extrusion logic
3. **URScript** (`src/urscript/*.script`) — application-level tuning and waypoints

Order matters: Klipper controls the motor directly, so its parameters must be correct before the bridge can meaningfully clamp or scale commands, and URScript values must match the bridge.

---

## 2. Determining Motor Specs Without a Datasheet

The motor is provided without a datasheet. Determine these specs experimentally before tuning config values.

| Spec | How to measure | Used in |
|------|---------------|---------|
| **Step angle** | Disconnect motor from pump. Send `MANUAL_STEPPER STEPPER=pump MOVE=40 SPEED=5` (default `rotation_distance`). If the shaft completes exactly one revolution → 200 steps/rev → 1.8°/step (standard NEMA17). If not, adjust distance and retry. | Verify 200 steps/rev assumption in `printer.cfg` |
| **Rated current** | Unknown — determine empirically (Section 3b). Start at 0.3A and increase. Most NEMA17: 0.5–1.7A. | `run_current` in `printer.cfg` |
| **Coil resistance** | Multimeter across one coil pair (two wires with continuity). Typical NEMA17: 1–8 Ω. | Sanity-check current setting |
| **Coil pairs** | Continuity mode: two wires that beep together = one coil. 4-wire NEMA17 = 2 coils. | Wiring to SKR Pico E-axis connector |
| **Pump displacement** | After coupling motor to pump: dispense into graduated cylinder at known move distance. Calculate ml/rev. | `rotation_distance` calibration |

> **Tip:** If the motor has a label with a part number, search it online — forum posts or supplier listings often have the rated current and step angle even without a formal datasheet.

---

## 3. Klipper Configuration (`src/klipper/printer.cfg`)

Do each step in order. Verify before moving on.

### 3a. MCU Serial Path (line 13)

Auto-handled by `deploy.sh`, but verify:

```bash
grep serial ~/printer_data/config/printer.cfg
ls /dev/serial/by-id/usb-Klipper_rp2040_*
```

The serial ID must match the actual device. If it says `PLACEHOLDER`, update it.

### 3b. Motor Current (lines 44, 48) — No Datasheet Procedure

Without a datasheet, determine safe `run_current` experimentally:

1. **Measure coil resistance** with multimeter (one coil pair). Record as R_coil.
2. **Start low:** set `run_current: 0.300` in `printer.cfg`, restart Klipper.
3. **Test unloaded motion:** `MANUAL_STEPPER STEPPER=pump MOVE=100 SPEED=10`. Motor should spin smoothly.
4. **Increase by 0.1A** and re-test. At each step:
   - `DUMP_TMC STEPPER="manual_stepper pump"` — check for `otpw` (over-temperature pre-warning) flag
   - Touch motor after 30s of continuous motion — should be warm, not too hot to touch (~60°C max)
   - Touch TMC2209 heatsink — target < 80°C
5. **Test under load:** couple motor to pump, apply paste/fluid back-pressure. If motor stalls (stops or skips steps), increase `run_current` by 0.1A.
6. **Find the sweet spot:** lowest current where motor doesn't stall under load, with thermal margin.
   - **Hard limits:** 0.8A without fan, ~1.2A with active cooling (SKR Pico RSENSE = 0.110Ω)
   - **Sanity check:** if R_coil < 2Ω and current > 1.0A, add the cooling fan (Section 3g)
7. **Set `hold_current`** to 50–70% of final `run_current`. Test that pump doesn't backdrive when motor is idle.

Cross-ref: `docs/design/stepper_driving.md` Section 11.2

### 3c. Rotation Distance (line 29)

The most critical calibration value — defines mm of pump travel per motor revolution.

1. Mark pump plunger/rotor at a reference position.
2. `MANUAL_STEPPER STEPPER=pump SET_POSITION=0`
3. `MANUAL_STEPPER STEPPER=pump MOVE=100 SPEED=10`
4. Measure actual travel (mm) or dispensed volume (ml).
5. Calculate: `new_rotation_distance = current_value × (actual / commanded)`
6. Update `printer.cfg`, restart Klipper, repeat until < 1% error.

Example: if `rotation_distance: 40` and you command 100mm but measure 92mm actual, new value = `40 × (92 / 100) = 36.8`.

Cross-ref: `docs/design/stepper_driving.md` Section 11.1

### 3d. Velocity and Acceleration (lines 36–37)

- `velocity: 50` — test at increasing speeds: 5, 10, 25, 50 mm/s. If motor stalls at a speed, that's the mechanical limit. Set `velocity` to 80% of it.
- `accel: 200` — reduce if pump shows backlash or overshoot during speed changes.

Cross-ref: `docs/design/stepper_driving.md` Section 11.3

### 3e. StealthChop vs SpreadCycle (line 49)

| Setting | Behavior |
|---------|----------|
| `stealthchop_threshold: 999999` | Always StealthChop (quiet, lower torque) |
| `stealthchop_threshold: 0` | Always SpreadCycle (louder, higher torque at speed) |
| `stealthchop_threshold: 25` | Hybrid: StealthChop below 25 mm/s, SpreadCycle above |

Start with StealthChop (default). Switch to SpreadCycle if motor stalls under load at speed.

Cross-ref: `docs/design/stepper_driving.md` Section 11.4

### 3f. Direction Pin (line 26)

If motor moves in the wrong direction, add `!` prefix:

```ini
dir_pin: !gpio13
```

Convention: positive MOVE = extrude, negative = retract.

### 3g. Optional: Cooling Fan (lines 86–88)

Uncomment the `[fan]` section if running above 0.8A or in a warm environment:

```ini
[fan]
pin: gpio17
```

Fan0 port on SKR Pico.

### 3h. Optional: StallGuard Threshold

- `printer.cfg` line 58: `poll_interval: 0.05` (20 Hz — usually fine as-is)
- `config.py` line 120: `STALLGUARD_THRESHOLD = 10` (tune after hardware testing)

StallGuard tuning requires running the motor under various loads and speeds. See `docs/design/hitl_plan.md` Stage 4 Amendment for the sweep procedure.

---

## 4. Bridge Daemon Configuration (`src/bridge/config.py`)

### 4a. Network (`--host` / systemd override)

| Environment | Host |
|-------------|------|
| Dev (URSim) | `--host <WINDOWS_IP>` |
| Prod (UR30) | Default `192.168.1.100` |

Already covered in `docs/dev_bench_guide.md` Section 8.

### 4b. Safety Limits (lines 95–96)

```python
MAX_EXTRUSION_RATE = 50.0    # mm/s — must be ≤ printer.cfg velocity
DEFAULT_ACCEL = 200           # mm/s² — must be ≤ printer.cfg accel
```

These values should always be ≤ the Klipper values. The bridge clamps commanded rates to `MAX_EXTRUSION_RATE`, so setting it higher than Klipper's `velocity` just defers the clamp to firmware.

### 4c. Extrusion Multiplier (line 94)

```python
EXTRUSION_MULTIPLIER = 1.0    # only used in bridge-computed speed-sync mode
```

Calibrate via `test_calibration.script` Sub-test A (flow rate vs. speed characterization). Also settable at runtime: `--extrusion-multiplier 0.85`.

### 4d. Extrusion Profiles (`src/bridge/profiles.json`)

After running `test_calibration.script` Sub-test A:

1. Update the `lookup_table` profile with real data points (speed → flow rate pairs).
2. Or fit a polynomial to the data and update `polynomial` coefficients.
3. Select active profile: edit `"active_profile"` in `profiles.json`, or use `--profile lookup_table` CLI flag.

### 4e. StallGuard Threshold (line 120)

```python
STALLGUARD_THRESHOLD = 10    # sg_result below this = stall
```

Too low = false stall detections. Too high = missed real stalls. Tune after hardware testing with the motor under load.

### 4f. Watchdog (line 109)

```python
WATCHDOG_TIMEOUT = 0.5    # seconds
```

Increase to 1.0 if seeing false timeouts on a noisy network. Leave at 0.5 for production.

### 4g. Data Logging (lines 128–134)

Enable for calibration runs: `--log` CLI flag or set `LOG_ENABLED = True`.

For production, change `LOG_DIR` to persistent storage:

```python
LOG_DIR = "/home/pi/w26_logs"
```

---

## 5. URScript Configuration

### 5a. Teach Waypoints (MUST DO)

Three files contain placeholder waypoint poses that **must** be taught on the physical robot:

| File | Lines | Variables |
|------|-------|-----------|
| `test_basic.script` | 41–43 | `START_POSE`, `MID_POSE`, `END_POSE` |
| `test_calibration.script` | 91–93 | `START_POSE`, `MID_POSE`, `END_POSE` |
| `extrusion_control.script` | (uses `movel` inline) | Application-specific |

**Procedure:** Move robot to safe position via teach pendant, record pose (`get_actual_tcp_pose()`), paste into script. The path should be ~100mm total length in a clear region of the workspace.

### 5b. Safety Limit (must match bridge)

| File | Line | Variable |
|------|------|----------|
| `extrusion_control.script` | 26 | `MAX_EXTRUSION_RATE = 50.0` |
| `test_calibration.script` | 35 | `MAX_EXTRUSION_RATE = 50.0` |

Must match `config.py` `MAX_EXTRUSION_RATE`.

### 5c. Extrusion Multiplier (after calibration)

| File | Line | Variable |
|------|------|----------|
| `extrusion_control.script` | 29 | `EXTRUSION_MULTIPLIER = 1.0` |
| `test_calibration.script` | 34 | `EXTRUSION_MULTIPLIER = 1.0` |

Update after running calibration Sub-test A.

### 5d. Retraction Parameters (after calibration)

`test_calibration.script` lines 69–80 define 6 retraction trial configs (distance + speed pairs). After running Sub-test C:

1. Identify which trial stopped dripping fastest.
2. Apply winning distance/speed values to `extrusion_control.script` retraction logic.

### 5e. Calibration Test Speeds

In `test_calibration.script`:

| Lines | Variables | Purpose |
|-------|-----------|---------|
| 46–53 | `SPEED_1` through `SPEED_8` | Flow rate characterization (Sub-test A) |
| 97–100 | `CONST_RATE_1` through `CONST_RATE_4` | Constant-rate gravimetric test (Sub-test B2) |

Adjust ranges if pump can't reach 50 mm/s or if you need finer resolution at low speeds.

---

## 6. Keeping Config in Sync

Three values must match across files. If you change one, change all.

| Parameter | `printer.cfg` | `config.py` | URScript |
|-----------|--------------|-------------|----------|
| Max speed | `velocity: 50` | `MAX_EXTRUSION_RATE = 50.0` | `MAX_EXTRUSION_RATE = 50.0` |
| Acceleration | `accel: 200` | `DEFAULT_ACCEL = 200` | N/A |
| Extrusion multiplier | N/A | `EXTRUSION_MULTIPLIER = 1.0` | `EXTRUSION_MULTIPLIER = 1.0` |

The bridge daemon clamps values to its own limits. Mismatches cause silent clamping — e.g., if URScript commands 60 mm/s but `config.py` caps at 50, the motor runs at 50 with no error.

---

## 7. Quick Reference: Default vs. Calibrated Values

### Klipper (`printer.cfg`)

| Parameter | Line | Default | When to change |
|-----------|------|---------|---------------|
| `serial` | 13 | `PLACEHOLDER` | First deploy (auto by `deploy.sh`) |
| `dir_pin` | 26 | `gpio13` | Motor moves wrong direction → add `!` |
| `rotation_distance` | 29 | `40` | After measuring pump displacement |
| `velocity` | 36 | `50` | After finding stall speed |
| `accel` | 37 | `200` | If pump shows backlash |
| `run_current` | 44 | `0.580` | After thermal/stall testing |
| `hold_current` | 48 | `0.400` | 50–70% of final `run_current` |
| `stealthchop_threshold` | 49 | `999999` | If motor stalls under load at speed |
| `poll_interval` | 58 | `0.05` | Rarely — 20 Hz is a good default |

### Bridge (`config.py`)

| Parameter | Line | Default | When to change |
|-----------|------|---------|---------------|
| `EXTRUSION_MULTIPLIER` | 94 | `1.0` | After calibration Sub-test A |
| `MAX_EXTRUSION_RATE` | 95 | `50.0` | Match to `printer.cfg` velocity |
| `DEFAULT_ACCEL` | 96 | `200` | Match to `printer.cfg` accel |
| `WATCHDOG_TIMEOUT` | 109 | `0.5` | False timeouts → increase to 1.0 |
| `STALLGUARD_THRESHOLD` | 120 | `10` | After StallGuard hardware testing |
| `LOG_ENABLED` | 128 | `False` | Enable for calibration runs |
| `LOG_DIR` | 129 | `/tmp/w26_logs` | Production → `/home/pi/w26_logs` |

### URScript

| Parameter | File | Line(s) | Default | When to change |
|-----------|------|---------|---------|---------------|
| `MAX_EXTRUSION_RATE` | `extrusion_control.script` | 26 | `50.0` | Match to `config.py` |
| `EXTRUSION_MULTIPLIER` | `extrusion_control.script` | 29 | `1.0` | After calibration |
| `MAX_EXTRUSION_RATE` | `test_calibration.script` | 35 | `50.0` | Match to `config.py` |
| `EXTRUSION_MULTIPLIER` | `test_calibration.script` | 34 | `1.0` | After calibration |
| `START/MID/END_POSE` | `test_basic.script` | 41–43 | Placeholder | Teach on real robot |
| `START/MID/END_POSE` | `test_calibration.script` | 91–93 | Placeholder | Teach on real robot |
| `SPEED_1`–`SPEED_8` | `test_calibration.script` | 46–53 | 2–50 | Adjust for pump range |
| Retraction trials | `test_calibration.script` | 69–80 | 6 configs | After Sub-test C |

---

## 8. Verification Checklist

After completing all configuration:

- [ ] `DUMP_TMC STEPPER="manual_stepper pump"` — no error flags (`otpw`, `ot`, `s2ga/b`, `ola/b`)
- [ ] Motor moves correct direction at commanded speed
- [ ] `rotation_distance` calibrated to < 1% error
- [ ] Bridge connects to UR (real or URSim) and shows running status
- [ ] `test_basic.script` Sub-tests A–F pass
- [ ] `test_calibration.script` Sub-test A run, data recorded
- [ ] Commit updated `printer.cfg` and `config.py` with calibrated values

---

## Related Documents

| Topic | Location |
|-------|----------|
| Bench bring-up (prerequisite) | `docs/dev_bench_guide.md` |
| Stepper driving design + calibration theory | `docs/design/stepper_driving.md` (Section 11) |
| Integration plan (Stages 3–4) | `docs/design/integration_plan.md` |
| StallGuard HITL test plan | `docs/design/hitl_plan.md` |
| Register allocation | `docs/register_allocation.md` |
| SKR Pico hardware specs | `docs/skr_pico_specs.md` |
