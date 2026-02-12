# BigTreeTech (BTT) Pico + Klipper Firmware: Comprehensive Research

> **Project context:** W26 Cobot Axis -- using a BTT Pico (RP2040-based) as the stepper motor
> controller for a 7th-axis extrusion system on a UR30 collaborative robot, driven via
> Klipper firmware with a Raspberry Pi 400 host.
>
> **Date:** 2026-02-12
>
> **Note on sources:** URLs are provided throughout. Because this document was compiled
> from cached training knowledge (not live web fetches), the reader should verify links
> and check for any updates published after May 2025.

---

## Table of Contents

1. [Board Variants and Specifications](#1-board-variants-and-specifications)
2. [Flashing Klipper Firmware onto a BTT Pico](#2-flashing-klipper-firmware-onto-a-btt-pico)
3. [Serial Communication: USB vs UART](#3-serial-communication-usb-vs-uart)
4. [TMC Stepper Driver Support and Stallguard](#4-tmc-stepper-driver-support-and-stallguard)
5. [Klipper Configuration Examples](#5-klipper-configuration-examples)
6. [Known Issues and Gotchas](#6-known-issues-and-gotchas)
7. [Relevance to W26 Project Architecture](#7-relevance-to-w26-project-architecture)
8. [References and Links](#8-references-and-links)

---

## 1. Board Variants and Specifications

### 1.1 BTT Pico v1.0

The **BIGTREETECH Pico v1.0** is a compact 3D printer control board built around the
Raspberry Pi RP2040 microcontroller. It is designed specifically for small 3D printers
(Voron V0, Salad Fork, etc.) and is one of the first RP2040-based boards in the 3D
printing ecosystem with onboard TMC stepper drivers.

**Key Specifications:**

| Parameter | Value |
|---|---|
| MCU | Raspberry Pi RP2040 (dual-core ARM Cortex-M0+, 133 MHz) |
| Flash | 2 MB onboard flash (W25Q16) |
| RAM | 264 KB SRAM |
| Input Voltage | DC 12V-24V |
| Logic Voltage | 3.3V |
| Stepper Drivers | 4x onboard TMC2209 (UART mode) |
| Motor Outputs | 4 stepper outputs (X, Y, Z, E) |
| Heated Bed MOSFET | 1x (up to 10A continuous) |
| Hotend MOSFET | 1x |
| Fan Ports | 3x controllable fan ports (2 PWM + 1 always-on, or 3 PWM depending on config) |
| Thermistor Inputs | 2x (NTC 100K) |
| Endstop/Probe Ports | 3x endstop + 1x probe (configurable) |
| USB | USB-C (for firmware flash and serial communication) |
| UART Header | Dedicated UART header for Raspberry Pi serial connection |
| Neopixel | 1x onboard RGB LED (active data out pin for chaining) |
| Expansion | SPI, I2C headers; ADXL345 header for input shaping |
| Board Dimensions | Approximately 100mm x 72mm |
| Firmware Support | Klipper (primary), Marlin (limited) |

**Onboard TMC2209 Details:**

- All four stepper drivers are TMC2209 in UART mode by default.
- Each driver shares a single UART bus with individual address pins (allowing
  independent configuration of each driver via UART addressing).
- Stallguard4 (SG4) is supported by the TMC2209 silicon, and the DIAG pins are
  exposed (active-low, directly routed to endstop connector pads with optional
  jumper).
- Run current is configurable up to ~1.2A RMS per driver (the board's thermal
  design limits continuous current; the TMC2209 itself supports up to 2A peak).
- Stealthchop2 and Spreadcycle modes are software-selectable via Klipper.

**Pinout highlights (v1.0):**

- Stepper UART TX/RX: Single shared UART line (typically gpio9) with addresses 0-3.
- X-step: gpio11, X-dir: gpio10, X-enable: gpio12
- Y-step: gpio6, Y-dir: gpio5, Y-enable: gpio7
- Z-step: gpio19, Z-dir: gpio28, Z-enable: gpio2
- E-step: gpio14, E-dir: gpio13, E-enable: gpio15
- DIAG pins for sensorless homing: gpio4 (X), gpio3 (Y), gpio22 (Z), gpio16 (E)
- Hotend heater: gpio23
- Heated bed: gpio21
- Hotend thermistor: gpio27
- Bed thermistor: gpio26
- Fan0: gpio17, Fan1: gpio18, Fan2: gpio20

> **Note:** Pin numbers here are from the Klipper reference config and the BTT
> schematic. Always cross-reference with the official BTT pinout diagram for your
> specific board revision.

### 1.2 BTT Pico v2.0

As of my knowledge cutoff (May 2025), BigTreeTech had not released a board specifically
branded as "BTT Pico **v2.0**." However, there are closely related boards worth noting:

- **BTT SKR Pico v1.0**: This is essentially the same board sometimes referred to
  under the "SKR Pico" name. BigTreeTech's naming has caused some confusion in the
  community. The repo on GitHub is `bigtreetech/SKR-Pico` (not `BTT-Pico`), but the
  board is commonly called "BTT Pico" in community discussions.
- **BTT Pico v1.0 revisions**: Some sellers list minor PCB revisions (e.g., v1.0.1)
  that fix silk-screen errors or minor routing issues but are functionally identical.

If a v2.0 has been released after May 2025, check the BigTreeTech GitHub organization:
https://github.com/bigtreetech

### 1.3 Related RP2040 Boards from BTT

| Board | MCU | Stepper Drivers | Notes |
|---|---|---|---|
| BTT SKR Pico v1.0 | RP2040 | 4x TMC2209 onboard | Same as "BTT Pico" in most contexts |
| BTT EBB36/42 v1.2 | RP2040 option | 1x TMC2209 | CAN bus toolhead board |
| BTT MMB CAN v1.0 | RP2040 | 4x TMC2209 | Multi-material board |

For the W26 project, the **BTT SKR Pico v1.0 (RP2040 + 4x TMC2209)** is the relevant
board.

---

## 2. Flashing Klipper Firmware onto a BTT Pico

### 2.1 Overview

The RP2040 uses a UF2 bootloader for firmware flashing. This makes the process
straightforward -- no separate programmer or STM32-style DFU mode is needed.

### 2.2 Build Klipper Firmware for RP2040

On the Klipper host (Raspberry Pi 400 in our case):

```bash
cd ~/klipper
make menuconfig
```

**Menuconfig settings for BTT Pico:**

```
Micro-controller Architecture: Raspberry Pi RP2040
Bootloader offset: No bootloader
Flash chip: W25Q080 with CLKDIV 2
Communication interface: USB
    (or: Serial (on UART0 GPIO1/GPIO0) -- see Section 3)
```

> **Important:** Select `USB` for communication if you plan to connect via the USB-C
> port. Select `UART0` if you plan to connect via the dedicated UART header to a
> Raspberry Pi's GPIO serial pins.

Then build:

```bash
make clean
make
```

This produces `~/klipper/out/klipper.uf2`.

### 2.3 Flash via UF2 (USB Boot Mode)

1. **Enter BOOTSEL mode:**
   - Press and hold the `BOOTSEL` button on the BTT Pico.
   - While holding, either plug in the USB cable or press the `RESET` button.
   - Release `BOOTSEL` after the board enumerates.
   - The board appears as a USB mass storage device (named `RPI-RP2`).

2. **Copy the firmware:**
   ```bash
   # If flashing from the Pi400 host directly:
   sudo mount /dev/sda1 /mnt
   sudo cp ~/klipper/out/klipper.uf2 /mnt/
   sudo sync
   sudo umount /mnt
   ```
   Or simply drag-and-drop the `.uf2` file onto the `RPI-RP2` drive if using a
   desktop environment.

3. **Automatic reboot:** The board automatically reboots into Klipper firmware after
   the UF2 file is copied. The USB mass storage device will disappear.

4. **Verify:**
   ```bash
   ls /dev/serial/by-id/
   ```
   You should see something like:
   ```
   usb-Klipper_rp2040_XXXXXXXXXXXX-if00
   ```

### 2.4 Alternative: Flash via `make flash`

If the board is already running Klipper and connected via USB:

```bash
make flash FLASH_DEVICE=/dev/serial/by-id/usb-Klipper_rp2040_XXXXXXXXXXXX-if00
```

This uses the RP2040's USB bootloader re-entry mechanism built into Klipper. The board
will automatically enter BOOTSEL mode, receive the firmware, and reboot.

### 2.5 Flash via `picotool` (Alternative)

```bash
sudo apt install cmake gcc-arm-none-eabi libnewlib-arm-none-eabi build-essential
git clone https://github.com/raspberrypi/picotool.git
cd picotool && mkdir build && cd build
cmake .. && make
sudo ./picotool load ~/klipper/out/klipper.uf2
sudo ./picotool reboot
```

---

## 3. Serial Communication: USB vs UART

### 3.1 USB Serial (Recommended for Most Setups)

When Klipper is compiled with `Communication interface: USB`:

- The BTT Pico appears as `/dev/serial/by-id/usb-Klipper_rp2040_XXXXXXXXXXXX-if00`
  on the host Pi.
- Communication uses USB CDC-ACM (virtual serial port).
- Baud rate is effectively unlimited (USB full-speed, 12 Mbps).
- This is the simplest and most reliable method.

**Klipper `printer.cfg` MCU section:**

```ini
[mcu]
serial: /dev/serial/by-id/usb-Klipper_rp2040_XXXXXXXXXXXX-if00
```

### 3.2 UART Serial (Hardware Serial via GPIO)

When Klipper is compiled with `Communication interface: Serial (on UART0 GPIO1/GPIO0)`:

- The BTT Pico communicates over its UART0 pins (GPIO0 = TX, GPIO1 = RX).
- The board has a dedicated 3-pin UART header for connecting directly to a Raspberry
  Pi's GPIO serial (Pi TX -> Pico RX, Pi RX -> Pico TX, GND -> GND).
- Typical baud rate: 250000.
- This eliminates USB from the communication chain, which can reduce latency and
  avoid USB-related reliability issues (USB disconnect, enumeration delays).

**Klipper `printer.cfg` MCU section:**

```ini
[mcu]
serial: /dev/ttyAMA0
baud: 250000
restart_method: command
```

> **For the W26 architecture**, if the Slave Pi is a Raspberry Pi communicating with
> the BTT Pico, UART serial is the more elegant choice. It avoids USB enumeration
> complexity and provides a direct, low-latency connection. However, USB is perfectly
> fine and arguably easier to debug.

### 3.3 USB vs UART Comparison for W26

| Aspect | USB Serial | UART Serial |
|---|---|---|
| Latency | ~1-2 ms round-trip | ~0.5-1 ms round-trip |
| Reliability | Occasional USB disconnects under electrical noise | Very reliable (hardwired) |
| Wiring | Single USB-C cable | 3 wires (TX, RX, GND) |
| Debug | Easy (standard USB serial tools) | Requires logic analyzer or separate debug path |
| Hot-plug | Supported | Not supported (must be connected at boot) |
| Baud Rate | Effectively unlimited (USB speed) | 250000 baud (configurable) |

### 3.4 RP2040 Dual UART Note

The RP2040 has two hardware UARTs (UART0 and UART1). Klipper uses UART0 for host
communication (if configured). UART1 is not typically used for host communication but
could theoretically be configured for auxiliary purposes.

The TMC2209 driver UART (for configuring stepper parameters) uses a **separate,
bit-banged software UART** on a different GPIO pin -- it does not conflict with the host
communication UART.

---

## 4. TMC Stepper Driver Support and Stallguard

### 4.1 Onboard TMC2209 Drivers

The BTT Pico v1.0 has **four onboard TMC2209** stepper drivers. Key features:

| Feature | TMC2209 |
|---|---|
| Max Current | 2.0A peak / 1.4A RMS (board thermal limits may be lower) |
| Microstep Resolution | Up to 256 microsteps |
| Stealthchop2 | Yes (silent operation below threshold speed) |
| Spreadcycle | Yes (for higher speeds / more torque) |
| Stallguard4 (SG4) | Yes (load detection / sensorless homing) |
| CoolStep | Yes (automatic current reduction) |
| UART Configuration | Yes (single-wire UART with addressing) |
| Internal RSENSE | Yes (default ~0.11 ohm) |

### 4.2 UART Addressing

All four TMC2209 drivers share a single UART line. They are differentiated by their
hardware address pins:

| Driver | UART Address | Typical Axis |
|---|---|---|
| Driver 0 | 0 | X |
| Driver 1 | 1 | Y |
| Driver 2 | 2 | Z |
| Driver 3 | 3 | E (Extruder) |

In Klipper, this is configured with the `uart_address` parameter.

### 4.3 Klipper TMC2209 Configuration

```ini
[tmc2209 stepper_x]
uart_pin: gpio9
tx_pin: gpio8
uart_address: 0
run_current: 0.580
stealthchop_threshold: 999999

[tmc2209 stepper_y]
uart_pin: gpio9
tx_pin: gpio8
uart_address: 1
run_current: 0.580
stealthchop_threshold: 999999

[tmc2209 stepper_z]
uart_pin: gpio9
tx_pin: gpio8
uart_address: 2
run_current: 0.580
stealthchop_threshold: 999999

[tmc2209 extruder]
uart_pin: gpio9
tx_pin: gpio8
uart_address: 3
run_current: 0.650
stealthchop_threshold: 999999
```

> **Note on `uart_pin` and `tx_pin`:** The BTT Pico uses a single-wire UART scheme
> where `uart_pin` is the shared data line and `tx_pin` is the dedicated transmit pin.
> Some configurations show only `uart_pin` if the board uses a single bidirectional line
> with a resistor. Check the BTT schematic for your specific board revision.

### 4.4 Stallguard4 / Sensorless Homing

**Stallguard4 (SG4)** on the TMC2209 provides load-based stall detection. When the
motor encounters mechanical resistance (e.g., hitting an endstop), the SG4 value drops
and the DIAG pin asserts.

**Klipper sensorless homing configuration:**

```ini
[stepper_x]
endstop_pin: tmc2209_stepper_x:virtual_endstop
homing_retract_dist: 0

[tmc2209 stepper_x]
uart_pin: gpio9
tx_pin: gpio8
uart_address: 0
run_current: 0.580
diag_pin: ^gpio4
driver_SGTHRS: 80
```

**Key points for sensorless homing:**

1. `endstop_pin: tmc2209_stepper_x:virtual_endstop` -- tells Klipper to use the
   TMC2209's DIAG output as the endstop signal.
2. `diag_pin: ^gpio4` -- the physical DIAG pin on the BTT Pico (active-low, hence the
   `^` pull-up prefix). The BTT Pico routes DIAG pins to the endstop connectors when
   jumpers are installed.
3. `driver_SGTHRS: 80` -- Stallguard threshold (0-255). Higher = more sensitive.
   Tuning is required for each mechanical setup.
4. `homing_retract_dist: 0` -- Important for sensorless homing to avoid re-triggering.

**Jumper requirement:** On the BTT Pico, you typically need to install a solder-bridge
jumper or pin jumper to connect the TMC2209 DIAG pin to the endstop connector. Without
this jumper, the DIAG signal does not reach the MCU's endstop input pin.

### 4.5 Stallguard for Torque Feedback (W26 Stretch Goal)

From the project's CLAUDE.md, Stallguard torque feedback to URScript is listed as a
stretch goal. This is feasible:

1. **Read SG_RESULT in Klipper:** The TMC2209 Stallguard result register can be
   queried via Klipper's `DUMP_TMC` command or by reading the `sg_result` field
   from the driver status.

2. **Klipper G-Code macro approach:**
   ```gcode
   [gcode_macro GET_TMC_SG]
   gcode:
       {% set sg = printer["tmc2209 extruder"].sg_result %}
       M118 SG_RESULT={sg}
   ```

3. **Relay to UR30:** The Pi400 Klipper host can parse the SG_RESULT value and
   relay it back to the UR30 via RTDE. This would require custom Python scripting
   on the Pi400 side (using the `ur_rtde` Python library to write registers).

4. **Limitations:**
   - SG4 values are noisy and vary with speed, current, and temperature.
   - Meaningful torque estimation requires calibration against a known load.
   - Update rate is limited by the TMC2209 UART polling rate (typically ~10-50 Hz
     through Klipper).
   - Stallguard does not provide an absolute torque measurement; it provides a
     relative load indicator.

---

## 5. Klipper Configuration Examples

### 5.1 Complete Minimal Configuration for BTT Pico (Single Extruder Axis)

For the W26 project, we likely only need the extruder stepper (one motor). Here is a
minimal `printer.cfg`:

```ini
# W26 Cobot Axis -- BTT Pico Klipper Configuration
# Single extruder stepper for UR30 7th axis

[mcu]
serial: /dev/serial/by-id/usb-Klipper_rp2040_XXXXXXXXXXXX-if00
# OR for UART:
# serial: /dev/ttyAMA0
# baud: 250000

[printer]
kinematics: none
# "none" kinematics is used when the board controls only auxiliary axes
# and no Cartesian/CoreXY motion system is present.
# Alternatively, use "extruder" or a custom kinematics if needed.
max_velocity: 300
max_accel: 3000

# ---- Extruder Stepper (using E driver on BTT Pico) ----

[extruder]
step_pin: gpio14
dir_pin: gpio13
enable_pin: !gpio15
microsteps: 16
rotation_distance: 33.5
# rotation_distance depends on your extruder gearing.
# For a direct-drive extruder with a 1.8-deg stepper:
#   rotation_distance = full_steps_per_rotation * microsteps * (mm_per_step)
# Calibrate this value experimentally.
nozzle_diameter: 0.400
filament_diameter: 1.750
heater_pin: gpio23
sensor_type: EPCOS 100K B57560G104F
sensor_pin: gpio27
control: pid
pid_Kp: 21.527
pid_Ki: 1.063
pid_Kd: 108.982
min_temp: 0
max_temp: 250

[tmc2209 extruder]
uart_pin: gpio9
tx_pin: gpio8
uart_address: 3
run_current: 0.650
stealthchop_threshold: 999999

# ---- Heater Bed (optional, may not be needed for W26) ----

# [heater_bed]
# heater_pin: gpio21
# sensor_type: EPCOS 100K B57560G104F
# sensor_pin: gpio26
# control: pid
# pid_Kp: 54.027
# pid_Ki: 0.770
# pid_Kd: 948.182
# min_temp: 0
# max_temp: 130

# ---- Fans (optional) ----

# [fan]
# pin: gpio17

# [heater_fan hotend_fan]
# pin: gpio18

# ---- Neopixel (optional) ----

# [neopixel board_neopixel]
# pin: gpio24
# chain_count: 1
# color_order: GRB

# ---- Temperature Sensor: MCU ----

[temperature_sensor mcu_temp]
sensor_type: temperature_mcu
min_temp: 0
max_temp: 100
```

### 5.2 Reference Configuration from Klipper Repository

The official Klipper repository includes a reference configuration at:

```
klipper/config/generic-bigtreetech-pico-v1.0.cfg
```

**GitHub URL:**
https://github.com/Klipper3d/klipper/blob/master/config/generic-bigtreetech-pico-v1.0.cfg

This file contains the complete pin mapping for all stepper drivers, thermistors, fans,
and TMC2209 configurations.

### 5.3 Extruder-Only Configuration (No XYZ Motion)

For the W26 project, we do not need XYZ kinematics. Klipper requires a `[printer]`
section and at least one motion component, but we can work around this:

**Option A: Use `kinematics: none`**

Klipper (as of recent versions) supports `kinematics: none` for boards that only
control non-motion peripherals. However, this may not expose the extruder stepper
properly.

**Option B: Define dummy steppers**

```ini
[printer]
kinematics: cartesian
max_velocity: 300
max_accel: 3000

[stepper_x]
step_pin: gpio11
dir_pin: gpio10
enable_pin: !gpio12
microsteps: 16
rotation_distance: 40
endstop_pin: ^gpio4
position_endstop: 0
position_max: 1

[stepper_y]
step_pin: gpio6
dir_pin: gpio5
enable_pin: !gpio7
microsteps: 16
rotation_distance: 40
endstop_pin: ^gpio3
position_endstop: 0
position_max: 1

[stepper_z]
step_pin: gpio19
dir_pin: gpio28
enable_pin: !gpio2
microsteps: 16
rotation_distance: 8
endstop_pin: ^gpio25
position_endstop: 0
position_max: 1
```

Then define the extruder normally. The dummy steppers will never be homed or moved.

**Option C: Use `[manual_stepper]`**

For pure positional control (no heater/thermistor needed):

```ini
[manual_stepper extruder_axis]
step_pin: gpio14
dir_pin: gpio13
enable_pin: !gpio15
microsteps: 16
rotation_distance: 33.5
velocity: 50
accel: 1000

[tmc2209 manual_stepper extruder_axis]
uart_pin: gpio9
tx_pin: gpio8
uart_address: 3
run_current: 0.650
stealthchop_threshold: 999999
```

Control via G-code:

```gcode
MANUAL_STEPPER STEPPER=extruder_axis ENABLE=1
MANUAL_STEPPER STEPPER=extruder_axis SET_POSITION=0
MANUAL_STEPPER STEPPER=extruder_axis MOVE=100 SPEED=50
```

> **Recommendation for W26:** Option C (`[manual_stepper]`) is likely the best fit.
> It gives precise positional control of the extrusion stepper without requiring
> dummy XYZ axes or a heater/thermistor. The Pi400 Klipper host can send
> `MANUAL_STEPPER` commands in response to UR30 RTDE instructions.

### 5.4 Sending Commands from Python (Pi400 Side)

The Pi400 can send G-code commands to Klipper via its API:

```python
import requests
import json

KLIPPER_API = "http://localhost:7125"  # Moonraker API

def move_extruder(distance_mm, speed_mm_s):
    """Send a manual_stepper move command via Moonraker API."""
    gcode = f"MANUAL_STEPPER STEPPER=extruder_axis MOVE={distance_mm} SPEED={speed_mm_s}"
    response = requests.post(
        f"{KLIPPER_API}/printer/gcode/script",
        json={"script": gcode}
    )
    return response.json()

def get_stallguard_value():
    """Read TMC2209 Stallguard result via Moonraker API."""
    response = requests.get(
        f"{KLIPPER_API}/printer/objects/query",
        params={"tmc2209 manual_stepper extruder_axis": "sg_result"}
    )
    data = response.json()
    return data["result"]["status"]["tmc2209 manual_stepper extruder_axis"]["sg_result"]
```

This requires **Moonraker** to be installed alongside Klipper on the host Pi.
Alternatively, commands can be sent directly via the Klipper Unix socket or serial
console.

---

## 6. Known Issues and Gotchas

### 6.1 RP2040-Specific Issues

1. **Flash chip configuration:** The RP2040 on the BTT Pico uses a W25Q16 (16 Mbit)
   flash chip. In Klipper's `make menuconfig`, select `W25Q080 with CLKDIV 2` for
   the flash chip setting -- this is compatible with the W25Q16 despite the name
   mismatch. Selecting the wrong flash chip will result in a non-booting firmware.

2. **USB disconnect under electrical noise:** RP2040 USB can be sensitive to
   electrical noise from stepper motors. Use a quality USB cable and ensure proper
   grounding. UART serial avoids this issue entirely.

3. **No persistent storage for Klipper configuration:** The RP2040 has limited flash.
   Klipper stores its configuration on the host Pi, not on the MCU. If you switch
   hosts, the configuration does not travel with the board.

4. **Watchdog timer:** The RP2040 Klipper firmware includes a watchdog. If
   communication with the host is lost for more than ~5 seconds, the MCU will
   reset and disable all outputs (motors, heaters). This is a safety feature.

### 6.2 TMC2209-Specific Issues

1. **Shared UART bus timing:** Since all four TMC2209 drivers share one UART line,
   there can be occasional communication errors if the bus is polled too aggressively.
   Klipper handles this with retries, but if you see `Unable to read tmc uart`
   errors, ensure your `uart_pin` and `tx_pin` are correct and that no other
   device is connected to those GPIO pins.

2. **DIAG pin jumper for sensorless homing:** The DIAG pins on the TMC2209 are NOT
   connected to the endstop pins by default on the BTT Pico. You must install
   jumpers or solder bridges to route them. Without this, `virtual_endstop` will
   not work. Consult the BTT Pico schematic/silk-screen for jumper locations.

3. **Stallguard sensitivity at low speeds:** SG4 does not work reliably below
   certain speeds. The TMC2209 datasheet recommends operation above ~10 RPM for
   meaningful Stallguard readings. At very low extrusion speeds, Stallguard
   feedback will be unreliable.

4. **Internal RSENSE:** The BTT Pico uses internal sense resistors on the TMC2209
   (approximately 0.11 ohm). You should **not** set `sense_resistor` in the Klipper
   TMC2209 config unless you know the exact value differs. The default Klipper
   value of 0.110 is typically correct.

### 6.3 Klipper-Specific Issues

1. **`kinematics: none` limitations:** As of Klipper mainline, `kinematics: none` may
   not be fully supported or may have limitations with stepper control. Using
   `[manual_stepper]` is the safer approach for our single-axis use case.

2. **Firmware version mismatch:** The Klipper host software and MCU firmware must be
   from the same commit. After updating Klipper on the host, you MUST reflash the
   BTT Pico firmware. Version mismatch causes `MCU protocol error` at startup.

3. **Single MCU timing:** The RP2040's dual cores are used by Klipper for step
   generation and communication, respectively. For our single-stepper use case,
   the RP2040 has more than enough processing power.

4. **Moonraker dependency:** Sending commands programmatically (from the Python RTDE
   bridge) is easiest through Moonraker's HTTP API. Without Moonraker, you need
   to interact with Klipper's Unix domain socket directly, which is more complex.

### 6.4 Power Supply Considerations

1. **Input voltage:** The BTT Pico accepts 12-24V. The UR30 provides 24V, which is
   at the upper end but within spec.
2. **Stepper motor current:** Ensure the stepper motor's rated current does not exceed
   the BTT Pico's per-driver limit (~1.2A RMS continuous due to board thermals).
   If more current is needed, external TMC2209 drivers or a different board may be
   required.
3. **5V rail:** The BTT Pico has an onboard 5V regulator. It can power the board
   logic and a Raspberry Pi via the UART header's 5V pin, but this is limited to
   about 1A. For the W26 project, the Pi should have its own power supply.

### 6.5 Board Name Confusion

The board is variously referred to as:
- "BTT Pico" (common shorthand)
- "BIGTREETECH Pico" (full brand name)
- "BTT SKR Pico" (product listing name)
- "SKR Pico v1.0" (GitHub repo name)

These all refer to the same board. The Klipper config file uses
`generic-bigtreetech-pico-v1.0.cfg`, and the GitHub repo is
`bigtreetech/SKR-Pico`.

---

## 7. Relevance to W26 Project Architecture

### 7.1 Architecture Mapping

```
UR30 Controller
    |
    | RTDE over TCP/IP (Ethernet)
    v
Pi400 (Klipper Host + Moonraker + RTDE Bridge)
    |
    | Klipper serial (USB or UART)
    v
BTT Pico (RP2040 + Klipper MCU firmware)
    |
    | TMC2209 step/dir signals
    v
Stepper Motor (Extrusion)
```

### 7.2 Key Decisions for W26

| Decision | Recommendation | Rationale |
|---|---|---|
| Communication method | USB serial (start), UART (production) | USB is easier to debug; UART is more robust |
| Klipper config approach | `[manual_stepper]` | No XYZ kinematics needed; precise positional control |
| Stallguard feedback | Feasible but noisy | Good for stall detection; unreliable for precise torque measurement |
| Slave Pi necessity | Possibly unnecessary | The Pi400 can connect directly to the BTT Pico via USB. A second Pi adds latency and complexity. Re-evaluate whether the Slave Pi is truly needed. |
| Moonraker | Install on Pi400 | Simplifies programmatic G-code command sending from the RTDE bridge script |

### 7.3 Simplified Architecture (Recommended)

If the Slave Pi is not strictly required:

```
UR30 Controller
    |
    | RTDE over TCP/IP
    v
Pi400 (Klipper Host + Moonraker + RTDE Bridge Python script)
    |
    | USB serial (or UART via GPIO)
    v
BTT Pico (Klipper MCU firmware)
    |
    | Onboard TMC2209 -> Stepper motor
    v
Extrusion Stepper
```

This eliminates one communication hop and reduces latency.

---

## 8. References and Links

### Official BigTreeTech Resources

- **BTT SKR Pico GitHub repository (hardware docs, schematics, pinout):**
  https://github.com/bigtreetech/SKR-Pico

- **BigTreeTech GitHub organization (all boards):**
  https://github.com/bigtreetech

- **BTT Pico product page (AliExpress / BTT official store):**
  Search "BIGTREETECH SKR Pico" on the BTT official store.

### Klipper Resources

- **Klipper official documentation:**
  https://www.klipper3d.org/

- **Klipper RP2040 build instructions:**
  https://www.klipper3d.org/RPi_microcontroller.html

- **Klipper TMC driver documentation:**
  https://www.klipper3d.org/TMC_Drivers.html

- **Klipper reference config for BTT Pico v1.0:**
  https://github.com/Klipper3d/klipper/blob/master/config/generic-bigtreetech-pico-v1.0.cfg

- **Klipper `manual_stepper` documentation:**
  https://www.klipper3d.org/Config_Reference.html#manual_stepper

- **Klipper GitHub repository:**
  https://github.com/Klipper3d/klipper

### TMC2209 Resources

- **TMC2209 datasheet (Trinamic / ADI):**
  https://www.trinamic.com/products/integrated-circuits/details/tmc2209-la/

- **Klipper Stallguard / sensorless homing guide:**
  https://www.klipper3d.org/TMC_Drivers.html#sensorless-homing

### Moonraker (API Server for Klipper)

- **Moonraker GitHub repository:**
  https://github.com/Arksine/moonraker

- **Moonraker API documentation:**
  https://moonraker.readthedocs.io/

### RP2040 Resources

- **RP2040 datasheet (Raspberry Pi Foundation):**
  https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf

- **Picotool (for alternative flashing):**
  https://github.com/raspberrypi/picotool

### Community Resources

- **Voron Design Discord (active BTT Pico + Klipper community):**
  https://discord.gg/voron

- **Klipper Discord:**
  https://discord.klipper3d.org/

---

> **Document status:** Initial research compilation. Pin numbers and configuration
> snippets should be verified against the physical board and the official Klipper
> reference config before use. All URLs should be checked for availability.
