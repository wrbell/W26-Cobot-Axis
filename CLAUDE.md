# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

University capstone project (ME472 - Mechatronics) to develop a stepper motor driver that takes commands from a Universal Robots UR30 controller to function as an additional (7th) axis of motion. The stepper motor drives a pump for **metal paste dispensing/extrusion** (pump type TBD — syringe, peristaltic, or progressive cavity).

**System architecture:**
```
                              ┌─── Pi400 (HMI / SSH / monitoring)
                              │       (development terminal, not in real-time loop)
                              │
UR30 Robot Controller  ──RTDE/TCP-IP──▶  Pi (Klipper host + RTDE bridge)  ──USB Serial──▶  SKR Pico (RP2040)  ──▶  Stepper Motor  ──▶  Pump
     (URScript)              (gigabit switch)                                  (Klipper MCU)         (metal paste dispensing)
```

**Communication chain:**
- UR30 ↔ Pi: RTDE over TCP/IP on port 30004 (ethernet, needs a gigabit switch)
- Pi → Klipper: Unix socket (`/tmp/klippy_uds`) — lowest latency path
- Pi ↔ SKR Pico: USB serial (Klipper's native MCU protocol)
- SKR Pico → Stepper: TMC2209 drivers (StealthChop/SpreadCycle)
- Pi400: **optional** — sits on the same network for SSH access, Moonraker/Mainsail web UI, development, and monitoring. System must run standalone without it (UR30 → Pi → SKR Pico → stepper).
- Estimated end-to-end latency: 5–20ms typical

**Power:** 5.1V + 24V from UR controller power block (2A continuous, 3.5A burst). Total draw ~1.1A typical @ 24V.

**Software stack:** Klipper (chosen over Lingua Franca — see `trades/lingua_franca_vs_klipper.md`). RTDE bridge daemon on Pi translates UR commands to Klipper G-code. `[manual_stepper]` config for single-axis control.

## Task Tracking

**Always check `todo.md` before starting work.** It tracks:
- Bolton's 7-step design process progress
- Phase 1–4 deliverables with accelerated schedule (target Mar 31)
- Software development tasks (what's written, what's TODO, what needs hardware)
- Source code index with file locations and status

## Repository Structure

- `src/bridge/` — Python RTDE-to-Klipper bridge daemon (config, RTDE client, Klipper client, main loop)
- `src/klipper/` — Klipper configuration (`printer.cfg` for SKR Pico)
- `src/urscript/` — URScript programs for UR30 teach pendant
- `trades/` — Trade studies (comms protocol, MCU platform, Klipper vs Lingua Franca)
- `docs/` — Engineering analysis and technical reference (latency, register allocation, hardware specs)
- `reqs/` — Course requirements, scope, process docs
- `schedule.md` — Accelerated project schedule (target completion Mar 31, official submission Apr 24)
- `todo.md` — Master task tracker

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
- **Pi (headless):** Raspberry Pi — runs Klipper host + Moonraker + RTDE bridge daemon (real-time control node)
- **Pi400:** Raspberry Pi 400 — HMI, SSH terminal, web UI access (Mainsail/Fluidd), development. Not in the real-time loop.
- **Microcontroller:** BigTreeTech SKR Pico V1.0 (RP2040-based, 4x TMC2209 soldered, Klipper-compatible, 85x56mm). Product code 1060000513. Full specs in `docs/skr_pico_specs.md`.
- **Actuator:** Stepper motor + pump — will be provided to the team (specs TBD on receipt)
- **Power:** 24V from UR controller power block → buck converters → 5.1V for Pi; 24V direct to SKR Pico VIN
- **RTDE library:** `ur_rtde` (SDU, C++ with Python bindings) — recommended over official UR Python client

## Source Code

| Component | Location |
|-----------|----------|
| Bridge daemon (main loop) | `src/bridge/bridge_daemon.py` |
| Bridge config (registers, constants) | `src/bridge/config.py` |
| Klipper Unix socket client | `src/bridge/klipper_client.py` |
| RTDE client wrapper | `src/bridge/rtde_client.py` |
| Klipper printer config | `src/klipper/printer.cfg` |
| URScript extrusion program | `src/urscript/extrusion_control.script` |
| URScript system validation test | `src/urscript/test_basic.script` |
| URScript pump calibration test | `src/urscript/test_calibration.script` |

## Design Documents

| Topic | Location |
|-------|----------|
| Problem analysis (Bolton Step 2) | `docs/problem_analysis.md` |
| RTDE register allocation | `docs/register_allocation.md` |
| Latency analysis | `docs/latency_analysis.md` |
| Trade: Klipper vs Lingua Franca | `trades/lingua_franca_vs_klipper.md` |
| Trade: Communication protocol | `trades/comms.md` |
| Trade: MCU platform | `trades/mcu.md` |
| Information needs tracker | `reqs/information_needs.md` |

## Reference Documents

| Topic | Location |
|-------|----------|
| Klipper protocols & API | `docs/klipper_protocols.md` |
| SKR Pico V1.0 hardware specs | `docs/skr_pico_specs.md` |
| SKR Pico + Klipper setup | `docs/skr_pico_klipper_setup.md` |
| UR RTDE protocol & latency | `docs/ur_rtde.md` |
| Power requirements | `docs/pi_power.md` |

## Stretch Goals

- Stallguard torque feedback from TMC2209 → Klipper `register_remote_method` → RTDE → URScript
- URCap for teach pendant UI (Java SDK, not needed for MVP)
- Predictive G-code timeshifting using Klipper's ~100ms lookahead buffer

## Team Responsibilities

- **Willem (Software/EE):** RTDE comms, Klipper integration, firmware, electrical documentation
- **Dawood (Mechanical):** Packaging, cabling, end effector, procurement

## Design Process

Follows Bolton's Mechatronics 7-step design process: need → problem analysis → specification → possible solutions → solution selection → detailed design → working drawings. Iteration between steps is expected.
