# Bolton Step 2: Problem Analysis

**Project:** W26 Cobot Axis -- UR30 External Stepper Axis for Metal Paste Dispensing
**Course:** ME 472 -- Mechatronics, Winter 2026, University of Michigan
**Team:** Willem (Software/EE), Dawood (Mechanical)
**Date:** 2026-02-12
**Design process reference:** Bolton, *Mechatronics*, 7th Ed., Chapter 1 -- Step 2: Analysis of the Problem

---

## 1. The True Nature of the Problem

The Universal Robots UR30 is a 6-axis collaborative robot. Its controller provides closed-loop servo control of the six internal joints but has **no native mechanism to command an external actuator as a coordinated axis of motion**. For metal paste dispensing (additive manufacturing / directed energy deposition), the robot must move along a toolpath while simultaneously driving a pump at a flow rate synchronized to the TCP (tool center point) velocity. If extrusion rate does not track TCP speed, the deposited bead will be under-filled (starved) during acceleration and over-filled (blobbed) during deceleration.

The UR30 controller cannot natively:

- Generate step/direction signals for an external stepper motor.
- Execute closed-loop velocity control of an external actuator.
- Synchronize an external motion axis to its internal trajectory planner at the servo-loop level.

The only outward-facing real-time data path is the RTDE interface (TCP port 30004, 500 Hz on e-Series). RTDE exposes general-purpose registers (48 INT32, 48 DOUBLE, 64 BOOL per direction) that URScript can read and write each 2 ms cycle. These registers carry no motion semantics -- they are raw numbers. All coordination logic must be implemented externally.

**The core problem is therefore:** design and build an external system that receives high-level extrusion commands from the UR30 via RTDE, translates them into precise stepper motor motion, drives a pump for metal paste dispensing, and reports status back -- all with end-to-end latency low enough to maintain acceptable bead quality.

---

## 2. Environmental Constraints

The system operates in a university robotics lab with a UR30 cobot cell.

| Constraint | Value / Description |
|------------|---------------------|
| Ambient temperature | 15--30 C (indoor lab, not climate-controlled in summer) |
| Vibration | Moderate -- UR30 arm motion induces vibration at the end effector and in nearby structures; stepper motor itself generates mechanical vibration |
| Electromagnetic interference | Low to moderate -- stepper PWM chopping at ~20 kHz, UR30 servo drives, lab bench equipment |
| Dust / particulate | Low (indoor lab), but metal paste residue is possible near the nozzle |
| Humidity | Uncontrolled indoor; assumed 20--60% RH |
| Network environment | Dedicated gigabit Ethernet segment between UR30 and Pi; no competing traffic expected |
| Safety | UR30 operates in collaborative mode with force-limited stopping; external stepper axis must not create hazards beyond the cobot's safety envelope |
| Accessibility | Electronics enclosure must be accessible for debugging during Phase 3/4 without disassembling the robot tooling |

---

## 3. Performance Requirements

### 3.1 Latency

| Parameter | Requirement | Basis |
|-----------|-------------|-------|
| End-to-end command latency (UR30 register write to stepper motion onset) | < 20 ms typical | At 50 mm/s TCP speed and 20 ms lag, extrusion position error is 1.0 mm -- the upper bound of acceptability for large-nozzle paste dispensing |
| RTDE communication cycle | 2 ms (500 Hz, fixed by UR30 e-Series controller) | Hardware constraint |
| Klipper lookahead buffer | ~100 ms (configurable) | Klipper pre-queues step events; introduces inherent latency between command issuance and physical motion. Must be characterized and potentially compensated via time-shifting. |
| Target typical latency | 5--10 ms | Analysis in `docs/ur_rtde.md` Section 6.2 estimates ~10 ms typical through the full chain |

### 3.2 Torque and Speed

**TBD -- parameterized on receipt of hardware.** The pump and motor will be provided to the team. The following parameters must be measured or obtained from datasheets once hardware is received:

| Parameter | Symbol | Unit | Status |
|-----------|--------|------|--------|
| Motor holding torque | T_hold | N-m | TBD -- from motor datasheet |
| Motor rated current (per phase) | I_rated | A (RMS) | TBD -- must be <= 1.2 A for SKR Pico TMC2209 with active cooling |
| Motor step angle | theta_step | degrees | TBD -- expected 1.8 (200 steps/rev) |
| Motor phase resistance | R_phase | ohm | TBD -- from motor datasheet |
| Motor phase inductance | L_phase | mH | TBD -- from motor datasheet |
| Pump torque requirement at target flow rate | T_pump | N-m | TBD -- characterize on receipt; depends on paste viscosity and back-pressure |
| Required speed range (motor RPM) | n_min, n_max | RPM | TBD -- derived from pump displacement and target flow rate |
| Target flow rate | Q | mL/min or cc/min | TBD -- depends on nozzle diameter, bead geometry, and paste properties |

**Design constraint:** The TMC2209 drivers on the SKR Pico V1.0 can deliver up to ~1.2 A RMS per phase with active cooling (0.8 A without). If the provided motor exceeds this, active cooling must be added or an alternative driver board must be sourced. The RSENSE value is 110 milliohm (fixed, soldered).

### 3.3 Precision

| Parameter | Requirement | Notes |
|-----------|-------------|-------|
| Microstepping | 16x minimum (configurable up to 256x via TMC2209 UART) | Higher microstepping improves resolution but reduces available torque at speed |
| Angular resolution (at 16x, 1.8 deg motor) | 0.1125 deg/microstep (3200 microsteps/rev) | Volumetric resolution depends on pump displacement per revolution -- TBD |
| Volumetric repeatability | TBD -- parameterized on pump displacement and paste properties | Paste dispensing tolerances are generally more forgiving than FDM filament extrusion |
| Position tracking error (steady-state) | Open-loop stepper; no encoder feedback unless Stallguard is used as a proxy for stall detection | Acceptable for paste dispensing where slight volumetric variation is tolerable |

---

## 4. Failure Modes

| # | Failure Mode | Cause | Effect | Severity | Detection Method | Mitigation |
|---|-------------|-------|--------|----------|-----------------|------------|
| F1 | **Loss of RTDE connection** | Network cable disconnect, UR30 power cycle, switch failure | Extrusion commands stop; last-received speed persists until timeout | High -- uncontrolled extrusion or starvation | RTDE library reports connection loss; bridge daemon timeout on missing packets | Bridge daemon implements watchdog: if no RTDE packet received within N cycles (configurable, e.g., 50 ms), command stepper to stop. Write error code to `input_int_register_1`. |
| F2 | **Stepper motor stall** | Torque demand exceeds motor capability (paste too viscous, pump jammed, mechanical binding) | Motor loses steps; extrusion volume is less than commanded; potential damage to coupling | High -- under-extrusion, possible mechanical damage | Stallguard4 on TMC2209 (stretch goal); alternatively, monitor actual vs. commanded velocity via Klipper status | Set `driver_SGTHRS` threshold; on stall detection, disable stepper, set fault flag (`input_bit_register_65`), report error code 2 to UR30 |
| F3 | **24V power fault** | UR30 power block overload (>2 A continuous), loose wiring, blown fuse | All electronics lose power; stepper stops immediately; Pi performs unclean shutdown | Critical -- abrupt halt, potential SD card corruption | Fuse on 24V input line; UR30 monitors power block current | Size total draw to stay within 2 A continuous; add bulk capacitor for transient ride-through; use journaling filesystem on Pi SD card |
| F4 | **Klipper host crash** | Software bug, kernel panic, OOM on Pi, SD card failure | Stepper stops (MCU enters shutdown state when host communication is lost) | High -- extrusion halts mid-path | Klipper MCU detects host timeout and disables steppers; bridge daemon loses klippy socket connection | Bridge daemon detects klippy disconnect, sets stepper status to error (code 1) in RTDE, URScript reads status and halts robot motion |
| F5 | **USB serial disconnect (Pi to SKR Pico)** | Cable unseated, USB hub failure, EMI-induced enumeration reset | Klipper reports MCU communication error; stepper stops | High -- same as F4 | Klipper reports `mcu 'mcu': Unable to connect` or `Lost communication with MCU` | Secure USB cable mechanically; use short, shielded cable; Klipper firmware_restart can attempt recovery |
| F6 | **Thermal fault on TMC2209** | Sustained high-current operation without adequate cooling | Driver enters thermal shutdown; stepper stops | Medium -- temporary halt; self-recovering after cooldown | TMC2209 reports thermal flag via UART; Klipper reads `drv_status` | Active cooling fan on SKR Pico heatsink; set `run_current` conservatively; monitor driver temperature via Klipper status object |
| F7 | **Extrusion command desynchronization** | Latency spike in RTDE or Klipper chain causes extrusion rate to lag behind TCP speed change | Over- or under-extrusion at path corners and speed transitions | Low to Medium -- cosmetic defect in deposited bead | Compare commanded vs. actual extrusion rate in bridge daemon logs | Characterize latency during Phase 4 testing; implement time-shifting compensation if needed; use `target_TCP_speed` (predictive) instead of `actual_TCP_speed` (reactive) |

---

## 5. Physical Constraints

### 5.1 UR30 Payload and Mounting

| Parameter | Value | Source |
|-----------|-------|--------|
| UR30 rated payload | 30 kg | UR30 datasheet |
| UR30 reach | 1300 mm | UR30 datasheet |
| Tool flange interface | ISO 9409-1-50-4-M6 (4x M6 on 50 mm bolt circle) | UR30 User Manual |
| Existing tooling weight | TBD -- measure in lab | Must be subtracted from available payload budget |

### 5.2 Component Weights (Estimated)

| Component | Estimated Weight | Notes |
|-----------|-----------------|-------|
| SKR Pico V1.0 | ~38 g | 85 x 56 mm, 4-layer PCB |
| Raspberry Pi (headless, model TBD) | 45--46 g (Pi 4B) | Depends on model selected |
| Stepper motor (NEMA 17 class) | 240--350 g | TBD -- parameterized on receipt of hardware |
| Pump | TBD | Parameterized on receipt of hardware |
| Enclosure (3D printed) | TBD | Depends on design; estimate 100--200 g for PLA/PETG |
| Cabling (power + signal + USB + Ethernet) | TBD | Depends on routing and lengths |
| Buck converter(s) | ~5--10 g each | Small module |
| **Subtotal (electronics only, no motor/pump)** | **~300--400 g** | Well within payload budget |

The motor and pump weight will dominate. Even a heavy pump assembly (e.g., 2--3 kg) is far below the 30 kg payload capacity, so payload is not expected to be a binding constraint. The primary physical concern is the **mounting envelope** and **cable routing**, not weight.

### 5.3 Mounting Options

| Location | Pros | Cons |
|----------|------|------|
| End effector (tool flange) | Shortest motor-to-pump coupling; pump at TCP for direct paste application | Adds inertia to wrist; all cables route along arm; vibration exposure highest |
| Robot base / pedestal | Stationary; easy access; no vibration from arm motion | Long mechanical coupling to pump (tubing or cable drive); introduces compliance and latency in paste delivery |
| Nearby table / enclosure | Stationary; ample space; easy access | Same coupling issues as base mount; cable management across workspace |

**Recommended approach:** Mount the pump and motor at or near the end effector (essential for direct paste dispensing). Mount the electronics enclosure (Pi, SKR Pico, buck converters) at the robot base or on a nearby surface to reduce end-effector weight and simplify cable management. Connect via USB cable (Pi to SKR Pico) and motor cable (SKR Pico to stepper) routed along the robot arm.

### 5.4 Cable Routing

| Cable | Length (est.) | Notes |
|-------|--------------|-------|
| Ethernet (UR30 controller to Pi) | 1--3 m | Through gigabit switch; standard Cat5e/Cat6 |
| USB (Pi to SKR Pico) | 0.3--1 m | Depends on whether SKR Pico is co-located with Pi or mounted separately |
| Motor cable (SKR Pico to stepper) | 1--3 m | 4-wire; voltage drop at 24V is negligible for these lengths |
| 24V power (UR30 power block to distribution) | 1--2 m | 18 AWG minimum for 2 A |
| 5V power (buck converter to Pi) | 0.1--0.3 m | Short; co-located |

All cable lengths are estimates pending physical measurements in the lab.

---

## 6. Power Constraints

### 6.1 Source

The UR30 Controller Box power block provides the sole 24V source (system must be self-contained, powered from the robot controller).

| Parameter | Value | Source |
|-----------|-------|--------|
| Internal 24V supply | 2 A continuous, 3.5 A burst (500 ms at 33% duty) | UR30 User Manual pp. 82--84 |
| External 24V option | Up to 6 A (with added external PSU to power block lower terminals) | UR30 User Manual |
| Voltage range (internal) | 23--25 V | UR30 User Manual |

### 6.2 System Power Budget

| Device | Current from 24V | Power (W) | Notes |
|--------|------------------|-----------|-------|
| Pi (headless, via buck at ~90% eff.) | ~0.35 A | ~8.5 W | Design current 1.5 A at 5.1 V |
| SKR Pico (logic, no motor) | ~0.08 A | ~1.9 W | Board quiescent |
| Stepper motor (via TMC2209) | 0.5--1.0 A | 12--24 W | TBD -- parameterized on motor rated current and load |
| **Total typical** | **~1.0 A** | **~24 W** | Single Pi architecture (no slave Pi) |
| **Total peak** | **~1.4 A** | **~34 W** | Motor acceleration transient |

**Note:** The earlier architecture included a slave Pi as a serial bridge. Per Klipper research (`docs/klipper_protocols.md` Section 9.5), the slave Pi is unnecessary -- the Klipper host connects directly to the SKR Pico via USB serial. Removing the slave Pi saves ~0.12 A at 24 V and simplifies the power budget. The Pi400 is retained as an **optional** HMI / development terminal and is not included in the power budget (it is powered independently or not present in the production configuration).

### 6.3 Margin

| Scenario | 24V Draw | Margin vs. 2 A Continuous |
|----------|----------|---------------------------|
| Idle (motor holding) | ~0.5 A | 1.5 A |
| Normal extrusion | ~1.0 A | 1.0 A |
| Peak (acceleration) | ~1.4 A | 0.6 A |

The system operates within the UR30 internal 24V budget under all expected conditions. The 3.5 A burst rating provides additional headroom for transient motor loads. An external 24V supply is available as a fallback if the provided motor draws more than anticipated.

---

## 7. Communication Constraints

### 7.1 RTDE Register Limits

| Resource | Available | Used by W26 (current allocation) | Remaining |
|----------|-----------|----------------------------------|-----------|
| Output INT32 registers (UR30 to Pi) | 48 | 1 (extrusion mode) | 47 |
| Output DOUBLE registers (UR30 to Pi) | 48 | 2 (extrusion rate, TCP speed) | 46 |
| Output BOOL registers (UR30 to Pi) | 64 | 3 (enable, e-stop, home) | 61 |
| Input INT32 registers (Pi to UR30) | 48 | 2 (stepper status, error code) | 46 |
| Input DOUBLE registers (Pi to UR30) | 48 | 1 (actual extrusion rate) | 47 |
| Input BOOL registers (Pi to UR30) | 64 | 2 (ready flag, fault flag) | 62 |

Register allocation is minimal (6 output, 5 input) with ample headroom for expansion. Full allocation is documented in `docs/register_allocation.md`.

### 7.2 RTDE Timing

| Parameter | Value |
|-----------|-------|
| RTDE output stream rate | 500 Hz (2 ms cycle), fixed by e-Series controller |
| Client write rate | Asynchronous; applied on next controller cycle |
| Round-trip latency (write input, read next output) | 2--5 ms typical |
| Stale data behavior | If bridge daemon misses a cycle, UR30 continues with last-received input values |

### 7.3 Non-Real-Time Host

The Raspberry Pi runs standard Linux (Raspberry Pi OS), which is **not a real-time operating system**. Scheduling jitter of 1--10 ms is possible under load. Implications:

- The bridge daemon's RTDE read/write loop may occasionally miss a 2 ms cycle. This is acceptable because the UR30 continues with the last-received values and the next cycle catches up.
- Klipper mitigates host jitter through its ~100 ms lookahead buffer: step events are pre-computed and queued on the MCU well ahead of their execution time, so MCU-level step timing is microsecond-precise regardless of host scheduling.
- If jitter proves problematic, PREEMPT_RT kernel patches can be applied (Klipper documentation recommends this for all hosts).

### 7.4 Klipper Command Path

| Segment | Interface | Estimated Latency |
|---------|-----------|-------------------|
| Bridge daemon to klippy | Unix socket (`/tmp/klippy_uds`), JSON | < 0.5 ms |
| klippy processing + motion planning | Internal | 1--5 ms |
| klippy to SKR Pico MCU | USB-CDC serial (12 Mbps), Klipper binary protocol | < 1 ms |
| MCU step execution from queue | Hardware timer ISR | < 0.001 ms (microsecond precision) |

The dominant latency contributor in the Klipper chain is the lookahead buffer (~100 ms), not the command transport. This buffer is a design choice (trading latency for step timing precision) and may be tunable for this application.

---

## 8. Parameters Awaiting Hardware Receipt

The pump and stepper motor will be provided to the team. The following table summarizes all design parameters that are currently unknown and will be filled in upon receipt of hardware.

| Parameter | Needed For | How to Obtain |
|-----------|-----------|---------------|
| Motor model number | Datasheet lookup, Klipper config | Read nameplate |
| Motor rated voltage | Verify compatibility with 24V TMC2209 chopper drive | Motor datasheet |
| Motor rated current (per phase, RMS) | Set `run_current` in Klipper TMC2209 config; verify <= 1.2 A for SKR Pico | Motor datasheet |
| Motor holding torque | Verify sufficient to drive pump at target flow rate | Motor datasheet |
| Motor step angle | Calculate microsteps/rev, set `rotation_distance` in Klipper | Motor datasheet |
| Motor phase resistance | Power dissipation calculation, current chopping analysis | Motor datasheet |
| Motor phase inductance | Maximum speed estimate (L limits dI/dt at high RPM) | Motor datasheet |
| Motor shaft diameter | Coupling design (Dawood) | Measure / datasheet |
| Motor body dimensions and weight | Mount design, payload budget | Measure / datasheet |
| Pump type (syringe, peristaltic, progressive cavity) | Torque profile, flow rate model, coupling design | Inspect on receipt |
| Pump displacement per revolution | Calculate `rotation_distance` for volumetric control | Pump datasheet or measure |
| Pump torque requirement vs. flow rate | Verify motor torque is sufficient; set current limit | Characterize experimentally |
| Pump mounting interface | End-effector bracket design (Dawood) | Measure on receipt |
| Pump weight | Payload budget | Weigh on receipt |
| Metal paste viscosity and working temperature | Flow rate model, latency tolerance assessment | Paste supplier datasheet |

---

## 9. Summary of Key Problem Characteristics

| Characteristic | Description |
|----------------|-------------|
| **System type** | Mechatronic: embedded computing + power electronics + mechanical coupling + real-time communication |
| **Primary challenge** | Bridging the UR30's register-based RTDE interface to precise stepper motor control with low enough latency for synchronized paste dispensing |
| **Critical constraint** | End-to-end latency must remain below ~20 ms for acceptable bead quality at typical TCP speeds (10--50 mm/s) |
| **Power constraint** | 2 A continuous at 24 V from UR30 internal supply; system draws ~1.0 A typical |
| **Communication constraint** | Non-real-time Linux host; mitigated by Klipper's MCU-side step buffering |
| **Physical constraint** | Motor and pump at end effector; electronics at robot base; cables routed along arm |
| **Primary unknowns** | Motor and pump specifications (provided hardware, not yet received); metal paste properties |
| **Highest-risk failure mode** | Loss of RTDE connection (F1) -- requires watchdog timeout and graceful stop |

This problem analysis informs the design specification (Bolton Step 3) and constrains the solution space for Step 4 (generation of possible solutions). The architecture selected in the Klipper vs. Lingua Franca trade study (`trades/lingua_franca_vs_klipper.md`) is consistent with the constraints identified here.
