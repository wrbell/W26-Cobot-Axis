# Circuit Schematic — Power Distribution and Signal Connections

**For:** Phase 2 Memo, Figure 2
**Author:** Willem
**Date:** 2026-02-12
**Status:** Rough draft — redraw in KiCad or draw.io for Word submission

---

## Schematic Description

The circuit has two domains: **power distribution** (24V from UR30 to all devices) and **signal connections** (data paths between devices).

---

## 1. Power Distribution

### 1.1 Source: UR30 Controller Box Power Block

```
UR30 Controller Box — Power Block (4 terminals)
┌──────────────────────────────────┐
│  PWR (+24V) ─────┐   GND (0V) ──┐
│  24V (ext)       │   0V (ext)   │
└──────────────────│──────────────│─┘
                   │              │
              ┌────┴────┐    ┌───┴───┐
              │  F1     │    │       │
              │  3A     │    │  GND  │
              │  Blade  │    │  Bus  │
              │  Fuse   │    │       │
              └────┬────┘    └───┬───┘
                   │              │
              ┌────┴────┐        │
              │  D1     │        │
              │ SMBJ24CA│        │
              │  TVS    │────────┤
              │ (bidir) │        │
              └────┬────┘        │
                   │              │
              ┌────┴────┐        │
              │  C1     │        │
              │ 100µF   │        │
              │  35V    │────────┤
              │ electr. │        │
              └────┬────┘        │
                   │              │
         ┌─── 24V Distribution ──┴─── GND Bus ───┐
         │         Point                          │
    ┌────┴────┐                          ┌───────┴───────┐
    │         │                          │               │
    ▼         ▼                          ▼               ▼
  SKR Pico  Buck Conv.              SKR Pico GND    Buck Conv. GND
  VIN+      VIN+                    VIN-            GND
```

### 1.2 Branch A: 24V Direct to SKR Pico

| Parameter | Value |
|-----------|-------|
| Connection | 24V distribution → SKR Pico VIN screw terminal |
| Wire gauge | 18 AWG (carries motor current, up to ~1.2A peak) |
| Protection | 100µF/35V bulk cap at distribution point (shared) |
| SKR Pico onboard | 5V buck → 3.3V LDO for RP2040 logic |
| SKR Pico VMOT | 24V direct to TMC2209 motor supply |

### 1.3 Branch B: 24V → 5.1V Buck Converter → Pi

```
24V Distribution ──[18 AWG]──▶ Pololu D24V22F5
                                ┌─────────────────┐
                                │  VIN  ───  VOUT  │──[22 AWG]──▶ Pi GPIO Pin 2 (5V)
                                │  GND  ───  GND   │──[22 AWG]──▶ Pi GPIO Pin 6 (GND)
                                │  EN (floating=on) │
                                │  PG (power good)  │  (optional: monitor with Pi GPIO)
                                └─────────────────┘
                                        │
                                   ┌────┴────┐
                                   │  PF1    │
                                   │  2A     │
                                   │ Polyfuse│
                                   │ (PTC)   │
                                   └────┬────┘
                                        │
                                   Pi GPIO Pin 2 (+5V)
                                   Pi GPIO Pin 6 (GND)
```

| Parameter | Value |
|-----------|-------|
| Converter | Pololu D24V22F5 (fixed 5.0V output, 2.2A max) |
| Input | 24V from distribution point |
| Output | 5.0V, design current 1.5A |
| Wire gauge (input) | 22 AWG (low current at 24V: ~0.35A) |
| Wire gauge (output) | 22 AWG (1.5A at 5V) |
| Protection | 2A resettable PTC polyfuse on 5V output rail |
| Pi power pins | Pin 2 or 4 (+5V), Pin 6 (GND) |
| Note | Bypasses USB-C PD; no onboard polyfuse protection |

### 1.4 Branch C: Motor Drive Path

```
SKR Pico TMC2209 (E-axis)
┌──────────────────────┐
│  VMOT ← 24V (from VIN)
│  A1 ────────────┐
│  A2 ────────────┤──── Stepper Motor 4-wire
│  B1 ────────────┤     (JST-XH connector on board;
│  B2 ────────────┘      extend with appropriate wire)
│  GND ← Board GND
└──────────────────────┘
```

| Parameter | Value |
|-----------|-------|
| Motor connector | JST-XH 4-pin on SKR Pico (E-axis header) |
| Motor cable | Per motor spec; 4-wire (A1, A2, B1, B2) |
| Cable length | ≤ 3 m (constraint C-07) |
| Protection | TMC2209 internal overcurrent + thermal shutdown |
| Current | Set via UART: run_current 0.580A, hold_current 0.400A |

---

## 2. Signal Connections

### 2.1 Ethernet (RTDE)

```
UR30 Ethernet Port ──[Cat5e, 1-3m]──▶ Gigabit Switch Port 1
Pi Ethernet Port   ──[Cat5e, 1-3m]──▶ Gigabit Switch Port 2
Pi 400 (optional)  ──[Cat5e, 1-3m]──▶ Gigabit Switch Port 3  (dashed — optional)
```

| Parameter | Value |
|-----------|-------|
| Protocol | RTDE over TCP/IP, port 30004 |
| Cable | Cat5e or Cat6, shielded recommended |
| Switch | Unmanaged gigabit, 5-port minimum |
| IP config | Same subnet (e.g., 192.168.1.x) |

### 2.2 USB Serial (Klipper MCU Communication)

```
Pi USB-A Port ──[USB-A to USB-C cable, 0.3-1.0m]──▶ SKR Pico USB-C Port
```

| Parameter | Value |
|-----------|-------|
| Protocol | Klipper binary MCU protocol over USB 2.0 Full-Speed (12 Mbps) |
| Cable | USB-A (Pi) to USB-C (SKR Pico), shielded, ≤ 1m |
| Device path | `/dev/serial/by-id/usb-Klipper_rp2040_<ID>-if00` |
| Note | USB also provides 5V from Pi to SKR Pico, but SKR Pico should be powered from 24V VIN for TMC2209 to work |

### 2.3 SKR Pico Internal (E-axis TMC2209)

These are internal board connections — no external wiring needed. Documented for the schematic.

| Signal | Pin | Direction | Description |
|--------|-----|-----------|-------------|
| E Step | gpio14 | RP2040 → TMC2209 | Step pulse |
| E Dir | gpio13 | RP2040 → TMC2209 | Direction |
| E Enable | gpio15 (active low) | RP2040 → TMC2209 | Driver enable |
| UART RX | gpio9 | TMC2209 → RP2040 | Shared UART bus (4 drivers) |
| UART TX | gpio8 | RP2040 → TMC2209 | Shared UART bus (via 1kΩ) |
| E DIAG | gpio16 | TMC2209 → RP2040 | StallGuard output (jumper required) |

---

## 3. Grounding

**Star topology grounding** at a central terminal block or bus bar:

```
               ┌─── Central GND Bus ───┐
               │                        │
          ┌────┴────┐             ┌────┴────┐
          │         │             │         │
     UR30 GND   Buck Conv.   SKR Pico    Pi GND
     (0V pin)    GND          GND       (GPIO pin 6)
```

- All grounds tied at a single point to prevent ground loops
- Use 18 AWG or thicker for the GND bus
- Short, low-impedance connections

---

## 4. Protection Component Summary

| Ref | Component | Value | Purpose | Location |
|-----|-----------|-------|---------|----------|
| F1 | Blade fuse | 3A, ATC/ATO | Overcurrent on 24V main | Inline between UR30 PWR and distribution |
| D1 | TVS diode | SMBJ24CA (bidirectional, 24V) | Transient/ESD suppression | Across 24V and GND at distribution point |
| C1 | Electrolytic cap | 100µF / 35V | Input voltage smoothing | At 24V distribution point |
| PF1 | Polyfuse | 2A resettable PTC | Pi overcurrent protection | Between buck converter output and Pi 5V |
| C2 | Ceramic cap | 100nF | Buck converter input decoupling | At buck converter VIN (per Pololu datasheet) |
| C3 | Ceramic cap | 100nF | Buck converter output decoupling | At buck converter VOUT (per Pololu datasheet) |

---

## 5. Wire Schedule

| Connection | Wire Gauge | Color (Suggested) | Length | Current |
|------------|------------|-------------------|--------|---------|
| UR30 PWR (+24V) → Fuse | 18 AWG | Red | 0.5–1.0 m | ≤ 2A |
| UR30 GND → GND bus | 18 AWG | Black | 0.5–1.0 m | ≤ 2A |
| Distribution → SKR Pico VIN+ | 18 AWG | Red | 0.1–0.3 m | ≤ 1.2A |
| Distribution → SKR Pico GND | 18 AWG | Black | 0.1–0.3 m | ≤ 1.2A |
| Distribution → Buck VIN | 22 AWG | Red | 0.1–0.3 m | ≤ 0.35A |
| Distribution → Buck GND | 22 AWG | Black | 0.1–0.3 m | ≤ 0.35A |
| Buck VOUT → Pi GPIO pin 2 | 22 AWG | Red | 0.1–0.3 m | ≤ 1.5A |
| Buck GND → Pi GPIO pin 6 | 22 AWG | Black | 0.1–0.3 m | ≤ 1.5A |
| SKR Pico E-axis → Motor | Per motor spec | Per convention | ≤ 3 m | ≤ 1.2A peak |

---

## Figure Caption

**Figure 2.** Circuit schematic showing power distribution from the UR30 controller's 24V power block through a 3A blade fuse and TVS diode to two branches: (a) 24V direct to the SKR Pico VIN for stepper motor drive, and (b) a Pololu D24V22F5 buck converter providing 5.1V to the Raspberry Pi via GPIO header. Signal connections include Ethernet (RTDE), USB serial (Klipper), and the 4-wire stepper motor cable. Protection components include a TVS diode (SMBJ24CA), bulk capacitor (100µF/35V), and resettable polyfuse (2A PTC) on the Pi 5V rail.
