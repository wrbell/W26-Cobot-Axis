# Power Requirements and Specifications -- Full Signal Chain

## W26 Cobot Axis Project: 24V Power Distribution Design

**Document scope:** Power input specs, current draw, voltage levels, and distribution design
for every device in the signal chain, all powered from the UR30 controller's 24V supply.

**Signal chain:**
```
UR30 Controller 24V  -->  Buck to 5.1V  -->  Pi (Klipper host + RTDE bridge)
                     -->  24V direct    -->  BTT Pico (onboard reg + VMOT)  -->  Stepper motor

Pi400 (optional HMI) sits on the same network for SSH/web UI -- not powered from UR30.
```

**Last updated:** 2026-02-12

---

## Table of Contents

1. [UR30 Controller -- 24V Power Source](#1-ur30-controller--24v-power-source)
2. [Raspberry Pi -- Klipper Host + RTDE Bridge](#2-raspberry-pi--klipper-host--rtde-bridge)
3. [Raspberry Pi 400 -- Optional HMI Terminal](#3-raspberry-pi-400--optional-hmi-terminal)
4. [BigTreeTech Pico (BTT Pico) -- Stepper Controller](#4-bigtreetech-pico-btt-pico--stepper-controller)
5. [NEMA 17 Stepper Motor -- Actuator](#5-nema-17-stepper-motor--actuator)
6. [Power Distribution Design](#6-power-distribution-design)
7. [Total Power Budget](#7-total-power-budget)
8. [Datasheet and Reference Links](#8-datasheet-and-reference-links)

---

## 1. UR30 Controller -- 24V Power Source

The UR30 provides two distinct 24V power points relevant to this project: the
**Controller Box I/O power block** and the **Tool I/O flange connector**. All data below
is taken directly from the UR30 User Manual (download from
[Universal Robots support](https://www.universal-robots.com/download/manuals-e-series/user/ur30/)
-- look up the specific revision matching the controller firmware in the lab).

### 1.1 Controller Box I/O -- Power Block (Manual pp. 82-84)

The Control Box has a 4-terminal **Power** block (PWR, GND, 24V, 0V).

| Parameter | Min | Typ | Max | Unit | Notes |
|-----------|-----|-----|-----|------|-------|
| Internal 24V supply voltage (PWR-GND) | 23 | 24 | 25 | V | |
| Internal 24V supply current (PWR-GND) | 0 | -- | 2 | A | *3.5 A for 500 ms at 33% duty cycle |
| External 24V input voltage (24V-0V) | 20 | 24 | 29 | V | If more current is needed |
| External 24V input current (24V-0V) | 0 | -- | 6 | A | With external PSU |

**Key points:**
- Default configuration uses the **internal** 24V supply: 2 A continuous, 3.5 A burst.
- If the project needs more than 2 A continuous, an **external 24V supply** can be
  connected to the lower two terminals (24V and 0V) of the Power block, supporting
  up to 6 A at 20-29 V input.
- Digital outputs (COx/DOx) are PNP type, IEC 61131-2 compliant, 1 A max per output,
  0.5 V max voltage drop.
- Digital inputs (EIx/SIx/CIx/DIx) are PNP+, 11-30 V ON region, 2-15 mA input current.

### 1.2 Tool I/O Flange Connector (Manual pp. 94, 101)

The 8-pin tool connector on Wrist 3 provides power and signals to end effectors.

**Tool connector pinout (at wrist flange):**

| Pin | Signal | Description |
|-----|--------|-------------|
| 1 | AI3 / RS485- | Analog in 3 or RS485- |
| 2 | AI2 / RS485+ | Analog in 2 or RS485+ |
| 3 | TO0/PWR | Digital Output 0 **or** 0V/12V/24V power |
| 4 | TO1/GND | Digital Output 1 **or** Ground |
| 5 | POWER | 0V/12V/24V (configurable via PolyScope) |
| 6 | TI0 | Digital Input 0 |
| 7 | TI1 | Digital Input 1 |
| 8 | GND | Ground |

**Tool I/O electrical specifications (Manual p. 101):**

| Parameter | Min | Typ | Max | Unit | Notes |
|-----------|-----|-----|-----|------|-------|
| Supply voltage in 24V mode | 23.5 | 24 | 24.8 | V | |
| Supply voltage in 12V mode | 11.5 | 12 | 12.5 | V | |
| Supply current (single pin) | -- | 600 | 2000** | mA | Pin 5 alone |
| Supply current (dual pin) | -- | 600 | 2000** | mA | Pins 3+5 combined |
| Supply capacitive load | -- | -- | 8000*** | uF | |

- \*\* 2 A peak for max 1 second, duty cycle max 10%. Average current over 10 seconds
  must not exceed typical (600 mA).
- \*\*\* 400 ms soft start time at power-on allows up to 8000 uF capacitive load.
  Hot-plugging capacitive loads is not allowed.
- A **protective diode** for inductive loads is highly recommended.

### 1.3 Recommendation for This Project

**Use the Controller Box Power block**, not the Tool I/O, as the primary 24V source.
The tool flange is limited to 600 mA typical (2 A peak burst only) which is insufficient
for the stepper motor alone. The Controller Box internal supply provides 2 A continuous,
and if needed the external input option raises this to 6 A.

Our total system draw is estimated at ~1.0-1.4 A (see Section 7). Two options:

- **Option A (simpler):** Use the internal 24V, accept that brief stepper acceleration
  peaks may approach the 2 A limit. The 3.5 A burst rating at 33% duty gives headroom.
- **Option B (recommended):** Connect an external 24V supply to the Power block's
  lower terminals (24V, 0V), gaining a 6 A budget with ample margin.

---

## 2. Raspberry Pi -- Klipper Host + RTDE Bridge

A single headless Raspberry Pi (Pi 4-class, BCM2711, quad-core Cortex-A72) serves as
the real-time control node: it runs the Klipper host (klippy), the RTDE bridge daemon,
and Moonraker. It receives RTDE commands from the UR30 over Ethernet and sends G-code
to the SKR Pico over USB serial. This Pi must be powered from the UR30's 24V supply
via a buck converter.

### 2.1 Power Input Specifications

| Parameter | Value | Notes |
|-----------|-------|-------|
| Input voltage (USB-C) | 5.1 V DC | Official spec |
| Recommended PSU | 5.1 V / 3.0 A (15.3 W) | Official Raspberry Pi USB-C PSU |
| Minimum supply current | 3.0 A | Required for stable operation |
| Absolute min voltage | 4.63 V | Below this the PMIC triggers under-voltage warning |
| Typical idle current draw | ~600 mA | Headless idle, no peripherals |
| Typical load current draw | ~1.0-1.2 A | CPU stress, Ethernet active |
| Peak current draw | ~1.4 A | All cores loaded + USB peripherals |
| Power via GPIO header (pin 2/4) | 5V | Bypasses USB-C PD negotiation; **no polyfuse protection** |

### 2.2 GPIO Voltage Levels

| Parameter | Value |
|-----------|-------|
| GPIO logic level | 3.3 V (LVCMOS) |
| GPIO output high | ~3.3 V |
| GPIO output low | ~0 V |
| GPIO input high threshold | ~1.8 V |
| GPIO input low threshold | ~0.8 V |
| Max GPIO source/sink current per pin | 16 mA (default drive strength) |
| Total GPIO current (all pins) | 50 mA max recommended |
| GPIO pin count | 40-pin header |
| 5V pins (pin 2, 4) | Connected directly to 5V rail |
| 3.3V pin (pin 1, 17) | From onboard 3.3V regulator, 50 mA available externally |

### 2.3 Power Input via GPIO Header (Relevant for This Project)

The Pi can be powered through GPIO pins 2 or 4 (5V) and pin 6 (GND) instead of
USB-C. This is the likely method when powering from the UR30 via a buck converter:

**Advantages:**
- Eliminates need for USB-C connector/cable
- Direct 5V rail connection
- Common approach in embedded/industrial applications

**Cautions:**
- No reverse-polarity protection on GPIO power pins
- No overcurrent protection (no polyfuse) -- the buck converter output must be
  properly fused or current-limited
- Voltage must be regulated to 5.0-5.25 V; the PMIC will flag under-voltage
  below ~4.63 V
- Add a Schottky diode or ideal-diode circuit if back-powering protection is needed

### 2.4 Notes for Klipper Host + RTDE Bridge Role

- Klipper host process (klippy) is CPU-light; typical CPU use is <10%
- RTDE bridge daemon adds minimal load (Python, event-driven)
- Ethernet is the primary data path (RTDE from UR30); draws ~0.2 A additional
- USB serial to SKR Pico for Klipper MCU communication
- No GPU load expected; headless operation, no HDMI output needed
- **Design current for Pi: 1.5 A at 5.1 V (7.65 W)** -- includes safety margin

### 2.5 Reference

- Pi 4B datasheet: https://datasheets.raspberrypi.com/rpi4/raspberry-pi-4-datasheet.pdf
- BCM2711 datasheet: https://datasheets.raspberrypi.com/bcm2711/bcm2711-peripherals.pdf
- Raspberry Pi hardware documentation: https://www.raspberrypi.com/documentation/computers/raspberry-pi.html

---

## 3. Raspberry Pi 400 -- Optional HMI Terminal

The Pi 400 is a Raspberry Pi 4-class SoC (BCM2711, quad-core Cortex-A72 @ 1.8 GHz)
built into a keyboard form factor. It sits on the same network as the control Pi and
is used for SSH access, Mainsail/Fluidd web UI, development, and monitoring. It is
**not** in the real-time control loop and does **not** need to be powered from the
UR30 -- it uses its own standard USB-C power supply.

### 3.1 Power Specifications (for reference only)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Input voltage (USB-C) | 5.1 V DC | Standard Raspberry Pi USB-C PSU |
| Recommended PSU | 5.1 V / 3.0 A (15.3 W) | Official Raspberry Pi USB-C PSU |
| Typical load current draw | ~1.0-1.2 A | Desktop use, Ethernet active |
| GPIO logic | 3.3 V LVCMOS | Same as all Pi models |

The Pi 400 is **not included in the UR30 power budget** since it is powered
independently. It can be removed from the setup entirely without affecting the
real-time control chain (UR30 -> Pi -> SKR Pico -> stepper).

### 3.2 References

- Raspberry Pi 400 product brief: https://datasheets.raspberrypi.com/pi400/pi400-product-brief.pdf
- BCM2711 datasheet: https://datasheets.raspberrypi.com/bcm2711/bcm2711-peripherals.pdf
- Raspberry Pi hardware documentation: https://www.raspberrypi.com/documentation/computers/raspberry-pi.html

---

## 4. BigTreeTech Pico (BTT Pico) -- Stepper Controller

The BTT Pico is an RP2040-based 3D printer controller board designed by BigTreeTech.
It is purpose-built for Klipper firmware and includes an onboard stepper driver.

### 4.1 Board Overview

| Parameter | Value |
|-----------|-------|
| MCU | RP2040 (dual Cortex-M0+ @ 133 MHz) |
| Flash | 2 MB (W25Q16) |
| Stepper driver (onboard) | TMC2209 (one channel, on some revisions two) |
| Firmware | Klipper (primary), Marlin (possible) |
| Communication to host | USB or UART serial |

### 4.2 Power Input Specifications

| Parameter | Value | Notes |
|-----------|-------|-------|
| Main power input (VIN / VMOT) | 12-24 V DC | Powers stepper driver motor supply |
| Absolute max VIN | 28 V | Do not exceed |
| Onboard 5V regulator | Yes (buck converter) | Steps VIN down to 5V for logic |
| 5V regulator output | 5 V / ~1 A | Powers RP2040 and peripherals |
| Onboard 3.3V regulator | Yes (LDO from 5V) | Powers RP2040 core and GPIO |
| 3.3V regulator output | 3.3 V / ~300 mA | |
| Board idle current from VIN | ~50-80 mA | At 24V, no motor active |
| Board current with motor active | Depends on motor current setting | See TMC2209 specs below |

### 4.3 TMC2209 Stepper Driver Specifications

The TMC2209 is a silent stepper driver with StallGuard and UART configuration.

| Parameter | Min | Typ | Max | Unit |
|-----------|-----|-----|-----|------|
| Motor supply voltage (VMOT) | 4.75 | -- | 29 | V |
| Motor coil current (RMS, per phase) | -- | -- | 1.4 (2.0 peak) | A |
| Logic supply voltage (VCC_IO) | 3.0 | 3.3 | 5.25 | V |
| UART interface voltage | 3.3 | -- | 5.0 | V |
| RDSon (high-side + low-side) | -- | 0.3 | -- | Ohm |
| Microstepping | 1/2 to 1/256 | -- | -- | steps |
| StallGuard threshold | Configurable via UART | | | |
| SpreadCycle / StealthChop | Both supported | | | |

**Current setting:** The RMS motor current is set via UART command or the VREF
potentiometer. At 24V VMOT with a typical NEMA 17 (1.5-1.7 A rated), the TMC2209
will be current-chopping, so actual draw from the 24V rail depends on motor speed
and load. Worst-case continuous draw from 24V:

```
I_24V = (V_motor_coil x I_motor_rms) / (V_supply x efficiency)
      = (coil_resistance x I_rms x I_rms) / (24 x 0.90)
```

For a 1.7 A motor at 24V: **~0.8-1.2 A from 24V** under typical extrusion loads.

### 4.4 GPIO and Signal Levels

| Parameter | Value |
|-----------|-------|
| RP2040 GPIO logic level | 3.3 V |
| GPIO max source/sink | 12 mA per pin |
| UART to host Pi | 3.3 V TTL (or USB) |
| Endstop inputs | 3.3 V logic, active low with pull-up |
| Thermistor inputs | Analog, 3.3 V reference |

### 4.5 References

- BTT Pico GitHub: https://github.com/bigtreetech/BTT-Pico
- BTT Pico schematic (in GitHub repo): includes full power path and TMC2209 wiring
- TMC2209 datasheet: https://www.trinamic.com/fileadmin/assets/Products/ICs_Documents/TMC2209_Datasheet_V103.pdf
- RP2040 datasheet: https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf

---

## 5. NEMA 17 Stepper Motor -- Actuator

NEMA 17 is a frame size standard (42 mm x 42 mm face). Electrical parameters vary
by model. Below are typical specifications for motors commonly used in 3D printer
extrusion (which aligns with this project's use case).

### 5.1 Typical NEMA 17 Specifications (Extrusion-Class)

| Parameter | Typical Range | Common Value | Unit |
|-----------|---------------|--------------|------|
| Step angle | 1.8 | 1.8 | degrees |
| Steps per revolution | 200 | 200 | steps |
| Rated voltage | 2.8-4.2 | 3.2 | V |
| Rated current (per phase) | 1.0-2.0 | 1.7 | A |
| Phase resistance | 1.5-2.5 | 1.8 | Ohm |
| Phase inductance | 2.5-4.5 | 3.2 | mH |
| Holding torque | 0.28-0.65 | 0.44 (45 Ncm) | Nm |
| Detent torque | 0.02-0.04 | 0.026 | Nm |
| Rotor inertia | 50-80 | 68 | g-cm^2 |
| Body length | 34-48 | 40 | mm |
| Shaft diameter | 5 | 5 | mm |
| Weight | 240-350 | 280 | g |
| Max operating temperature | 80 | 80 | deg C |
| Insulation class | B | B | -- |

### 5.2 Popular Models for 3D Printer Extrusion

| Model | Rated Current | Holding Torque | Resistance | Notes |
|-------|---------------|----------------|------------|-------|
| 17HS4401 | 1.7 A | 0.40 Nm (40 Ncm) | 1.5 Ohm | Very common, good balance |
| 17HS4401S | 1.7 A | 0.42 Nm | 1.5 Ohm | Variant with flat shaft |
| 17HS3401 | 1.3 A | 0.28 Nm | 2.4 Ohm | Lower torque, lower current |
| 42-34 (short body) | 0.95 A | 0.22 Nm | 3.6 Ohm | Pancake motor for direct drive |
| LDO-42STH48-2504AH | 1.0 A | 0.55 Nm | 5.0 Ohm | High-torque, higher resistance |

### 5.3 Voltage and Current Chopping Explanation

Stepper motors are **rated at a low voltage** (e.g., 3.2 V = 1.7 A x 1.8 Ohm) which is
the DC steady-state voltage at rated current. Modern chopper drivers like the TMC2209
operate at a much higher supply voltage (24 V) and rapidly switch the current on/off
to regulate it to the target RMS value. This provides:

- **Faster current rise time** through the coil inductance (better high-speed torque)
- **Precise current control** via PWM chopping
- **Higher supply voltage does NOT damage the motor** -- the driver controls current

The actual DC bus current drawn from the 24V supply is much less than the motor's
rated phase current because of the voltage ratio:

```
P_motor = I_rms^2 x R_coil  (at standstill/low speed)
I_24V   = P_motor / (24V x driver_efficiency)
        = (1.7^2 x 1.8) / (24 x 0.90)
        = 5.2 / 21.6
        = ~0.24 A at standstill

At speed, back-EMF reduces chopping duty, and dynamic current varies.
Typical average: 0.5-1.0 A from 24V for a 1.7 A motor under load.
Peak (acceleration): up to ~1.5 A briefly.
```

### 5.4 References

- NEMA 17 specification (NEMA ICS 16): Motor frame/mounting standard
- 17HS4401 datasheet (StepperOnline): https://www.omc-stepperonline.com/download/17HS4401.pdf
- TMC2209 application note on motor selection: https://www.trinamic.com/support/eval-kits/

---

## 6. Power Distribution Design

### 6.1 Architecture Overview

```
                    UR30 Controller Box
                    Power Block (24V)
                         |
                    PWR (+24V) ---- GND (0V)
                         |              |
                    +----+----+---------+----+
                    |                        |
               [Buck #1]               [Direct 24V]
              24V -> 5.1V                    |
                    |                        |
                   Pi                   BTT Pico VIN
             (Klipper host              (VMOT + onboard
            + RTDE bridge)               5V/3.3V reg)
                    |                        |
               [USB serial]            TMC2209 driver
                    |                        |
               BTT Pico               NEMA 17 stepper

   Pi400 (optional HMI) -- powered independently, not shown in power chain
```

### 6.2 Buck Converter: 24V to 5V

The Raspberry Pi requires a regulated 5V supply. A buck (step-down) switching converter
is the correct topology for 24V-to-5V conversion due to the high step-down ratio
(poor efficiency with linear regulators: 5/24 = 21%, wasting 79% as heat).

**Requirements (single converter for the Pi):**

| Parameter | Value |
|-----------|-------|
| Output voltage | 5.0-5.25 V |
| Output current (design) | 1.5 A |
| Output current (peak) | 2.0 A |
| Input voltage range | 20-29 V |
| Ripple (max) | 50 mV p-p |

**Recommended buck converter modules:**

| Module | Input Range | Output | Max Current | Efficiency | Notes | Approx Price |
|--------|-------------|--------|-------------|------------|-------|-------------|
| Pololu D24V22F5 | 4.5-42 V | 5.0 V fixed | 2.2 A | ~90% | Small, well-documented | $8 |
| Pololu D24V50F5 | 4.5-38 V | 5.0 V fixed | 5.0 A | ~90% | Higher headroom | $13 |
| DROK LM2596 module | 4.5-40 V | Adjustable | 3.0 A | ~85% | Cheap, adjust pot to 5.1V | $3 |
| Adafruit 5V Buck (P/N 1385) | 7-36 V | 5.0 V fixed | 3.0 A | ~85% | Breadboard-friendly | $10 |
| Murata OKI-78SR-5/1.5 | 7-36 V | 5.0 V fixed | 1.5 A | ~90% | Drop-in 7805 replacement, TO-220 package | $5 |
| Traco Power TSR 1-2450 | 6.5-36 V | 5.0 V fixed | 1.0 A | ~90% | SIP-3 package, simple | $5 |

**Recommendation:**
- **Pi:** Pololu D24V22F5 (5V/2.2A) or equivalent. Provides full 2 A+ headroom,
  high efficiency, compact form factor, and well-documented for Pi projects.
  Available on DigiKey. The Murata OKI-78SR-5/1.5 is also a good choice if the
  1.5 A rating provides sufficient margin.

### 6.3 3.3V Logic Supply

The 3.3V supply for logic signals is handled by the **onboard regulators** on each board:
- **Pi:** Onboard 3.3V LDO on the PMIC (powered from 5V rail)
- **BTT Pico:** Onboard 3.3V LDO (powered from its onboard 5V buck, which runs off VIN)

No external 3.3V regulator is needed. The Pi communicates with the BTT Pico over USB
serial; both devices share 3.3V logic levels.

### 6.4 24V Direct to BTT Pico

The BTT Pico's VIN (VMOT) input accepts 12-24V directly. Connect the UR30's 24V
Power block output directly to the BTT Pico power input terminals:

- **VIN+ / VMOT+** <-- UR30 PWR (24V)
- **VIN- / GND** <-- UR30 GND (0V)

The BTT Pico's onboard buck converter generates 5V for the RP2040, and the onboard
LDO generates 3.3V from that 5V. No external regulation is needed for the BTT Pico
itself.

### 6.5 Wiring Recommendations

| Connection | Wire Gauge (AWG) | Notes |
|------------|------------------|-------|
| UR30 24V to distribution point | 18 AWG (min) | Carries full system current (~1.4 A peak) |
| 24V to BTT Pico VIN | 20 AWG | Motor current path (~1.2 A peak) |
| 24V to buck converter input | 22 AWG | Low current at 24V (~0.35 A for Pi) |
| Buck converter 5V to Pi GPIO | 20 AWG | 1.5 A at 5V |
| GND bus (common ground) | 18 AWG | All grounds must be tied together |
| USB cable (Pi to BTT Pico) | -- | Standard USB cable, minimal current |

### 6.6 Protection Components

| Component | Purpose | Recommendation |
|-----------|---------|----------------|
| Blade fuse (3A) on 24V input | Overcurrent protection | ATC/ATO automotive fuse holder |
| TVS diode (24V, bidirectional) | Transient/ESD protection | Littelfuse SMBJ24CA or equivalent |
| Flyback diode on stepper | Inductive kickback protection | 1N4007 or SS34 Schottky across motor leads |
| Bulk capacitor at 24V bus | Voltage stability | 100 uF / 35V electrolytic at distribution point |
| Decoupling capacitors | Local noise filtering | 100 nF ceramic at each regulator input/output |
| Polyfuse on 5V output | Pi overcurrent protection | 2A resettable PTC fuse |

### 6.7 Grounding

**All grounds must be common (star topology preferred):**
- UR30 0V/GND
- Buck converter GND
- BTT Pico GND
- Pi GND (via GPIO pin 6)

Use a central grounding point (busbar or terminal block) with short, low-impedance
connections to each device. This prevents ground loops and ensures signal integrity
on the UART/serial lines.

---

## 7. Total Power Budget

### 7.1 Current Budget at 24V Input

| Device | Current from 24V | Power (W) | Notes |
|--------|------------------|-----------|-------|
| Pi (via buck @ ~90% eff) | 0.35 A | 8.5 W | 1.5A x 5.1V / 0.90 = 8.5W; 8.5/24 = 0.35A |
| BTT Pico (logic, no motor) | 0.08 A | 1.9 W | Board quiescent at 24V |
| NEMA 17 stepper (via TMC2209) | 0.5-1.0 A | 12-24 W | Varies with speed/load |
| **TOTAL (typical)** | **~1.0 A** | **~23 W** | Normal extrusion operation |
| **TOTAL (peak/worst-case)** | **~1.4 A** | **~34 W** | Acceleration + CPU loaded |

### 7.2 Current Budget at 5V Rail

| Device | Current at 5V | Power (W) |
|--------|---------------|-----------|
| Pi | 1.5 A (design) | 7.65 W |
| BTT Pico (internal, from VIN) | ~0.2 A | 1.0 W |

### 7.3 Margin Analysis

**Using UR30 internal 24V supply (2 A continuous, 3.5 A burst @ 33% duty):**

| Scenario | Draw | Margin vs 2A | Status |
|----------|------|--------------|--------|
| Idle (all on, motor holding) | ~0.5 A | 1.5 A spare | OK |
| Normal operation (extrusion) | ~1.0 A | 1.0 A spare | OK |
| Peak (acceleration burst) | ~1.4 A | 0.6 A spare | OK (within continuous) |
| Absolute worst case | ~1.8 A | 0.2 A | OK -- burst rating provides headroom |

**Using external 24V supply via Power block (6 A max):**

All scenarios have >4 A of margin. This is the recommended approach if any
additional peripherals (fans, sensors, LEDs) are planned.

### 7.4 Summary

The system power budget is well within the UR30's capabilities with a single Pi:
- **Typical continuous draw: ~1.0 A at 24V (~23 W)**
- **Peak draw: ~1.4 A at 24V (~34 W)**
- **UR30 internal 24V provides 2A continuous** -- adequate with good margin
- **External 24V option provides 6A** -- ample for future expansion

The Pi400 (optional HMI) is powered independently and does not affect this budget.

---

## 8. Datasheet and Reference Links

### 8.1 Raspberry Pi

| Document | URL |
|----------|-----|
| Pi 4B datasheet | https://datasheets.raspberrypi.com/rpi4/raspberry-pi-4-datasheet.pdf |
| Pi 400 product brief | https://datasheets.raspberrypi.com/pi400/pi400-product-brief.pdf |
| BCM2711 peripherals | https://datasheets.raspberrypi.com/bcm2711/bcm2711-peripherals.pdf |
| RP2040 datasheet | https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf |
| Pi GPIO pinout | https://pinout.xyz/ |
| Pi power/PSU documentation | https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supply |

### 8.2 BigTreeTech Pico

| Document | URL |
|----------|-----|
| BTT Pico GitHub repo | https://github.com/bigtreetech/BTT-Pico |
| BTT Pico schematic | https://github.com/bigtreetech/BTT-Pico/tree/master/Hardware |
| BTT Pico Klipper config | https://github.com/bigtreetech/BTT-Pico/tree/master/Firmware/Klipper |

### 8.3 TMC2209 Stepper Driver

| Document | URL |
|----------|-----|
| TMC2209 datasheet (v1.09) | https://www.trinamic.com/fileadmin/assets/Products/ICs_Documents/TMC2209_Datasheet_V103.pdf |
| TMC2209 application note | https://www.trinamic.com/products/integrated-circuits/details/tmc2209-la/ |
| Trinamic (Analog Devices) product page | https://www.analog.com/en/products/tmc2209.html |

### 8.4 NEMA 17 Stepper Motor

| Document | URL |
|----------|-----|
| 17HS4401 datasheet | https://www.omc-stepperonline.com/download/17HS4401.pdf |
| NEMA motor standards (ICS 16) | https://www.nema.org/standards/view/nema-ics-16-motion-step-motors |
| StepperOnline NEMA 17 catalog | https://www.omc-stepperonline.com/nema-17-stepper-motor |

### 8.5 UR30 Robot Controller

| Document | Location |
|----------|----------|
| UR30 User Manual | https://www.universal-robots.com/download/manuals-e-series/user/ur30/ |
| Controller I/O specs | Manual Section 9.4, pp. 82-84 |
| Tool I/O connector pinout | Manual Section 9.7.1, p. 94 |
| Tool I/O electrical specs | Manual Section 9.7.6, p. 101 |
| UR support site | https://www.universal-robots.com/download/ |

### 8.6 Buck Converters (Recommended)

| Product | URL |
|---------|-----|
| Pololu D24V22F5 | https://www.pololu.com/product/2858 |
| Pololu D24V50F5 | https://www.pololu.com/product/2851 |
| Murata OKI-78SR-5/1.5-W36-C | https://www.murata.com/en-us/products/productdetail?partno=OKI-78SR-5%2F1.5-W36-C |
| Traco TSR 1-2450 | https://www.tracopower.com/int/series/tsr-1 |

---

## Appendix A: Quick Reference Card

```
POWER SOURCE:     UR30 Controller Box, Power block
                  Internal: 24V / 2A continuous (3.5A burst)
                  External: 24V / 6A (with added PSU)

PI (headless):    5.1V via GPIO pins 2+6 from buck converter
                  Klipper host + RTDE bridge + Moonraker
                  Design: 1.5A @ 5.1V = 7.65W
                  GPIO: 3.3V logic

BTT PICO:         24V direct to VIN (onboard 5V + 3.3V regs)
                  Logic: 3.3V (RP2040)
                  TMC2209: 24V VMOT, up to 1.4A RMS to motor

STEPPER:          NEMA 17, 1.7A rated, ~0.44 Nm
                  Driven at 24V via TMC2209 current chopping
                  24V bus draw: 0.5-1.0A typical

PI400 (optional): HMI terminal on same network (SSH, web UI)
                  Powered independently -- not in UR30 power budget

TOTAL 24V DRAW:   ~1.0A typical, ~1.4A peak
TOTAL POWER:      ~23W typical, ~34W peak
```
