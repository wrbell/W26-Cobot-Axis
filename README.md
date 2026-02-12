# W26 Cobot Axis — UR30 7th Axis for Metal Paste Dispensing

**Course:** ME 472 — Mechatronics, Winter 2026, University of Michigan
**Team:** Willem (Software/EE), Dawood (Mechanical)
**Instructor:** Prof. Pannier

## Overview

A stepper-motor-driven pump that functions as a 7th axis on a Universal Robots UR30 collaborative robot. The UR30 commands extrusion of **metal paste** through RTDE (Real-Time Data Exchange), and a Raspberry Pi translates those commands into Klipper G-code to drive a stepper motor via a BigTreeTech SKR Pico board.

## System Architecture

```
                              ┌─── Pi400 (optional HMI / SSH / Mainsail web UI)
                              │
UR30 Robot Controller  ──RTDE/TCP-IP──▶  Pi (Klipper host + RTDE bridge)  ──USB Serial──▶  SKR Pico (RP2040)  ──▶  Stepper Motor  ──▶  Pump
     (URScript)              (gigabit switch)                                  (Klipper MCU)         (metal paste dispensing)
```

| Link | Protocol | Latency |
|------|----------|---------|
| UR30 ↔ Pi | RTDE over TCP/IP (port 30004) | 2–5 ms |
| Pi → Klipper | Unix socket (`/tmp/klippy_uds`) | < 1 ms |
| Pi ↔ SKR Pico | USB serial (Klipper MCU protocol) | 1–3 ms |
| SKR Pico → Stepper | TMC2209 (StealthChop/SpreadCycle) | < 0.1 ms |
| **End-to-end** | | **~5–20 ms typical** |

The Pi400 is an **optional** HMI for SSH, web UI, and monitoring. The system runs standalone: UR30 → Pi → SKR Pico → stepper.

## Hardware

| Component | Details |
|-----------|---------|
| Robot | Universal Robots UR30 (6-axis, 30 kg payload) |
| Control Pi | Raspberry Pi (headless) — Klipper host + Moonraker + RTDE bridge daemon |
| HMI (optional) | Raspberry Pi 400 — SSH, Mainsail/Fluidd web UI |
| MCU Board | BigTreeTech SKR Pico V1.0 (RP2040, 4x TMC2209, 85×56 mm) |
| Stepper Motor | TBD — selection depends on pump torque requirements |
| Pump | TBD — metal paste dispensing (syringe, peristaltic, or progressive cavity) |
| Power | 24V from UR30 controller → buck converter(s) → 5.1V for Pi; 24V direct to SKR Pico |

## Software Stack

- **Klipper** — firmware on SKR Pico, host on Pi. `[manual_stepper]` config for single-axis control.
- **Moonraker** — API layer on Pi, exposes Klipper via HTTP/WebSocket/JSON-RPC.
- **RTDE Bridge Daemon** — Python service on Pi, translates UR30 register values to Klipper G-code via Unix socket.
- **URScript** — program on UR30 teach pendant, writes extrusion commands to RTDE output registers.
- **`ur_rtde`** — SDU library (C++ with Python bindings) for RTDE communication.

## Project Schedule

| Phase | Description | Timeline |
|-------|-------------|----------|
| 1 | Ideation and Scope | Complete |
| 2 | Design and Preliminary Analysis | Feb 9 – Mar 22 (in progress) |
| 3 | Build and Additional Design/Analysis | Mar 23 – Apr 5 |
| 4 | Test and Reporting | Apr 6 – Apr 23 |

**Target completion:** Mar 31, 2026
**Final report due:** Apr 23, 2026
**Oral presentation:** Apr 24, 2026 (6:30–9:30 PM)

See [`schedule.md`](schedule.md) for the full weekly timeline and milestones.

## Repository Structure

```
├── CLAUDE.md                   # AI assistant context (Claude Code)
├── README.md                   # This file
├── schedule.md                 # Accelerated project schedule
├── todo.md                     # Project task tracker (Bolton process + phase deliverables)
├── reqs/                       # Requirements and design process
│   ├── about.md                # Course project overview and phase descriptions
│   ├── initial_scope.md        # Project scope definition
│   ├── phase2.md               # Phase 2 deliverable requirements
│   ├── phase3.md               # Phase 3/4 final report requirements
│   ├── process.md              # Bolton's 7-step design process
│   ├── information_needs.md    # Data/information gaps per task
│   └── trade_lingua_franca_vs_klipper.md  # Firmware trade study
├── tech_docs/                  # Technical research and reference docs
│   ├── UR30/                   # UR30 user manual, RTDE protocol research
│   ├── BigTree Controller/     # SKR Pico V1.0 specs, Klipper setup guide
│   ├── Klipper/                # Klipper protocols and API reference
│   └── Pi400/                  # Power requirements and budget
└── init_docs/                  # Meeting notes and source PDFs
```

## Key Documents

| Document | Description |
|----------|-------------|
| [`todo.md`](todo.md) | Full task list organized by Bolton's design process and project phases |
| [`reqs/information_needs.md`](reqs/information_needs.md) | What data we still need to gather, per task |
| [`reqs/trade_lingua_franca_vs_klipper.md`](reqs/trade_lingua_franca_vs_klipper.md) | Trade study: Klipper (4.70) vs Lingua Franca (1.95) |
| [`tech_docs/BigTree Controller/skr_pico_v1_specs.md`](tech_docs/BigTree%20Controller/skr_pico_v1_specs.md) | SKR Pico V1.0 complete hardware reference |
| [`tech_docs/UR30/ur_rtde_research.md`](tech_docs/UR30/ur_rtde_research.md) | RTDE protocol, register allocation, latency analysis |
| [`tech_docs/Klipper/klipper_protocols.md`](tech_docs/Klipper/klipper_protocols.md) | Klipper API surface and serial protocol |

## Design Process

Follows Bolton's Mechatronics 7-step design process (see [`reqs/process.md`](reqs/process.md)):

1. **The Need** — UR30 lacks a native extrusion axis for metal paste dispensing
2. **Problem Analysis** — constraints, performance requirements, failure modes (in progress)
3. **Specification** — formal design spec (in progress)
4. **Possible Solutions** — trade studies (Klipper vs LF complete; location, MCU, comms pending)
5. **Solution Selection** — Klipper selected; architecture documented
6. **Detailed Design** — Phase 2 deliverable: circuit diagrams, BOM, analysis
7. **Working Drawings** — final schematics, CAD, wiring diagrams

## Team

| Member | Role | Focus Areas |
|--------|------|-------------|
| Willem | Software / EE | RTDE comms, Klipper integration, firmware, electrical documentation |
| Dawood | Mechanical | Packaging, cabling, end effector mounting, 3D-printed components, procurement |
