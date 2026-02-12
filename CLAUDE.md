# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

University capstone project (ME472 - Mechatronics) to develop a stepper motor driver that takes commands from a Universal Robots UR30 controller to function as an additional (7th) axis of motion. The stepper motor provides extrusion control.

**System architecture (revised per Pannier Review):**
```
UR30 Robot Controller  ──RTDE/TCP-IP──▶  Pi400 (Klipper host)  ──▶  Slave Pi (comms bridge)  ──Serial──▶  BigTree Pico (RP2040)  ──▶  Stepper Motor
     (URScript)              (may need network switch)           (Klipper serial)              (firmware)        (extrusion)
```

**Communication chain:**
- UR30 ↔ Pi400: RTDE over TCP/IP (ethernet, may need a gigabit switch)
- Pi400 ↔ Slave Pi: Klipper control signals
- Slave Pi ↔ BigTree Pico: Serial (via Klipper)
- BigTree Pico → Stepper: PWM/TBD

**Power:** 5.1V, 24V from UR controller (powers Pi, microcontroller, and actuator).

**Languages:** URScript (robot side), C++ or MicroPython (RP2040/Pico firmware). Lingua Franca was considered but requires trade study vs Klipper.

## Repository Structure

- `reqs/` — Project requirements, scope definition, phase deliverables, and design process methodology
- `tech_docs/` — Technical documentation and manuals (UR30 User Manual, placeholders for BigTree Controller, Klipper, Pi400)
- `init_docs/` — Pannier Review meeting notes and accelerated schedule PDF
- `schedule.md` — Accelerated project schedule (target completion Mar 31, official submission Apr 24)

## Project Phases

| Phase | Description | Duration |
|-------|------------|----------|
| 1 | Ideation and Scope | 2 weeks (complete) |
| 2 | Design and Preliminary Analysis | 6 weeks (in progress) |
| 3 | Build and Additional Design/Analysis | 3 weeks |
| 4 | Test and Reporting | 3 weeks |

Final report due: **Thu Apr 23, 2026**. Report is max 2000 words with figures/tables (which don't count toward word limit).

## Key Technical Details

- **Robot:** Universal Robots UR30 (6-axis collaborative robot)
- **Master Pi:** Raspberry Pi 400 — runs Klipper as host, receives RTDE commands from UR30
- **Slave Pi:** Second Raspberry Pi — bridges comms between Klipper host and microcontroller
- **Microcontroller:** BigTree Pico (RP2040-based 3D printer controller variant)
- **Actuator:** Stepper motor (~24V) for extrusion control
- **Power:** 5.1V + 24V from UR controller
- **Firmware platform:** Klipper

## Open Questions (from Pannier Review)

- Latency impact of ethernet comms chain — is it acceptable relative to print speed? Can G-code execution be timeshifted if latency is predictable?
- URScript ↔ Klipper bidirectionality — what protocols does Klipper support? May need forked features.
- UR CAPs (URCaps) creation process
- Stallguard torque feedback from stepper back to URScript (stretch goal)
- Lingua Franca vs Klipper trade study (language/framework decision)
- Pi ↔ Microcontroller protocol trade (serial via Klipper vs alternatives)

## Team Responsibilities

- **Willem (Software/EE):** RTDE comms, Klipper integration, firmware, electrical documentation
- **Dawood (Mechanical):** Packaging, cabling, end effector, procurement

## Design Process

Follows Bolton's Mechatronics 7-step design process: need → problem analysis → specification → possible solutions → solution selection → detailed design → working drawings. Iteration between steps is expected.
