# BigTreeTech SKR Pico V1.0 -- Hardware Reference

> **Product code:** BIGTREETECH SKR Pico V1.0 (1060000513)
> **Date code:** 2025.1.10
> **Project context:** W26 Cobot Axis -- single stepper motor driver for UR30 7th axis, controlled via Klipper firmware.
> **Document date:** 2026-02-12

---

## Table of Contents

1. [Naming Clarification](#1-naming-clarification)
2. [Full Specifications](#2-full-specifications)
3. [Complete Pinout](#3-complete-pinout)
4. [TMC2209 Driver Details](#4-tmc2209-driver-details)
5. [Klipper Firmware Flashing Procedure](#5-klipper-firmware-flashing-procedure)
6. [Known Issues and Community Notes](#6-known-issues-and-community-notes)
7. [Schematic and Hardware Design Files](#7-schematic-and-hardware-design-files)
8. [Sources](#8-sources)

---

## 1. Naming Clarification

The board is referred to by several names in the community. They all mean the same product:

| Name | Context |
|------|---------|
| **BTT SKR Pico V1.0** | Official product name on packaging and GitHub |
| **SKR Pico** | Common shorthand |
| **BTT Pico** | Community shorthand (e.g., Fabreeko, Voron forums) |
| **BIGTREETECH SKR Pico** | Full brand + product name |

The official GitHub repository is `bigtreetech/SKR-Pico`. The Klipper reference config filename is `generic-bigtreetech-skr-pico-v1.0.cfg`.

There is **no separate board called "BTT Pico"** that differs from the SKR Pico. The "SKR" prefix is part of BigTreeTech's product line naming (like SKR Mini, SKR Octopus, etc.). The "Pico" refers to its compact form factor and RP2040 MCU (same chip as the Raspberry Pi Pico), not to the Raspberry Pi Pico board itself.

An **"Armored" variant** exists (SKR Pico Armored) which adds a protective metal top cover / enclosure for improved cooling and physical protection. The PCB is identical.

---

## 2. Full Specifications

### 2.1 MCU

| Parameter | Value |
|-----------|-------|
| Microcontroller | Raspberry Pi RP2040 |
| Architecture | Dual-core ARM Cortex-M0+ |
| Clock speed | Up to 133 MHz |
| On-chip SRAM | 264 KB (6 independent banks) |
| External flash | 2 MB (W25Q16 QSPI, 16 Mbit) |
| Logic voltage | 3.3V |

### 2.2 Power

| Parameter | Value |
|-----------|-------|
| Input voltage | DC 12V -- 24V |
| Fuse | Replaceable SMD fuse in removable fuse holder |
| On-board regulation | 3.3V for MCU logic; 5V rail available |
| Heater bed max power | 24V x 10A = 240W (at 24V input) |
| Hotend heater max power | 70W (at 24V input) |

### 2.3 Stepper Motor Outputs

| Parameter | Value |
|-----------|-------|
| Driver IC | TMC2209 (x4, soldered on-board, non-replaceable) |
| Driver mode | UART (factory-configured) |
| Motor axes | X, Y, Z (Z1+Z2 share one driver slot), E -- 4 driver positions total |
| Connector type | JST-XH 4-pin (per motor) |

### 2.4 Heater / MOSFET Outputs

| Output | Pin | Max Rating |
|--------|-----|------------|
| Heated bed (HB) | gpio21 | 10A continuous @ 24V (240W) |
| Hotend heater (HE) | gpio23 | ~3A @ 24V (70W) |

### 2.5 Fan Ports

| Port | Pin | Type | Notes |
|------|-----|------|-------|
| Fan0 (part cooling) | gpio17 | PWM, N-MOSFET switched | With flyback protection diode |
| Fan1 (heatbreak) | gpio18 | PWM, N-MOSFET switched | With flyback protection diode |
| Fan2 (controller) | gpio20 | PWM, N-MOSFET switched | With flyback protection diode |

All 3 fan ports are driven by PWM-capable MOSFETs. Voltage follows VIN (12V or 24V depending on PSU).

### 2.6 Thermistor Inputs

| Input | Pin | Type |
|-------|-----|------|
| TH0 (hotend) | gpio27 | 100K NTC (pulled up on-board) |
| THB (bed) | gpio26 | 100K NTC (pulled up on-board) |

### 2.7 Endstop / Limit Switch Ports

| Port | Pin | Notes |
|------|-----|-------|
| X endstop | gpio4 | Active-low with internal pull-up available (`^gpio4`) |
| Y endstop | gpio3 | Active-low with internal pull-up available (`^gpio3`) |
| Z endstop | gpio25 | Active-low with internal pull-up available (`^gpio25`) |

### 2.8 Probe / Proximity / Laser

| Port | Pin | Notes |
|------|-----|-------|
| Probe sensor (BLTouch signal) | gpio22 | Shared with proximity switch via SELECT jumper |
| Probe control (BLTouch servo) | gpio29 | PWM output for BLTouch deploy/retract |
| Proximity switch (PS) | gpio22 | Shared with probe; jumper-selectable external pull-up |
| Laser port | gpio29 | Dedicated laser output header |

A jumper (SELECT-PROXIMITY-I/O-PIN) determines whether gpio22 is routed to the PS connector or the PROBE connector.

### 2.9 Other I/O

| Function | Pin | Notes |
|----------|-----|-------|
| Neopixel (WS2812) | gpio24 | 1x on-board RGB LED; active data-out for daisy-chaining |
| Filament runout sensor | gpio16 | Active-low with pull-up (`^gpio16`) |
| MCU temperature | Internal | RP2040 on-die temperature sensor |

### 2.10 Communication Interfaces

| Interface | Details |
|-----------|---------|
| USB | USB Type-C (USB 2.0 Full-Speed, 12 Mbps) |
| UART to Pi | UART0 on GPIO0 (TX) / GPIO1 (RX); dedicated 3-pin header |
| SPI | SPI0 available on GPIO3 (SCK), GPIO4 (MOSI/TX) -- shared with endstop pins |
| I2C | Not broken out to dedicated header; available via software on unused GPIOs |
| ADXL345 | Can be connected via SPI to the RP2040 for input shaping |

**Note:** SPI0 pins overlap with endstop pins (gpio3, gpio4). Using SPI for an accelerometer means those endstops cannot be used simultaneously. See Klipper discourse thread on `gpio3 is reserved for spi0a`.

### 2.11 Physical

| Parameter | Value |
|-----------|-------|
| Board dimensions | 85 mm x 56 mm |
| PCB layers | 4 |
| Mounting | Matches Raspberry Pi mounting hole pattern (for stacking) |
| Heatsink | Included; attached with thermal conductive silicone pad |
| Capacitors | Murata MLCC ceramic capacitors |
| Weight | ~38g (board only, estimated; not specified in official docs) |

### 2.12 LED Indicators

| LED | Function |
|-----|----------|
| LED6 | Power indicator (red, steady when powered) |
| LED4 | Heated bed HB status (on during heating) |
| LED5 | Heating rod HE status (on during heating) |
| LED1 | Fan0 status |
| LED2 | Fan1 status |
| LED3 | Fan2 status |
| LED7 | Programmable RGB (Neopixel on gpio24) |

---

## 3. Complete Pinout

### 3.1 Stepper Motor Pins

| Axis | Step | Direction | Enable | UART | UART TX | Address | DIAG / Endstop |
|------|------|-----------|--------|------|---------|---------|----------------|
| X | gpio11 | gpio10 | gpio12 | gpio9 | gpio8 | 0 | gpio4 |
| Y | gpio6 | gpio5 | gpio7 | gpio9 | gpio8 | 2 | gpio3 |
| Z | gpio19 | gpio28 | gpio2 | gpio9 | gpio8 | 1 | gpio25 |
| E (extruder) | gpio14 | gpio13 | gpio15 | gpio9 | gpio8 | 3 | gpio16 |

**Notes:**
- Enable pins are active-low (use `!gpioNN` in Klipper config).
- Direction pins may need inversion depending on motor wiring (use `!gpioNN`).
- All four drivers share the same UART RX (gpio9) and TX (gpio8) pins, differentiated by `uart_address`.
- DIAG pins share the same physical connector as endstop pins. A jumper must be installed to connect the TMC2209 DIAG output to the endstop input pin for sensorless homing.

### 3.2 Heater Pins

| Function | Pin |
|----------|-----|
| Hotend heater (HE) | gpio23 |
| Heated bed (HB) | gpio21 |

### 3.3 Thermistor Pins

| Function | Pin |
|----------|-----|
| Hotend thermistor (TH0) | gpio27 |
| Bed thermistor (THB) | gpio26 |

### 3.4 Fan Pins

| Function | Pin |
|----------|-----|
| Part cooling fan (Fan0) | gpio17 |
| Heatbreak fan (Fan1) | gpio18 |
| Controller fan (Fan2) | gpio20 |

### 3.5 Endstop / Probe Pins

| Function | Pin |
|----------|-----|
| X endstop | gpio4 |
| Y endstop | gpio3 |
| Z endstop | gpio25 |
| BLTouch sensor / Probe | gpio22 |
| BLTouch control / Servo | gpio29 |
| Filament runout | gpio16 |

### 3.6 Neopixel / RGB

| Function | Pin |
|----------|-----|
| Neopixel data | gpio24 |

### 3.7 Host Communication

| Function | Pin |
|----------|-----|
| UART0 TX (to Pi RX) | gpio0 |
| UART0 RX (from Pi TX) | gpio1 |
| USB | USB-C connector (no GPIO pin -- hardware USB on RP2040) |

---

## 4. TMC2209 Driver Details

### 4.1 TMC2209 IC Specifications (on this board)

| Parameter | Value |
|-----------|-------|
| IC | TMC2209-LA (Trinamic / Analog Devices) |
| Interface mode | UART (single-wire, shared bus with addressing) |
| Max current (IC absolute max) | 2.0A RMS / 2.8A peak |
| RSENSE value | 110 milliohm (0.110 ohm) on-board sense resistors |
| Max settable current (with 110mR RSENSE) | 1.77A RMS theoretical; Klipper default `sense_resistor: 0.110` |
| Board thermal limit (continuous, no fan) | ~0.8A RMS per driver |
| Board thermal limit (continuous, with active cooling) | ~1.2A RMS per driver (estimate) |
| Microstep resolution | Up to 256 microsteps (via UART configuration) |
| StealthChop2 | Yes (silent operation below configurable velocity threshold) |
| SpreadCycle | Yes (higher torque / higher speed operation) |
| StallGuard4 (SG4) | Yes (load detection, sensorless homing) |
| CoolStep | Yes (automatic current reduction based on load) |

### 4.2 UART Wiring

The four on-board TMC2209 drivers share a **single UART bus** using a two-wire configuration:

- **RX line (uart_pin):** gpio9 -- shared by all four drivers (active receive)
- **TX line (tx_pin):** gpio8 -- shared by all four drivers (active transmit)

This is a half-duplex single-wire UART implementation where the TX and RX lines are connected to the TMC2209's PDN_UART pin through a 1K ohm resistor on the TX side. This resistor separates the TX and RX signals, preventing bus contention.

Each driver is addressed individually using the TMC2209's MS1/MS2 address pins, which are hardwired on the PCB to set unique addresses:

| Driver | uart_address | MS1 | MS2 |
|--------|-------------|-----|-----|
| X | 0 | LOW | LOW |
| Z | 1 | HIGH | LOW |
| Y | 2 | LOW | HIGH |
| E | 3 | HIGH | HIGH |

**Note:** The address assignments do not follow a sequential axis order (X=0, Y=2, Z=1, E=3). This is a PCB routing convenience; it does not affect functionality as long as the Klipper config uses the correct `uart_address` for each axis.

### 4.3 RSENSE and Current Setting

The on-board sense resistors are **110 milliohm (0.110 ohm)**. In Klipper, this is the default `sense_resistor` value for the TMC2209, so it does not need to be explicitly set. The RMS current formula is:

```
I_RMS = (V_REF / (R_SENSE + 0.020)) * (1 / sqrt(2)) * (CS / 31)
```

Where `V_REF` = 0.325V (internal), `R_SENSE` = 0.110 ohm, and `CS` is the current scale register (0-31).

At maximum `CS = 31`: **I_RMS_max = 1.77A**

However, the board's thermal design limits practical continuous current to:
- **0.8A RMS** without active cooling (BTT's own recommendation)
- **~1.2A RMS** with a fan blowing on the heatsink (community consensus)

For the W26 project (single stepper), thermal concerns are reduced since only one driver is active.

### 4.4 StallGuard4 and DIAG Pins

Each TMC2209 has a DIAG output pin that asserts (goes low) when a motor stall is detected by StallGuard4. On the SKR Pico, the DIAG pins are routed to the **endstop connector pads** but are **disconnected by default**. To enable sensorless homing:

1. **Install the DIAG jumper** for the relevant axis. This is a physical pin jumper on the board that bridges the TMC2209 DIAG output to the endstop input GPIO.
2. **Remove any mechanical endstop** connected to that axis. Sensorless homing and physical endstops are mutually exclusive on the same axis (they share the same GPIO pin).
3. **Configure Klipper** to use the virtual endstop:

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

DIAG pin to GPIO mapping:

| Axis | DIAG Pin (GPIO) |
|------|----------------|
| X | gpio4 |
| Y | gpio3 |
| Z | gpio25 |
| E | gpio16 |

**StallGuard threshold (`driver_SGTHRS`):** Range 0--255. Higher values = more sensitive (triggers at lower load). Must be tuned per mechanical setup. Typical starting values: 50--100.

---

## 5. Klipper Firmware Flashing Procedure

### 5.1 Build Configuration (make menuconfig)

On the Klipper host (Raspberry Pi):

```bash
cd ~/klipper
make menuconfig
```

Set the following options:

```
[*] Enable extra low-level configuration options
    Micro-controller Architecture  --->  Raspberry Pi RP2040
    Processor model                --->  rp2040
    Bootloader offset              --->  No bootloader
    Flash chip                     --->  W25Q080 with CLKDIV 2
    Communication interface        --->  USBSERIAL
```

**Notes on settings:**
- The flash chip is actually a W25Q16 (16 Mbit / 2 MB), but the `W25Q080 with CLKDIV 2` setting is compatible and is what BTT and Klipper documentation specify. Do not select a different flash option.
- For **UART communication** instead of USB, select: `Communication interface ---> Serial (on UART0 GPIO1/GPIO0)`.
- The "No bootloader" setting is correct -- the RP2040 uses its built-in ROM bootloader for UF2 flashing.

### 5.2 Build Firmware

```bash
make clean
make
```

This produces `~/klipper/out/klipper.uf2`.

### 5.3 Enter Boot Mode (DFU / BOOTSEL)

1. Install a jumper on the **Boot** header pins on the SKR Pico.
2. Optionally install a jumper on the **USB Power** header if the board is not powered by 24V.
3. Press the **Reset** button on the board.
4. The RP2040 enters USB mass storage mode and appears as a drive named **RPI-RP2** (or **RPI-PR2** in some documentation).

### 5.4 Flash Firmware (Initial Flash)

**Important:** The `make flash` command does **not** work for initial flashing on the SKR Pico V1.0. You must manually copy the UF2 file.

**Method A -- From Raspberry Pi (headless):**

```bash
sudo mount /dev/sda1 /mnt
sudo cp ~/klipper/out/klipper.uf2 /mnt/
sudo umount /mnt
```

**Method B -- From a desktop computer:**

Drag and drop the `klipper.uf2` file onto the RPI-RP2 USB drive that appears when the board is in boot mode.

### 5.5 Post-Flash

1. The board automatically reboots after the UF2 file is copied. The USB mass storage device disappears.
2. **Remove the Boot jumper** and press Reset for normal operation.
3. Verify the board is recognized:

```bash
ls /dev/serial/by-id/
```

Expected output:

```
usb-Klipper_rp2040_XXXXXXXXXXXX-if00
```

### 5.6 Subsequent Firmware Updates

Once Klipper is already running on the board, subsequent updates can use `make flash`:

```bash
sudo service klipper stop
cd ~/klipper
make flash FLASH_DEVICE=/dev/serial/by-id/usb-Klipper_rp2040_XXXXXXXXXXXX-if00
sudo service klipper start
```

This uses Klipper's built-in mechanism to re-enter the RP2040 bootloader via USB, flash the new firmware, and reboot automatically.

---

## 6. Known Issues and Community Notes

### 6.1 Heatsink Adhesion

The included heatsink is attached with a thermal conductive silicone pad (not screws). Multiple users report the heatsink detaching after days to weeks of use. **Recommendation:** verify heatsink adhesion before deployment; consider reinforcing with thermal tape or a mechanical clip.

If the heatsink is removed, ensure the thermal pad is properly aligned to avoid shorting exposed components underneath.

**GitHub issue:** bigtreetech/SKR-Pico#4

### 6.2 Thermal Limits

BTT explicitly states: *"If you want to use a motor drive current of more than 0.8A, it is recommended to use a fan to actively cool the drive chip."* For the W26 project running a single stepper at moderate current (0.5--0.8A), this is unlikely to be an issue, but active cooling should be considered if running above 0.8A.

### 6.3 USB Detection on Boot

Some users report the SKR Pico is not detected by the host Pi until the Reset button on the board is manually pressed after system boot. This appears related to USB enumeration timing.

**GitHub issue:** bigtreetech/CB1#11

**Workaround:** Add a short delay and USB reset in the Pi's startup script, or use UART communication instead of USB.

### 6.4 UART Connection Difficulties with Pi

Multiple GitHub issues (#9, #18, #22) report difficulty establishing UART serial communication between the SKR Pico and various Raspberry Pi models (Pi Zero 2W, Pi 3B+, Pi 4B). Common causes:
- Incorrect baud rate (must match Klipper build setting)
- Linux serial console still enabled on `/dev/ttyAMA0` (must be disabled via `raspi-config`)
- TX/RX wires swapped

### 6.5 24V Power Required for TMC2209 UART

**Critical for W26:** If the SKR Pico is not powered with 12--24V on its main VIN, Klipper will be unable to communicate with the TMC2209 drivers via UART, and the board may shut down. The USB 5V power alone is insufficient for driver communication. The 24V supply from the UR controller power block must be connected before Klipper can read/write TMC registers.

### 6.6 Shared UART Bus Errors

Since all four TMC2209 drivers share one UART line, occasional `Unable to read tmc uart` errors can occur. Klipper handles this with automatic retries. Frequent errors may indicate:
- Incorrect `uart_pin` / `tx_pin` / `uart_address` in config
- Electrical noise on the UART lines
- Damaged driver IC

### 6.7 SPI Pin Conflict

GPIO3 (Y endstop) and GPIO4 (X endstop) overlap with SPI0 pins. If SPI is used (e.g., for an ADXL345 accelerometer), those endstop ports become unavailable. Klipper will raise: `pin gpio3 is reserved for spi0a`.

### 6.8 Non-Replaceable Drivers

The four TMC2209 drivers are **soldered directly onto the PCB**. If a driver fails, the entire board must be replaced. There are no plug-in driver sockets.

### 6.9 No Official Marlin Support

The SKR Pico was designed for Klipper. Multiple community requests for Marlin firmware support remain unanswered. This is not an issue for the W26 project (which uses Klipper).

### 6.10 make flash Does Not Work for Initial Flash

The `make flash` command cannot be used for the first firmware upload. The UF2 file must be manually copied to the RP2040's USB mass storage. After the initial flash, `make flash` works for subsequent updates.

### 6.11 Klipper Version Mismatch

The Klipper host software and MCU firmware must be compiled from the same Git commit. After updating Klipper on the Pi, the SKR Pico firmware **must** be reflashed. A version mismatch causes `MCU protocol error` at startup.

---

## 7. Schematic and Hardware Design Files

All hardware design files are available in the official BigTreeTech GitHub repository:

| File | URL |
|------|-----|
| Schematic (PDF) | https://github.com/bigtreetech/SKR-Pico/blob/master/Hardware/BTT%20SKR%20Pico%20V1.0-SCH.pdf |
| Pinout diagram (PDF) | https://github.com/bigtreetech/SKR-Pico/blob/master/Hardware/BTT%20SKR%20Pico%20V1.0-PIN.pdf |
| Top layer (PDF) | https://github.com/bigtreetech/SKR-Pico/blob/master/Hardware/BTT%20SKR%20Pico%20V1.0-TOP.pdf |
| Bottom layer (PDF) | https://github.com/bigtreetech/SKR-Pico/blob/master/Hardware/BTT%20SKR%20Pico%20V1.0-BOTTOM.pdf |
| Instruction manual (PDF) | https://github.com/bigtreetech/SKR-Pico/blob/master/BTT%20SKR%20Pico%20V1.0%20Instruction%20Manual.pdf |
| 3D model files | https://github.com/bigtreetech/SKR-Pico/tree/master/3D |
| Klipper config (BTT) | https://github.com/bigtreetech/SKR-Pico/blob/master/Klipper/SKR%20Pico%20klipper.cfg |
| Klipper config (official) | https://github.com/Klipper3d/klipper/blob/master/config/generic-bigtreetech-skr-pico-v1.0.cfg |

---

## 8. Sources

### Official BigTreeTech Resources
- [BTT SKR-Pico GitHub Repository](https://github.com/bigtreetech/SKR-Pico)
- [BTT SKR Pico Wiki](https://global.bttwiki.com/SKR%20Pico.html)
- [BTT Docs -- SKR Pico](https://github.com/bigtreetech/docs/blob/master/docs/SKR%20Pico.md)
- [BTT Product Page (Biqu Equipment)](https://biqu.equipment/products/btt-skr-pico-v1-0)
- [BTT Official Store -- SKR Pico Announcement](https://bigtree-tech.com/blogs/news/new-release-bigtreetech-skr-pico-v1-0-control-board)
- [BTT Instruction Manual PDF (hosted at grobotronics)](https://grobotronics.com/images/companies/1/BTT%20SKR%20Pico%20V1.0%20Instruction%20Manual.pdf)

### Klipper Resources
- [Klipper Reference Config: generic-bigtreetech-skr-pico-v1.0.cfg](https://github.com/Klipper3d/klipper/blob/master/config/generic-bigtreetech-skr-pico-v1.0.cfg)
- [Voron Design -- SKR Pico Klipper Firmware Guide](https://docs.vorondesign.com/build/software/skrPico_klipper.html)
- [Esoterical's USB Flashing Guide -- BTT SKR Pico](https://usb.esoterical.online/hardware_config/RP2040/BTT_SKR_Pico.html)
- [BTT SKR-Pico Klipper README](https://github.com/bigtreetech/SKR-Pico/blob/master/Klipper/README.md)

### TMC2209 Resources
- [TMC2209 Datasheet Rev 1.09 (Analog Devices)](https://www.analog.com/media/en/technical-documentation/data-sheets/TMC2209_datasheet_rev1.09.pdf)
- [TMC2209 Product Page (Analog Devices)](https://www.analog.com/en/products/tmc2209.html)
- [BTT TMC2209 Wiki](https://global.bttwiki.com/TMC2209.html)

### RP2040 Resources
- [RP2040 Datasheet (Raspberry Pi)](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
- [RP2040 Specifications (Raspberry Pi)](https://www.raspberrypi.com/products/rp2040/specifications/)

### Community / Reviews
- [CNX Software -- BTT SKR Pico Review](https://www.cnx-software.com/2022/01/27/btt-skr-pico-a-raspberry-pi-rp2040-based-3d-printer-control-board/)
- [3DPrinters-Guide -- SKR Pico V1.0 Review](https://3dprinters-guide.com/bigtreetech-skr-pico-v1-0-review-the-perfect-upgrade-for-your-voron/)
- [GitHub Issues -- bigtreetech/SKR-Pico](https://github.com/bigtreetech/SKR-Pico/issues)
- [Voron Design -- SKR Pico V1.0 Wiring](https://docs.vorondesign.com/build/electrical/v0_skr_pico_wiring.html)
- [Klipper Discourse -- SKR Pico SPI Pin Conflict](https://klipper.discourse.group/t/skr-pico-pin-gpio3-is-reserved-for-spi0a/10437)
