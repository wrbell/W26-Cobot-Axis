# Stepper Driving Design — Klipper Host to SKR Pico to Motor

> **Project:** W26 Cobot Axis (ME472 Mechatronics Capstone)
> **Author:** Willem (Software/EE)
> **Date:** 2026-02-12
> **Status:** Design — consolidates and justifies the stepper control chain
>
> **Consolidates information from:**
> - `docs/klipper_protocols.md` (Sections 5, 8)
> - `docs/skr_pico_specs.md` (Sections 2–4)
> - `docs/skr_pico_klipper_setup.md` (Sections 2–5)
> - `src/klipper/printer.cfg` (implementation)
> - `docs/design/bridge_enhancements.md` (status feedback limitations)

---

## Table of Contents

1. [Scope](#1-scope)
2. [Design Decision: `manual_stepper` vs `extruder`](#2-design-decision-manual_stepper-vs-extruder)
3. [Hardware: SKR Pico and TMC2209](#3-hardware-skr-pico-and-tmc2209)
4. [Klipper Firmware: Build and Flash](#4-klipper-firmware-build-and-flash)
5. [Klipper Configuration](#5-klipper-configuration)
6. [Host-to-MCU Communication](#6-host-to-mcu-communication)
7. [Step Generation Pipeline](#7-step-generation-pipeline)
8. [Control Interface: G-code Commands](#8-control-interface-g-code-commands)
9. [Status Feedback and Limitations](#9-status-feedback-and-limitations)
10. [Safety Mechanisms](#10-safety-mechanisms)
11. [Calibration Procedure](#11-calibration-procedure)
12. [References](#12-references)

---

## 1. Scope

This document covers the stepper driving subsystem — everything between the Klipper host process (klippy) running on the Pi and the physical stepper motor shaft rotation. This is one link in the full communication chain:

```
UR30 ──RTDE──▶ Pi (bridge daemon) ──Unix socket──▶ klippy ──[THIS DOCUMENT]──▶ SKR Pico ──▶ Stepper ──▶ Pump
```

The upstream interfaces (RTDE and bridge daemon) are documented in `docs/register_allocation.md` and `docs/klipper_protocols.md`. This document focuses on:

- **Why** we chose `[manual_stepper]` over `[extruder]`
- **How** Klipper drives the RP2040 MCU to generate step pulses
- **What** the TMC2209 driver does with those pulses
- **What** status information flows back up the chain
- **What** safety mechanisms protect the hardware

---

## 2. Design Decision: `manual_stepper` vs `extruder`

Klipper offers two configuration approaches for independent stepper control:

| Feature | `[extruder]` | `[manual_stepper]` |
|---------|-------------|-------------------|
| Heater/thermistor required | Yes (mandatory) | No |
| Position/velocity control | Via G1 E-axis moves | Via `MANUAL_STEPPER` G-code |
| Acceleration limits | Shared with toolhead | Independent `velocity` and `accel` params |
| `motion_report` velocity field | Yes (`live_extruder_velocity`) | No |
| TMC2209 UART support | Yes | Yes |
| Homing support | No (E-axis has no endstop) | Yes (optional endstop or sensorless) |
| Enable/disable control | Implicit | Explicit (`ENABLE=0/1`) |
| Pressure advance | Yes | No (not applicable) |

### Decision: `[manual_stepper]` — Selected

**Rationale:**

1. **No heater required.** The `[extruder]` section mandates `heater_pin`, `sensor_type`, `sensor_pin`, PID parameters, and temperature limits. We have no heater or thermistor on the pump. Using `[extruder]` would require either dummy pin assignments or a fake heater section — both are fragile workarounds.

2. **Explicit enable/disable.** The bridge daemon needs to gate stepper power independently (e.g., disable on e-stop, enable on command). `MANUAL_STEPPER STEPPER=pump ENABLE=0/1` provides this directly. With `[extruder]`, enable is managed implicitly by Klipper's idle timeout.

3. **Independent velocity/accel limits.** `[manual_stepper]` has its own `velocity` and `accel` parameters that are not shared with or constrained by the `[printer]` section's `max_velocity`/`max_accel`. This keeps pump tuning isolated.

4. **Homing support.** `[manual_stepper]` can optionally define an `endstop_pin` for homing the pump to a reference position. This is useful if the pump has a physical home switch or if we use TMC2209 sensorless homing (StallGuard).

**Trade-off accepted:** `[manual_stepper]` does not expose a `live_velocity` status object in Klipper. The bridge daemon works around this by polling TMC2209 driver status (standstill flag, StallGuard) rather than tracking real-time velocity. See [Section 9](#9-status-feedback-and-limitations).

---

## 3. Hardware: SKR Pico and TMC2209

### 3.1 Board Selection

The BigTreeTech SKR Pico V1.0 was selected in the MCU trade study (`trades/mcu.md`). Key specs relevant to stepper driving:

| Parameter | Value |
|-----------|-------|
| MCU | RP2040 (dual-core ARM Cortex-M0+, 133 MHz) |
| Stepper drivers | 4x TMC2209 (soldered on-board, UART mode) |
| Input voltage | DC 12–24V (we use 24V from UR controller) |
| Motor connectors | JST-XH 4-pin per axis |
| Dimensions | 85 mm x 56 mm |

Full hardware reference: `docs/skr_pico_specs.md`.

### 3.2 Driver Socket Selection: E-axis

We use the **E (extruder) driver socket** for the pump stepper. This is the most intuitive mapping — it is the socket designed for the extrusion motor in a 3D printer, and our pump serves an analogous function.

**E-axis pin assignments on SKR Pico V1.0:**

| Function | GPIO Pin | Klipper Config |
|----------|----------|----------------|
| Step | gpio14 | `step_pin: gpio14` |
| Direction | gpio13 | `dir_pin: gpio13` |
| Enable | gpio15 | `enable_pin: !gpio15` (active-low) |
| UART RX | gpio9 | `uart_pin: gpio9` |
| UART TX | gpio8 | `tx_pin: gpio8` |
| UART address | 3 | `uart_address: 3` |
| DIAG (StallGuard) | gpio16 | `diag_pin: ^gpio16` (if sensorless homing is used) |

The other three driver sockets (X, Y, Z) are unused. Their steppers will remain disabled by Klipper since they are not defined in `printer.cfg`.

### 3.3 TMC2209 Driver Configuration

The TMC2209 is a stepper motor driver IC from Trinamic (now Analog Devices) that handles the low-level current regulation, microstepping, and diagnostic reporting. Klipper configures it via a single-wire UART bus.

**Key parameters in our configuration:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `run_current` | 0.580 A | Conservative starting point. Board thermal limit without fan is ~0.8A. Single active driver reduces thermal concern. Increase after verifying motor specs and thermals. |
| `hold_current` | 0.400 A | Reduced current when stationary to limit heating. Must be high enough to prevent the pump backdriving. |
| `stealthchop_threshold` | 999999 | StealthChop always enabled (silent operation). For higher torque at speed, set to 0 for SpreadCycle. Tune based on pump load and noise requirements. |
| `microsteps` | 16 | 16 microsteps per full step. With a 200-step motor (1.8-degree), this gives 3200 microsteps per revolution. Higher microstepping (32, 64, 256) is available via TMC2209 but offers diminishing returns and reduces max torque per microstep. |
| `sense_resistor` | 0.110 ohm (default) | On-board RSENSE value. Not set explicitly because Klipper's default matches the hardware. |

**Operating modes:**

- **StealthChop2:** Voltage-mode chopping for silent operation at low-to-moderate speeds. Used during normal extrusion. No audible motor noise.
- **SpreadCycle:** Current-mode chopping for higher torque and better high-speed performance. Noisier. Automatically engaged above `stealthchop_threshold` speed (if set). Our config keeps StealthChop always on.

### 3.4 UART Bus Architecture

All four TMC2209 drivers share a single UART bus (gpio9 RX, gpio8 TX). Each driver has a hardware address set by MS1/MS2 pins on the PCB:

| Driver | Axis | Address | MS1 | MS2 |
|--------|------|---------|-----|-----|
| 0 | X | 0 | LOW | LOW |
| 1 | Z | 1 | HIGH | LOW |
| 2 | Y | 2 | LOW | HIGH |
| 3 | E (pump) | 3 | HIGH | HIGH |

The UART bus is half-duplex with a 1K ohm resistor separating TX and RX on the PDN_UART line. Klipper polls one driver at a time, using the address to select the target. Occasional `Unable to read tmc uart` errors are normal and handled by Klipper's retry logic.

**Critical note:** The 24V power supply must be connected before Klipper can communicate with the TMC2209 via UART. USB 5V alone is insufficient for driver communication (`docs/skr_pico_specs.md` Section 6.5).

---

## 4. Klipper Firmware: Build and Flash

### 4.1 Build Configuration

On the Klipper host (Pi):

```bash
cd ~/klipper
make menuconfig
```

Settings:

```
[*] Enable extra low-level configuration options
    Micro-controller Architecture  --->  Raspberry Pi RP2040
    Processor model                --->  rp2040
    Bootloader offset              --->  No bootloader
    Flash chip                     --->  W25Q080 with CLKDIV 2
    Communication interface        --->  USBSERIAL
```

**Notes:**
- Flash chip: The physical chip is W25Q16 (2 MB), but the `W25Q080 with CLKDIV 2` setting is compatible and is what BTT specifies. Selecting the wrong flash chip produces a non-booting firmware.
- Communication: USB serial is the primary choice. UART (on UART0 GPIO1/GPIO0) is an alternative with slightly lower latency (~0.5ms vs ~1ms) but less convenient for debugging.

```bash
make clean && make
# Produces ~/klipper/out/klipper.uf2
```

### 4.2 Initial Flash (UF2 Bootloader)

1. Install jumper on **Boot** header pins.
2. Press **Reset** button. Board appears as USB mass storage drive `RPI-RP2`.
3. Copy firmware:
   ```bash
   sudo mount /dev/sda1 /mnt
   sudo cp ~/klipper/out/klipper.uf2 /mnt/
   sudo umount /mnt
   ```
4. Board auto-reboots. Remove Boot jumper.
5. Verify:
   ```bash
   ls /dev/serial/by-id/
   # Expected: usb-Klipper_rp2040_XXXXXXXXXXXX-if00
   ```

### 4.3 Subsequent Updates

Once Klipper is running, flash via USB without physical button press:

```bash
sudo service klipper stop
make flash FLASH_DEVICE=/dev/serial/by-id/usb-Klipper_rp2040_XXXXXXXXXXXX-if00
sudo service klipper start
```

**Version mismatch warning:** Host and MCU firmware must be from the same Git commit. After updating Klipper on the Pi, always reflash the SKR Pico. A version mismatch causes `MCU protocol error` at startup.

---

## 5. Klipper Configuration

The complete `printer.cfg` is at `src/klipper/printer.cfg`. The stepper-relevant sections are:

### 5.1 MCU Declaration

```ini
[mcu]
serial: /dev/serial/by-id/usb-Klipper_rp2040_PLACEHOLDER-if00
```

The `PLACEHOLDER` is replaced with the actual serial ID after flashing.

### 5.2 Printer Section

```ini
[printer]
kinematics: none
max_velocity: 100
max_accel: 500
```

`kinematics: none` tells Klipper this is not a printer with XYZ axes. The `max_velocity`/`max_accel` here apply to the toolhead (which doesn't exist); the pump stepper has its own limits in the `[manual_stepper]` section.

### 5.3 Manual Stepper

```ini
[manual_stepper pump]
step_pin: gpio14
dir_pin: gpio13
enable_pin: !gpio15
microsteps: 16
rotation_distance: 40
velocity: 50
accel: 200
```

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `rotation_distance` | 40 mm | Distance the pump advances per full shaft revolution. **Must be calibrated** against the actual pump — see [Section 11](#11-calibration-procedure). |
| `velocity` | 50 mm/s | Default maximum speed for `MANUAL_STEPPER MOVE=...` commands. |
| `accel` | 200 mm/s^2 | Acceleration limit. Prevents instantaneous speed changes that could cause missed steps or mechanical shock. |

With a 200-step motor and 16 microsteps: 3200 microsteps/rev, and `rotation_distance: 40` gives **0.0125 mm per microstep**.

### 5.4 TMC2209 Driver

```ini
[tmc2209 manual_stepper pump]
uart_pin: gpio9
tx_pin: gpio8
uart_address: 3
run_current: 0.580
hold_current: 0.400
stealthchop_threshold: 999999
```

See [Section 3.3](#33-tmc2209-driver-configuration) for parameter rationale.

---

## 6. Host-to-MCU Communication

### 6.1 Physical Layer

The Pi connects to the SKR Pico via USB-C cable. The RP2040's USB 2.0 Full-Speed interface (12 Mbps) presents as a CDC-ACM virtual serial port at `/dev/serial/by-id/usb-Klipper_rp2040_...-if00`.

### 6.2 Klipper Binary Serial Protocol

Klipper uses a custom binary protocol over the serial link. **This is an internal protocol — the bridge daemon never speaks it directly.** klippy (the host process) handles all translation from G-code to binary MCU commands.

**Message format:**

```
<length:1B> <sequence:1B> <content:variable> <crc16:2B>
```

- Max message size: 64 bytes
- Sequence numbers: 4-bit (0–15), wrapping
- Reliable delivery: ACK/retransmit mechanism
- Commands encoded with variable-length integer (VLQ) encoding

### 6.3 Connection Startup

When klippy connects to the MCU:

1. **Identify:** Host reads the MCU's compiled command dictionary (defines available commands like `queue_step`, `stepper_config`, `set_digital_out`).
2. **Version check:** Host verifies firmware compatibility.
3. **Clock synchronization:** Host periodically sends `get_clock` commands, builds a linear regression model of clock offset and drift. This enables scheduling future events in MCU clock ticks with **microsecond precision**.
4. **Begin commanding:** Host sends timed step commands.

### 6.4 Clock Synchronization Detail

The RP2040 runs a hardware timer as its clock source. The klippy host:
- Measures round-trip time of `get_clock` commands
- Estimates MCU clock offset and drift rate via linear regression
- Translates host-side event times to MCU clock ticks
- Schedules `queue_step` commands at precise MCU tick values

This is what enables microsecond-precision step timing despite running the motion planner on a non-real-time Linux host.

---

## 7. Step Generation Pipeline

This is the core of how a G-code command becomes physical motor rotation:

```
MANUAL_STEPPER STEPPER=pump MOVE=10 SPEED=25
        │
        ▼
  klippy G-code parser
        │
        ▼
  manual_stepper.py module
  (computes move: start_pos → end_pos, velocity, accel)
        │
        ▼
  Klipper move planner
  (trapezoidal velocity profile: accel → cruise → decel)
        │
        ▼
  Step generator
  (converts velocity profile to discrete step times in MCU ticks)
        │
        ▼
  queue_step commands
  (batched binary messages via serial protocol)
        │
        ▼
  RP2040 MCU step queue
  (hardware timer fires step pulses at exact tick values)
        │
        ▼
  GPIO14 (step pin) → TMC2209 → motor coils → shaft rotation
```

### 7.1 The Lookahead Buffer

Klipper pre-queues step commands **~100ms ahead** of real time on the MCU. This is critical:

- **Benefit:** The MCU executes steps from its hardware timer queue, immune to Linux scheduling jitter. Step timing precision is microsecond-level regardless of host load.
- **Cost:** There is a ~100ms latency between issuing a new command and seeing the motor respond to it (for the *first* command). During steady-state streaming, new speed changes propagate through the buffer with a ~5–13ms per-segment latency.
- **Implication for W26:** The bridge daemon must account for this buffer when synchronizing extrusion with UR30 arm motion. The design allows for time-shifting commands (sending extrusion commands slightly ahead of corresponding arm positions) as a future enhancement.

### 7.2 Velocity Profiles

Klipper generates trapezoidal velocity profiles for each move:

```
Speed ▲
      │    ╱‾‾‾‾‾‾╲
      │   ╱  cruise  ╲
      │  ╱     at      ╲
      │ ╱    SPEED=25    ╲
      │╱   (50mm/s max)   ╲
      ┼───────────────────────▶ Time
       accel              decel
      (200 mm/s²)       (200 mm/s²)
```

The `velocity` and `accel` parameters in `[manual_stepper pump]` control the shape of this profile. Klipper automatically generates the acceleration and deceleration ramps — the bridge daemon only specifies the target position and speed.

---

## 8. Control Interface: G-code Commands

The bridge daemon sends these `MANUAL_STEPPER` commands via the klippy Unix socket:

| Command | Purpose | Example |
|---------|---------|---------|
| `MANUAL_STEPPER STEPPER=pump ENABLE=1` | Power on the stepper driver | Called on "enable" command from UR30 |
| `MANUAL_STEPPER STEPPER=pump ENABLE=0` | Power off the driver (motor freewheels) | Called on "disable" or e-stop |
| `MANUAL_STEPPER STEPPER=pump MOVE=<pos> SPEED=<v>` | Move to absolute position at given speed | Primary extrusion command |
| `MANUAL_STEPPER STEPPER=pump SET_POSITION=0` | Zero the current position counter | Called after homing or on "zero" command |
| `MANUAL_STEPPER STEPPER=pump SPEED=<v> ACCEL=<a> MOVE=<pos>` | Move with custom accel | For retraction (fast decel) |

The bridge daemon translates RTDE register values into these commands:

```
RTDE mode=1 (extrude), rate=25.0 mm/s
    → MANUAL_STEPPER STEPPER=pump MOVE=<current_pos + large_distance> SPEED=25.0

RTDE mode=2 (retract), rate=10.0 mm/s
    → MANUAL_STEPPER STEPPER=pump MOVE=<current_pos - retract_distance> SPEED=10.0

RTDE mode=0 (off)
    → MANUAL_STEPPER STEPPER=pump SET_POSITION=<current_pos>
       (stops by setting target = current position)

RTDE estop=true
    → MANUAL_STEPPER STEPPER=pump ENABLE=0
       (immediately de-energizes driver)
```

**Speed-proportional mode:** When the UR30 provides TCP speed via `output_double_register_1`, the bridge daemon computes `extrusion_rate = tcp_speed × multiplier` and optionally applies a non-linear extrusion profile (linear, polynomial, or lookup table — see `src/bridge/extrusion_profile.py`).

---

## 9. Status Feedback and Limitations

### 9.1 What We Can Read Back

| Data Source | Method | Fields | Update Rate |
|-------------|--------|--------|-------------|
| TMC2209 driver status | `objects/query` on klippy socket | `drv_status` (stall flag, standstill, over-temp, open load, short-to-ground, current scale) | ~4 Hz (250ms polling) |
| Stepper enable state | `objects/query` on `stepper_enable` | Which steppers are enabled | On change |
| Position | `MANUAL_STEPPER STEPPER=pump` (no args) | Current position via G-code response | On demand |

### 9.2 What We Cannot Read Back

**`[manual_stepper]` does not expose real-time velocity.** This is a known limitation of Klipper's `manual_stepper` module. The `motion_report.live_extruder_velocity` field only works with `[extruder]` config. With `[manual_stepper]` and `kinematics: none`, this field is always 0.0.

**Workaround (implemented in bridge daemon):**
- The bridge reports the **commanded rate** as "actual rate" to the UR30 via RTDE (`input_double_register_0`).
- The `KlipperStatusPoller` (`src/bridge/klipper_status.py`) polls TMC2209 `drv_status` in a background thread at 4 Hz. The `stst` (standstill) flag indicates whether the motor is actually moving. The `sg_result` (StallGuard) field provides a relative load indicator.
- If the TMC2209 reports standstill but the bridge thinks the motor should be moving, this indicates a stall or lost steps — the bridge sets the fault flag.

### 9.3 TMC2209 Status Fields (from `drv_status`)

| Field | Meaning | W26 Use |
|-------|---------|---------|
| `stst` | Standstill indicator (1 = motor stopped) | Detect unexpected stops |
| `sg_result` | StallGuard4 load value (0–510) | Stall detection; torque proxy (stretch goal) |
| `cs_actual` | Actual motor current scale (0–31) | Verify current delivery |
| `ot` | Overtemperature flag | Thermal fault detection |
| `otpw` | Overtemperature pre-warning | Early thermal warning |
| `ola` / `olb` | Open load on phase A/B | Wiring fault detection |
| `s2ga` / `s2gb` | Short to ground on phase A/B | Wiring fault detection |
| `stealth` | StealthChop mode active | Verify operating mode |

---

## 10. Safety Mechanisms

### 10.1 Klipper MCU Watchdog

The RP2040 Klipper firmware includes a hardware watchdog timer. If host communication is lost for **~5 seconds**, the MCU resets and **disables all outputs** (all steppers de-energize, all GPIOs go to safe state). This is a firmware-level safety that cannot be overridden by software.

### 10.2 Bridge Daemon Watchdog

The bridge daemon's `Watchdog` module (`src/bridge/watchdog.py`) monitors the RTDE timestamp field. If no valid RTDE data arrives within **0.5 seconds**, the watchdog triggers and the bridge daemon:
1. Sends `MANUAL_STEPPER STEPPER=pump ENABLE=0` to stop the stepper.
2. Sets the fault flag in RTDE input registers.
3. Waits for valid RTDE data to resume.

### 10.3 E-stop Path

When `output_bit_register_65` (e-stop) is set by URScript:
1. Bridge daemon immediately sends `MANUAL_STEPPER STEPPER=pump ENABLE=0`.
2. State machine enters `ESTOP` state — stepper cannot be re-enabled without clearing the e-stop flag and sending a new enable command.

This is a **software e-stop** (sub-cycle response at ~2ms). A hardware e-stop via UR30 safety I/O should be added as a secondary safety layer and would cut 24V power directly.

### 10.4 Thermal Protection

The TMC2209 has built-in thermal shutdown at ~150 degrees C and pre-warning at ~120 degrees C. The `KlipperStatusPoller` monitors the `ot` and `otpw` flags and reports them to the bridge daemon. If overtemperature is detected, the bridge daemon sets the error code and fault flag.

### 10.5 Klipper Idle Timeout

`printer.cfg` sets `[idle_timeout] timeout: 3600` (1 hour). If no commands are received for 1 hour, Klipper automatically disables all steppers. During normal operation, the bridge daemon's control loop acts as a continuous keepalive.

---

## 11. Calibration Procedure

The following parameters must be calibrated against the actual pump hardware (TBD on receipt):

### 11.1 `rotation_distance`

This is the most critical parameter. It defines how many millimeters of pump travel correspond to one full shaft revolution.

**Procedure:**
1. Mark the pump plunger/rotor at a reference position.
2. Send `MANUAL_STEPPER STEPPER=pump MOVE=100 SPEED=10` (move 100 "mm").
3. Measure actual travel with calipers.
4. Compute: `rotation_distance = (rotation_distance_current × actual_travel) / commanded_travel`
5. Update `printer.cfg` and repeat until error is < 1%.

For volumetric calibration (ml/rev instead of mm/rev): weigh the dispensed material, convert using known density.

### 11.2 `run_current`

**Procedure:**
1. Start at 0.580 A (current setting).
2. Test extrusion at the expected operating speed.
3. If motor skips steps (audible click, position error), increase by 0.1 A increments.
4. Monitor TMC2209 temperature via `DUMP_TMC STEPPER="manual_stepper pump"`.
5. If `otpw` flag triggers, add active cooling (fan on Fan0 port, gpio17) or reduce current.
6. Board limit without fan: 0.8 A. With fan: ~1.2 A.

### 11.3 `velocity` and `accel`

**Procedure:**
1. Start with `velocity: 50` and `accel: 200`.
2. Test at increasing speeds until the pump mechanism limits are reached (missed steps, excessive vibration, flow rate saturation).
3. Reduce `velocity` to 80% of the maximum achievable speed for margin.
4. Reduce `accel` if the pump mechanism exhibits backlash or overshoot during speed changes.

### 11.4 StealthChop vs SpreadCycle

If the pump requires higher torque at speed:
1. Set `stealthchop_threshold: 0` to use SpreadCycle (noisier but more torque).
2. Or set a threshold speed (in mm/s): StealthChop below, SpreadCycle above.
3. SpreadCycle provides ~10–20% more torque at the cost of audible motor noise.

---

## 12. References

### Internal Documents

| Document | Relevance |
|----------|-----------|
| `docs/skr_pico_specs.md` | Complete hardware pinout, TMC2209 specs, known issues |
| `docs/skr_pico_klipper_setup.md` | Firmware build, flash procedure, UART details |
| `docs/klipper_protocols.md` | Host-MCU binary protocol, step generation, status objects |
| `docs/latency_analysis.md` | Per-segment latency breakdown including MCU link |
| `docs/register_allocation.md` | RTDE registers that carry stepper commands and status |
| `docs/design/bridge_enhancements.md` | TMC2209 status polling design, velocity feedback limitation |
| `src/klipper/printer.cfg` | Implementation of the configuration described here |
| `src/bridge/klipper_status.py` | TMC2209 status poller implementation |
| `trades/mcu.md` | SKR Pico selection rationale |

### External References

- [Klipper `manual_stepper` Config Reference](https://www.klipper3d.org/Config_Reference.html#manual_stepper)
- [Klipper TMC Drivers Guide](https://www.klipper3d.org/TMC_Drivers.html)
- [Klipper MCU Serial Protocol](https://www.klipper3d.org/Protocol.html)
- [TMC2209 Datasheet (Analog Devices)](https://www.analog.com/media/en/technical-documentation/data-sheets/TMC2209_datasheet_rev1.09.pdf)
- [RP2040 Datasheet (Raspberry Pi)](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
- [BTT SKR Pico GitHub (schematics, pinout)](https://github.com/bigtreetech/SKR-Pico)
- [Klipper Reference Config for SKR Pico](https://github.com/Klipper3d/klipper/blob/master/config/generic-bigtreetech-skr-pico-v1.0.cfg)
