# Design Specification

**Project:** W26 Cobot Axis -- UR30 External Stepper Axis for Metal Paste Dispensing
**Bolton Step 3:** Preparation of a Specification
**Course:** ME 472 -- Mechatronics, Winter 2026, University of Michigan
**Team:** Willem (Software/EE), Dawood (Mechanical)
**Date:** 2026-02-12
**Status:** Phase 2 Deliverable

---

## 1. Scope

This specification defines the functional, interface, performance, and environmental requirements for an external stepper motor axis that receives commands from a Universal Robots UR30 controller via RTDE and drives a pump for metal paste dispensing. It is derived from the problem analysis (Bolton Step 2, `docs/problem_analysis.md`) and constrains the solution space for detailed design (Bolton Steps 4--7).

Parameters that depend on hardware not yet received (motor, pump, paste) are marked **[TBD]** with acceptable ranges.

---

## 2. Functional Requirements

### 2.1 Extrusion Control

| ID | Requirement |
|----|-------------|
| FR-01 | The system shall drive a stepper motor to extrude metal paste at a commanded rate (mm/s) received via RTDE. |
| FR-02 | The system shall support three extrusion modes: off (0), extrude (1), and retract (2). |
| FR-03 | The system shall accept a commanded extrusion rate in the range 0.0 -- 50.0 mm/s. Upper bound is configurable (`MAX_EXTRUSION_RATE`). |
| FR-04 | The system shall support speed-proportional extrusion, where extrusion rate = K x TCP_speed, with a configurable multiplier K. |
| FR-05 | The system shall clamp all commanded rates to `MAX_EXTRUSION_RATE` before issuing motor commands. |

### 2.2 Status Reporting

| ID | Requirement |
|----|-------------|
| FR-06 | The system shall report stepper status (idle, running, error, homing) to the UR30 via RTDE input registers at the bridge loop rate. |
| FR-07 | The system shall report a numeric error code (0=none, 1=comms_lost, 2=stall_detected, 3=thermal_fault) to the UR30 via RTDE. |
| FR-08 | The system shall report the actual extrusion rate (mm/s) to the UR30 via RTDE. |
| FR-09 | The system shall assert a ready flag when the stepper is enabled, Klipper is connected, and RTDE is active. |
| FR-10 | The system shall assert a fault flag when any error condition is active. |

### 2.3 Safety and Emergency Stop

| ID | Requirement |
|----|-------------|
| FR-11 | The system shall halt stepper motion within one RTDE cycle (2 ms) of the software e-stop bit being asserted by the UR30. |
| FR-12 | The system shall disable the stepper driver and set status to error when e-stop is received. |
| FR-13 | The system shall implement a watchdog: if no valid RTDE data is received for 500 ms (configurable), the stepper shall be stopped and the fault flag asserted. |
| FR-14 | The system shall stop the stepper and report error code 1 (comms_lost) if the Klipper host connection is lost. |

### 2.4 Homing

| ID | Requirement |
|----|-------------|
| FR-15 | The system shall initiate a homing sequence when the home command bit is asserted via RTDE. |
| FR-16 | The system shall report status = 3 (homing) during the homing sequence. |
| FR-17 | The system shall return to status = 0 (idle) upon homing completion. |

### 2.5 Enable / Disable

| ID | Requirement |
|----|-------------|
| FR-18 | The system shall enable the stepper driver only when the enable bit is asserted via RTDE. |
| FR-19 | The system shall disable the stepper driver (de-energize motor windings) when the enable bit is de-asserted. |
| FR-20 | The system shall not accept extrusion commands when the enable bit is FALSE, regardless of mode. |

### 2.6 Mode Switching

| ID | Requirement |
|----|-------------|
| FR-21 | The system shall transition between extrusion modes (off, extrude, retract) without requiring a restart. |
| FR-22 | The system shall decelerate to zero before reversing direction when switching between extrude and retract modes. |

### 2.7 Connection Management

| ID | Requirement |
|----|-------------|
| FR-23 | The system shall automatically attempt to reconnect to the UR30 RTDE interface if the connection is lost, with a configurable retry interval (default 2.0 s). |
| FR-24 | The system shall automatically attempt to reconnect to the Klipper host socket if the connection is lost. |
| FR-25 | The system shall operate as a daemon process, starting automatically on Pi boot via systemd. |

---

## 3. Interface Specifications

### 3.1 RTDE Output Registers (UR30 to Pi)

Written by URScript on the UR30, read by the bridge daemon on the Pi.

| Register | Data Type | Purpose | Range / Values | Units |
|----------|-----------|---------|----------------|-------|
| `output_int_register_0` | INT32 | Extrusion mode command | 0 = off, 1 = extrude, 2 = retract | -- |
| `output_double_register_0` | DOUBLE (64-bit IEEE 754) | Commanded extrusion rate | 0.0 -- 50.0 | mm/s |
| `output_double_register_1` | DOUBLE (64-bit IEEE 754) | Robot TCP speed magnitude | 0.0 -- 1000.0 | mm/s |
| `output_bit_register_64` | BOOL | Extrusion enable | TRUE = enabled, FALSE = disabled | -- |
| `output_bit_register_65` | BOOL | Emergency stop | TRUE = halt immediately | -- |
| `output_bit_register_66` | BOOL | Home stepper command | TRUE = initiate homing | -- |

**Reserved for future use:** `output_int_register_1` (position target), `output_double_register_2` (TCP Z-height), `output_bit_register_67`.

### 3.2 RTDE Input Registers (Pi to UR30)

Written by the bridge daemon on the Pi, read by URScript on the UR30.

| Register | Data Type | Purpose | Range / Values | Units |
|----------|-----------|---------|----------------|-------|
| `input_int_register_0` | INT32 | Stepper status | 0 = idle, 1 = running, 2 = error, 3 = homing | -- |
| `input_int_register_1` | INT32 | Error code | 0 = none, 1 = comms_lost, 2 = stall_detected, 3 = thermal_fault | -- |
| `input_double_register_0` | DOUBLE (64-bit IEEE 754) | Actual extrusion rate | 0.0 -- 50.0 | mm/s |
| `input_bit_register_64` | BOOL | Stepper ready flag | TRUE = ready to accept commands | -- |
| `input_bit_register_65` | BOOL | Stepper fault flag | TRUE = fault condition active | -- |

**Reserved for future use:** `input_int_register_2` (stepper position), `input_double_register_1` (StallGuard load), `input_double_register_2` (driver temperature), `input_bit_register_66` (homing complete).

### 3.3 RTDE Connection

| Parameter | Value |
|-----------|-------|
| Transport | TCP/IP |
| Port | 30004 |
| Update rate | 500 Hz (2 ms cycle, fixed by UR e-Series controller) |
| Bridge read/write rate | 125 Hz (8 ms cycle) |
| Protocol version | RTDE v2 (UR e-Series) |
| Library | `ur_rtde` (SDU Robotics, C++ with Python bindings) |

### 3.4 Klipper Interface

| Parameter | Value |
|-----------|-------|
| Host-to-klippy transport | Unix domain socket at `/tmp/klippy_uds` |
| Protocol | Klipper JSON-RPC |
| Stepper name | `pump` (matches `[manual_stepper pump]` in `printer.cfg`) |
| Primary commands | `MANUAL_STEPPER STEPPER=pump MOVE=<dist> SPEED=<vel> ACCEL=<accel>` |
| Enable/disable | `MANUAL_STEPPER STEPPER=pump ENABLE={0,1}` |
| Emergency stop | `M112` |
| Status objects | `tmc2209 manual_stepper pump`, `stepper_enable` |

### 3.5 USB Serial (Pi to SKR Pico)

| Parameter | Value |
|-----------|-------|
| Interface | USB 2.0 Full-Speed (12 Mbps) via USB-C |
| Protocol | Klipper binary MCU protocol |
| Device path | `/dev/serial/by-id/usb-Klipper_rp2040_<ID>-if00` |
| Cable length | 0.3 -- 1.0 m (shielded recommended) |

### 3.6 Ethernet (UR30 Network)

| Parameter | Value |
|-----------|-------|
| Topology | UR30 controller, Pi, and Pi400 (optional) connected via gigabit switch |
| UR30 IP | Configurable (default 192.168.0.3) |
| Pi IP | Configurable (same subnet as UR30) |
| Cable | Cat5e or Cat6, 1 -- 3 m |

### 3.7 Power Connections

| Connection | Voltage | Source | Destination | Wire Gauge | Protection |
|------------|---------|--------|-------------|------------|------------|
| 24 V main | 24 V DC (23--25 V) | UR30 power block (PWR, GND) | Distribution point | 18 AWG min | 3 A blade fuse, SMBJ24CA TVS |
| 24 V to SKR Pico | 24 V DC | Distribution point | SKR Pico VIN screw terminals | 18 AWG | 100 uF/35 V bulk cap |
| 5.1 V to Pi | 5.1 V DC | Pololu D24V22F5 buck converter | Pi GPIO header pins 2+4, 6 | 22 AWG | 2 A resettable PTC (polyfuse) |
| Motor | 24 V DC (chopper-driven) | SKR Pico E-axis TMC2209 | Stepper motor 4-wire (A1/A2/B1/B2) | Per motor spec | TMC2209 overcurrent protection |

---

## 4. Performance Targets

### 4.1 Latency

| Parameter | Target | Basis |
|-----------|--------|-------|
| End-to-end command latency (UR30 register write to stepper motion onset) | < 20 ms (P95) | At 50 mm/s and 20 ms lag, position error is 1.0 mm -- upper bound for paste dispensing |
| Typical end-to-end latency | 5 -- 10 ms | Per-segment analysis in `docs/latency_analysis.md` |
| RTDE cycle time | 2 ms (fixed) | UR e-Series hardware constraint |
| Bridge processing latency | < 2 ms | Python RTDE receive + translate + socket write |
| Klipper command-to-step latency | < 5 ms (steady-state) | klippy processing + USB serial + MCU queue |
| E-stop response (software) | < 1 RTDE cycle (2 ms) | Bridge daemon processes e-stop bit before any other command |
| Watchdog timeout | 500 ms (configurable) | Conservative; avoids false triggers from scheduling jitter |

### 4.2 Extrusion Position Error

| Scenario | TCP Speed Change | Error at 10 ms Latency | Acceptable |
|----------|-----------------|------------------------|------------|
| Gradual acceleration | 10 to 20 mm/s | 0.1 mm | Yes |
| Moderate acceleration | 0 to 50 mm/s | 0.5 mm | Yes |
| Sudden stop | 50 to 0 mm/s | 0.5 mm | Yes |
| Corner (worst case) | 50 to 0 to 50 mm/s | 1.0 mm | Marginal |

Acceptable position error for metal paste dispensing: < 1.0 mm (bead width 1 -- 5 mm).

### 4.3 Speed and Resolution

| Parameter | Value | Notes |
|-----------|-------|-------|
| Maximum commanded extrusion rate | 50.0 mm/s | Software-limited; configurable |
| Minimum commanded extrusion rate | **[TBD]** -- expected > 0.1 mm/s | Limited by motor low-speed torque and microstepping resolution |
| Microstepping | 16x (configurable up to 256x via TMC2209 UART) | Default in `printer.cfg` |
| Angular resolution (16x, 1.8 deg motor) | 0.1125 deg/microstep (3200 microsteps/rev) | Volumetric resolution depends on pump displacement |
| Stepper acceleration | 200 mm/s^2 (configurable) | Default in `printer.cfg` and `config.py` |
| Maximum motor velocity | **[TBD]** -- limited by motor inductance and 24 V supply | Characterize on hardware receipt |

### 4.4 Accuracy

| Parameter | Target | Notes |
|-----------|--------|-------|
| Commanded vs. actual speed (steady-state) | **[TBD]** -- characterize in Phase 4 | Open-loop stepper; expected < 1% error if no stall |
| Volumetric repeatability | **[TBD]** -- parameterized on pump displacement and paste properties | Characterize experimentally |
| Position tracking (open-loop) | No encoder; acceptable for paste dispensing where slight variation is tolerable | StallGuard stall detection as stretch goal |

---

## 5. Operating Environment

| Parameter | Value | Source |
|-----------|-------|--------|
| Ambient temperature | 15 -- 30 C (indoor university lab) | Problem analysis Section 2 |
| Humidity | 20 -- 60% RH (uncontrolled indoor) | Problem analysis Section 2 |
| Vibration | Moderate -- UR30 arm motion and stepper motor vibration | Stepper and pump mounted at or near end effector |
| EMI | Low to moderate -- stepper PWM chopping (~20 kHz), UR30 servo drives | Shielded USB cable recommended |
| Dust / particulate | Low; metal paste residue possible near nozzle | Electronics enclosed, separated from nozzle |
| Network | Dedicated gigabit Ethernet segment; no competing traffic | Isolated switch for UR30 + Pi + Pi400 |
| Safety classification | Collaborative robot cell; system operates within UR30's force-limited safety envelope | No additional safety-rated hardware required for MVP |

---

## 6. Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| C-01 | Total 24 V current draw shall not exceed 2.0 A continuous (3.5 A burst at 33% duty, 500 ms) | UR30 internal power block rating (UR30 User Manual pp. 82--84) |
| C-02 | The system shall control exactly one stepper motor axis | Project scope -- single external pump axis |
| C-03 | The microcontroller shall be a BigTreeTech SKR Pico V1.0 (RP2040, 85 x 56 mm) | On-hand hardware; selected via trade study (`trades/mcu.md`) |
| C-04 | The Klipper host shall run on standard (non-RT) Raspberry Pi OS Linux | PREEMPT_RT is an optional enhancement; not required for MVP |
| C-05 | The Klipper firmware shall use the `[manual_stepper]` interface, not the standard extruder | Manual stepper provides direct speed/position commands without temperature interlocks |
| C-06 | TMC2209 run current shall not exceed 0.8 A RMS without active cooling, or 1.2 A RMS with active cooling | SKR Pico thermal limits; RSENSE = 0.110 ohm (fixed, soldered) |
| C-07 | Motor cable length shall not exceed 3 m (SKR Pico E-axis to stepper) | Voltage drop and EMI considerations at 24 V |
| C-08 | USB serial cable length shall not exceed 3 m (Pi to SKR Pico) | USB 2.0 Full-Speed specification |
| C-09 | The bridge daemon shall be implemented in Python 3 using the `ur_rtde` library | Chosen per trade study (`trades/comms.md`); Python for rapid development in capstone timeline |
| C-10 | The system shall be powered solely from the UR30 controller power block (no external PSU) unless motor current exceeds the 2 A budget | Self-contained system requirement |

---

## 7. Parameters Awaiting Hardware

The following parameters are unknown pending receipt of the motor, pump, and metal paste. Each is marked with an acceptable range that the design must accommodate. Final values shall be recorded upon receipt and the specification updated accordingly.

| Parameter | Acceptable Range | Impact If Outside Range |
|-----------|-----------------|------------------------|
| Motor rated current (per phase, RMS) | 0.3 -- 1.2 A | > 1.2 A requires active cooling fan or alternative driver board |
| Motor holding torque | > T_pump at target flow rate (**[TBD]**) | Insufficient torque requires gear reduction or different motor |
| Motor step angle | 1.8 deg (200 steps/rev) expected; 0.9 deg acceptable | Affects `rotation_distance` in Klipper config |
| Motor phase resistance | 1.0 -- 10.0 ohm (typical NEMA 17) | Low resistance increases current draw; high resistance limits max speed |
| Motor phase inductance | 1.0 -- 20.0 mH (typical NEMA 17) | High inductance limits max RPM at 24 V |
| Motor body dimensions | NEMA 17 (42.3 x 42.3 mm) or NEMA 14 (35.2 x 35.2 mm) expected | Affects mounting bracket design (Dawood) |
| Motor weight | 0.15 -- 0.40 kg | Affects end-effector payload budget |
| Pump type | Syringe, peristaltic, or progressive cavity | Affects torque profile, flow model, coupling design |
| Pump displacement per revolution | **[TBD]** | Determines `rotation_distance` for volumetric control |
| Pump torque requirement at target flow rate | **[TBD]** | Must be less than motor holding torque with margin |
| Pump weight | **[TBD]** | Affects end-effector payload budget |
| Pump mounting interface | **[TBD]** | Determines bracket design (Dawood) |
| Target flow rate | **[TBD]** | Derived from nozzle diameter, bead width, and TCP speed |
| Metal paste viscosity | **[TBD]** | Affects pump torque requirement and back-pressure |

---

## 8. Power Budget Summary

| Device | Idle (A @ 24 V) | Typical (A @ 24 V) | Peak (A @ 24 V) | Notes |
|--------|-----------------|---------------------|------------------|-------|
| Raspberry Pi (via buck converter, ~90% eff.) | 0.15 | 0.35 | 0.45 | Design current 1.5 A @ 5.1 V |
| SKR Pico (logic, TMC2209 quiescent) | 0.05 | 0.08 | 0.10 | No motor load |
| Stepper motor (via TMC2209) | 0.20 | 0.50 -- 1.00 | 1.00 -- 1.20 | **[TBD]** -- parameterized on motor rated current |
| Cooling fan (optional) | 0.00 | 0.05 | 0.10 | If TMC2209 active cooling is required |
| **Total** | **~0.40** | **~1.00** | **~1.40** | Motor current is dominant variable |
| **UR30 budget** | 2.00 continuous | 2.00 continuous | 3.50 burst | Per UR30 User Manual |
| **Margin** | **1.60** | **1.00** | **2.10** | Adequate under all expected conditions |

If the provided motor's rated current exceeds 1.2 A RMS per phase, the system shall use the UR30's external 24 V input (up to 6 A with added PSU) as a contingency.

---

## 9. Traceability

| Requirement | Source Document |
|-------------|-----------------|
| FR-01 through FR-05 | Problem analysis Section 1 (core problem statement) |
| FR-06 through FR-10 | Register allocation (`docs/register_allocation.md`), problem analysis Section 4 (failure modes) |
| FR-11 through FR-14 | Problem analysis Section 4 (F1, F4), latency analysis |
| FR-15 through FR-17 | Register allocation (home command bit) |
| FR-18 through FR-20 | Register allocation (enable bit design rationale) |
| FR-21, FR-22 | Register allocation (mode constants), bridge daemon `config.py` |
| FR-23 through FR-25 | Problem analysis Section 7.3 (non-RT host), bridge daemon design |
| Section 4 (performance) | Latency analysis (`docs/latency_analysis.md`) |
| Section 6 (constraints) | Problem analysis Sections 2, 5, 6; trade studies |
| Section 7 (TBD parameters) | Problem analysis Section 8 |

---

## 10. Revision History

| Rev | Date | Author | Description |
|-----|------|--------|-------------|
| A | 2026-02-12 | Willem | Initial release -- Phase 2 deliverable. Motor/pump parameters TBD. |
