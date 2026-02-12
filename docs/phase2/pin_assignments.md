# Pin Assignment Table

**For:** Phase 2 Memo, Table 5
**Author:** Willem
**Date:** 2026-02-12
**Status:** Rough draft — assumes Pi 4B, SKR Pico V1.0, E-axis driver

---

## 1. SKR Pico V1.0 — Pin Assignments (Active Pins Only)

Only pins used in the W26 project are listed. Unused axes (X, Y, Z), heaters, thermistors, and BLTouch are omitted.

| Pin | Signal | Direction | Voltage | Connected To | Klipper Config |
|-----|--------|-----------|---------|--------------|----------------|
| gpio14 | E Step | Output | 3.3V | TMC2209 E-axis (internal) | `step_pin: gpio14` |
| gpio13 | E Direction | Output | 3.3V | TMC2209 E-axis (internal) | `dir_pin: gpio13` |
| gpio15 | E Enable | Output (active low) | 3.3V | TMC2209 E-axis (internal) | `enable_pin: !gpio15` |
| gpio9 | TMC UART RX | Input | 3.3V | Shared UART bus, all 4 drivers (internal) | `uart_pin: gpio9` |
| gpio8 | TMC UART TX | Output | 3.3V | Shared UART bus via 1kΩ (internal) | `tx_pin: gpio8` |
| gpio16 | E DIAG / Filament | Input | 3.3V | TMC2209 E StallGuard output (jumper required) | `diag_pin: ^gpio16` (stretch goal) |
| gpio24 | Neopixel | Output | 3.3V | On-board WS2812 RGB LED | Optional status indicator |
| gpio17 | Fan0 | Output (PWM) | VIN (24V) | Cooling fan (if TMC2209 needs active cooling) | `[fan] pin: gpio17` |
| USB-C | USB Data | Bidirectional | USB 2.0 | Pi USB-A port (Klipper serial) | `serial: /dev/serial/by-id/usb-Klipper_rp2040_*` |
| VIN+ | Power input | — | 24V DC | UR30 24V distribution point | — |
| VIN- | Power ground | — | 0V | GND bus | — |
| E Motor Header | A1, A2, B1, B2 | Output | 24V chopped | Stepper motor 4-wire | JST-XH 4-pin |

### TMC2209 UART Address Map

| Driver Slot | UART Address | MS1 | MS2 | Used? |
|-------------|-------------|-----|-----|-------|
| X | 0 | LOW | LOW | No |
| Z | 1 | HIGH | LOW | No |
| Y | 2 | LOW | HIGH | No |
| **E (pump)** | **3** | **HIGH** | **HIGH** | **Yes** |

---

## 2. Raspberry Pi 4B — Pin Assignments

| Pin # | Pin Name | Signal | Direction | Voltage | Connected To |
|-------|----------|--------|-----------|---------|--------------|
| 2 | 5V Power | +5V input | Input | 5.0V | Buck converter VOUT (via polyfuse) |
| 4 | 5V Power | +5V input | Input | 5.0V | Tied to pin 2 (same rail) |
| 6 | Ground | GND | — | 0V | Buck converter GND / GND bus |
| USB-A | USB Host | USB serial | Bidirectional | USB 2.0 | SKR Pico USB-C |
| Ethernet | RJ45 | Ethernet | Bidirectional | Gigabit | Gigabit switch (RTDE + network) |

**Notes:**
- Pins 2 and 4 are both connected to the 5V rail. Either or both can be used for power input.
- No GPIO pins are used for signal I/O. All communication is via USB (to SKR Pico) and Ethernet (to UR30).
- Power via GPIO header bypasses the USB-C PD negotiation and the onboard polyfuse — external polyfuse is required.

---

## 3. UR30 Controller Box — Connections

| Connector | Terminal | Signal | Direction | Voltage | Connected To |
|-----------|----------|--------|-----------|---------|--------------|
| Power Block | PWR | +24V output | Output | 24V DC | 3A blade fuse → distribution point |
| Power Block | GND | 0V reference | — | 0V | GND bus |
| Ethernet | RJ45 | RTDE + network | Bidirectional | Gigabit | Gigabit switch |

**Notes:**
- Using the **internal** 24V supply (2A continuous, 3.5A burst at 33% duty).
- The lower two terminals (24V, 0V) on the Power Block are for external PSU input — unused unless motor current exceeds budget.
- Tool I/O flange is **not used** (insufficient current: 600mA typical).

---

## 4. Gigabit Ethernet Switch — Port Assignments

| Port | Device | Cable | Notes |
|------|--------|-------|-------|
| 1 | UR30 Controller | Cat5e, 1–3 m | RTDE traffic |
| 2 | Raspberry Pi 4B | Cat5e, 0.5–1 m | RTDE + SSH + Moonraker |
| 3 | Pi 400 (optional) | Cat5e, 1–3 m | SSH + Mainsail web UI |
| 4–5 | Unused | — | Available for expansion |

---

## 5. Pololu D24V22F5 Buck Converter — Pin Assignments

| Pin | Signal | Connected To | Notes |
|-----|--------|--------------|-------|
| VIN | +24V input | 24V distribution point | 22 AWG |
| GND | Ground | GND bus | 22 AWG |
| VOUT | +5.0V output | Pi GPIO pin 2 (via polyfuse) | 22 AWG |
| EN | Enable (active high) | Floating (internal pull-up = always on) | Or tie to VIN |
| PG | Power Good | Optional: Pi GPIO for monitoring | Open drain, active low when fault |

---

## 6. Summary — All External Wired Connections

This is the complete list of wires/cables that must be physically connected during assembly:

| # | From | To | Type | Length |
|---|------|----|------|--------|
| 1 | UR30 Power Block PWR | Blade fuse input | 18 AWG red wire | 0.5–1.0 m |
| 2 | Blade fuse output | TVS + cap + distribution | 18 AWG red wire | 0.1 m |
| 3 | UR30 Power Block GND | GND bus | 18 AWG black wire | 0.5–1.0 m |
| 4 | Distribution +24V | SKR Pico VIN+ | 18 AWG red wire | 0.1–0.3 m |
| 5 | GND bus | SKR Pico VIN- | 18 AWG black wire | 0.1–0.3 m |
| 6 | Distribution +24V | Buck converter VIN | 22 AWG red wire | 0.1–0.3 m |
| 7 | GND bus | Buck converter GND | 22 AWG black wire | 0.1–0.3 m |
| 8 | Buck converter VOUT | Polyfuse → Pi GPIO pin 2 | 22 AWG red wire | 0.1–0.3 m |
| 9 | Buck converter GND | Pi GPIO pin 6 | 22 AWG black wire | 0.1–0.3 m |
| 10 | SKR Pico E motor header | Stepper motor | 4-wire (per motor) | ≤ 3 m |
| 11 | Pi USB-A | SKR Pico USB-C | USB cable (shielded) | 0.3–1.0 m |
| 12 | UR30 Ethernet | Gigabit switch | Cat5e patch cable | 1–3 m |
| 13 | Pi Ethernet | Gigabit switch | Cat5e patch cable | 0.5–1 m |
| 14 | Pi 400 Ethernet (optional) | Gigabit switch | Cat5e patch cable | 1–3 m |

**Total wire/cable count:** 14 (13 if Pi 400 is omitted)

---

## Figure/Table Caption

**Table 5.** Pin assignment summary for all devices in the W26 Cobot Axis system. The SKR Pico uses the E-axis driver slot (TMC2209 at UART address 3) with step, direction, and enable on gpio14/13/15. The Raspberry Pi receives 5.1V power on GPIO pins 2+6 and communicates with the SKR Pico via USB serial. The UR30 provides 24V from the controller box power block and communicates via RTDE over Ethernet.
