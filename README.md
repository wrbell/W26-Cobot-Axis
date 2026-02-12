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
| Stepper Motor | TBD — will be provided to team; specs documented on receipt |
| Pump | TBD — will be provided to team; metal paste dispensing |
| Power | 24V from UR30 controller → buck converter(s) → 5.1V for Pi; 24V direct to SKR Pico |

## Software Stack

- **Klipper** — firmware on SKR Pico, host on Pi. `[manual_stepper]` config for single-axis control.
- **Moonraker** — API layer on Pi, exposes Klipper via HTTP/WebSocket/JSON-RPC.
- **RTDE Bridge Daemon** — Python service on Pi, translates UR30 register values to Klipper G-code via Unix socket.
- **URScript** — program on UR30 teach pendant, writes extrusion commands to RTDE output registers.
- **`ur_rtde`** — SDU library (C++ with Python bindings) for RTDE communication.

## Project Schedule

**Target completion:** Mar 31, 2026 | **Final report:** Apr 23 | **Oral presentation:** Apr 24, 6:30–9:30 PM

See [`schedule.md`](schedule.md) for the full weekly timeline.

### Accelerated Weekly Timeline

| Week | Dates | Phase | Milestone | Status |
|------|-------|-------|-----------|--------|
| 5 | Feb 2–8 | **Phase 1** | Planning — team, roles, component selection | **Complete** |
| 6–7 | Feb 9–22 | **Phase 2** | Design — trade studies, analysis, specs | **In Progress** |
| 8 | Feb 23–Mar 1 | **Phase 2** | Design refinement, BOM, Phase 2 memo submission | Upcoming |
| 9 | Mar 2–8 | **Phase 3** | Spring Break — flash firmware, Klipper setup, first stepper test | Upcoming |
| 10 | Mar 9–15 | **Phase 3** | RTDE bridge daemon, URScript program | Upcoming |
| 11 | Mar 16–22 | **Phase 3** | Integration — full chain working, progress memo | Upcoming |
| 12 | Mar 23–29 | **Phase 4** | System testing, latency measurement, fault testing | Upcoming |
| 13 | Mar 30–Apr 5 | **Phase 4** | Final testing by Mar 31, draft report | Upcoming |
| — | Apr 6–23 | Buffer | Report polish, supplementary materials | Upcoming |

### Key Milestones

| Date | Milestone |
|------|-----------|
| Feb 8 | Roles assigned, core components selected |
| **Mar 1** | **Phase 2 memo submitted** |
| Mar 8 | Klipper running, stepper moves (Spring Break) |
| Mar 22 | Full chain working: UR30 → Pi → SKR Pico → stepper |
| **Mar 31** | **Functional prototype complete — all testing done** |
| Apr 5 | Final report draft and presentation rehearsal |
| **Apr 23** | **Final report due** |
| **Apr 24** | **Oral presentation and design defense** |

---

## Bolton's 7-Step Design Process

The course requires following and documenting Bolton's mechatronics design process (see [`reqs/process.md`](reqs/process.md)). Progress per step:

### Step 1: The Need — Complete

- [x] Identify the need: UR30 lacks a native extrusion axis for metal paste dispensing
- [x] Document in [`reqs/initial_scope.md`](reqs/initial_scope.md)

### Step 2: Problem Analysis — Complete

- [x] Formal problem analysis — [`docs/problem_analysis.md`](docs/problem_analysis.md)
  - Environmental constraints, performance requirements, failure modes
  - Power constraints (2A @ 24V from UR30)
  - Communication constraints (RTDE 500Hz, non-RT Linux host)
- [x] Latency analysis — [`docs/latency_analysis.md`](docs/latency_analysis.md) (~8ms typical, adequate for paste)

### Step 3: Specification — In Progress

- [ ] Write formal design specification (functions, interfaces, accuracy targets, operating environment)
- [x] RTDE register allocation finalized — [`docs/register_allocation.md`](docs/register_allocation.md)
- [ ] Pin assignment table
- [ ] Power budget worksheet

### Step 4: Possible Solutions — In Progress

- [x] Firmware: Klipper vs Lingua Franca — [`trades/lingua_franca_vs_klipper.md`](trades/lingua_franca_vs_klipper.md)
- [x] Communication: RTDE vs alternatives — [`trades/comms.md`](trades/comms.md)
- [x] MCU platform: SKR Pico vs alternatives — [`trades/mcu.md`](trades/mcu.md)
- [ ] Location: end effector vs base-mounted vs gantry (Dawood)

### Step 5: Solution Selection — Complete

- [x] Klipper selected (4.70 vs 1.95)
- [x] RTDE selected (4.85 vs next-best 3.30)
- [x] SKR Pico selected (already on hand, Klipper-native)
- [x] Architecture documented in README and CLAUDE.md

### Step 6: Detailed Design — In Progress

- [ ] Circuit diagram (schematic)
- [ ] Circuit layout (physical arrangement)
- [ ] Block diagram of functions/signals
- [ ] Bill of materials with purchasing instructions
- [ ] Engineering analysis (motor loads, power budget)
- [ ] 3D-printed component designs (Dawood)

### Step 7: Working Drawings — Upcoming (Phase 3)

- [ ] Final circuit schematics
- [ ] Final mechanical drawings / CAD
- [ ] Wiring diagrams with pin assignments
- [ ] System block diagram

---

## Course Phase Tracking (Accelerated Schedule)

> Target: functional prototype by **Mar 31**. Apr 1–23 is buffer for documentation and polish.

### Phase 1: Ideation and Scope — Complete (Week 5: Feb 2–8)

- [x] Team formation and role assignment
- [x] Project idea submitted — stepper motor driver as 7th axis for UR30
- [x] Scope defined — [`reqs/initial_scope.md`](reqs/initial_scope.md)
- [x] Instructor go/no-go received — approved with feedback

### Phase 2: Design and Preliminary Analysis — In Progress (Weeks 6–8: Feb 9 – Mar 1)

**Deliverable:** Written memo (PDF, ≤5 pages). **Target: submit by Mar 1.**

| Category | Task | Status | Week |
|----------|------|--------|------|
| **Diagrams** | Block diagram of functions/signals | Not started | 7 |
| | Circuit diagram (schematic) | Not started | 7–8 |
| | Circuit layout (physical arrangement) | Not started | 8 |
| | Mechanical component sketches (Dawood) | Not started | 7–8 |
| **Trade studies** | Klipper vs Lingua Franca | **Complete** — [`lingua_franca_vs_klipper.md`](trades/lingua_franca_vs_klipper.md) | 6 |
| | Communication protocol | **Complete** — [`comms.md`](trades/comms.md) | 6 |
| | MCU platform | **Complete** — [`mcu.md`](trades/mcu.md) | 6 |
| | Location (Dawood) | Not started | 7 |
| **Analysis** | Problem analysis (Bolton Step 2) | **Complete** — [`problem_analysis.md`](docs/problem_analysis.md) | 6 |
| | RTDE register allocation | **Complete** — [`register_allocation.md`](docs/register_allocation.md) | 6 |
| | Latency analysis | **Complete** — [`latency_analysis.md`](docs/latency_analysis.md) | 6 |
| | Motor load / torque analysis | Pending hardware receipt | 8 |
| | Power budget | Not started | 7 |
| **Electrical** | Pin assignment table | Not started | 7 |
| | Buck converter selection | Not started | 7 |
| **BOM** | Bill of materials + purchasing instructions | Not started | 8 |
| **Mechanical** | 3D-printed component identification (Dawood) | Not started | 7–8 |
| **Submission** | Compile Phase 2 PDF (≤5 pages) | Not started | 8 |

### Phase 3: Build and Additional Design/Analysis (Weeks 9–11: Mar 2 – Mar 22)

Week 9 is Spring Break — dedicated build time.

| Task | Status | Week |
|------|--------|------|
| Flash Klipper firmware onto SKR Pico | Not started | 9 |
| Install Klipper + Moonraker on Pi | Not started | 9 |
| Write `printer.cfg` with `[manual_stepper]` | Not started | 9 |
| Test: send G-code, confirm stepper moves | Not started | 9 |
| Configure TMC2209 UART (run_current, stealthchop) | Not started | 9 |
| Write RTDE bridge daemon (Python) | Not started | 10 |
| Write URScript program | Not started | 10 |
| Implement status feedback (Klipper → RTDE → UR30) | Not started | 10–11 |
| 3D print mounting components (Dawood) | Not started | 9–10 |
| Assemble electronics + route cabling (Dawood) | Not started | 10–11 |
| Mount to end effector / robot (Dawood) | Not started | 11 |
| Progress memo to instructor | Not started | 11 |

### Phase 4: Test and Reporting (Weeks 12–13: Mar 23 – Apr 5)

Functional testing done by **Mar 31**. Week 13 for documentation.

| Task | Status | Week |
|------|--------|------|
| End-to-end functional test (UR30 → stepper moves) | Not started | 12 |
| Latency characterization (oscilloscope measurement) | Not started | 12 |
| Accuracy test (commanded vs actual speed/position) | Not started | 12 |
| Fault handling test (comms loss, stall, power) | Not started | 12 |
| Draft final report | Not started | 13 |
| Rehearse presentation | Not started | 13 |

### Buffer: Documentation Polish (Apr 6 – Apr 23)

| Task | Status | Due |
|------|--------|-----|
| Final report (≤2000 words, PDF) | Not started | Apr 23 |
| Supplementary materials (code, drawings) | Not started | Apr 23 |
| Oral presentation + design defense | Not started | Apr 24 |

## Repository Structure

```
├── CLAUDE.md                   # AI assistant context (Claude Code)
├── README.md                   # This file
├── schedule.md                 # Accelerated project schedule
├── todo.md                     # Project task tracker (Bolton process + phase deliverables)
├── trades/                     # Trade studies
│   ├── lingua_franca_vs_klipper.md  # Klipper (4.70) vs Lingua Franca (1.95)
│   ├── comms.md                # RTDE vs alternative UR30 protocols
│   └── mcu.md                  # SKR Pico vs alternative MCU platforms
├── docs/                       # Engineering analysis and technical reference
│   ├── problem_analysis.md     # Bolton Step 2: formal problem analysis
│   ├── register_allocation.md  # RTDE register mapping (finalized)
│   ├── latency_analysis.md     # End-to-end latency analysis
│   ├── klipper_protocols.md    # Klipper API surface and serial protocol
│   ├── skr_pico_specs.md       # SKR Pico V1.0 hardware reference
│   ├── skr_pico_klipper_setup.md  # SKR Pico + Klipper setup guide
│   ├── ur_rtde.md              # RTDE protocol, registers, latency
│   └── pi_power.md             # Power requirements and budget
├── reqs/                       # Course requirements and process
│   ├── about.md                # Course project overview
│   ├── initial_scope.md        # Project scope definition
│   ├── phase2.md               # Phase 2 deliverable requirements
│   ├── phase3.md               # Phase 3/4 final report requirements
│   ├── process.md              # Bolton's 7-step design process
│   └── information_needs.md    # Data/information gaps per task
```

## Key Documents

| Document | Description |
|----------|-------------|
| [`todo.md`](todo.md) | Full task list organized by Bolton's design process and project phases |
| [`reqs/information_needs.md`](reqs/information_needs.md) | What data we still need to gather, per task |
| [`docs/problem_analysis.md`](docs/problem_analysis.md) | Bolton Step 2: formal problem analysis |
| [`docs/register_allocation.md`](docs/register_allocation.md) | RTDE register mapping — finalized design decision |
| [`docs/latency_analysis.md`](docs/latency_analysis.md) | End-to-end latency analysis (~8ms typical) |
| [`trades/lingua_franca_vs_klipper.md`](trades/lingua_franca_vs_klipper.md) | Trade study: Klipper (4.70) vs Lingua Franca (1.95) |
| [`trades/comms.md`](trades/comms.md) | Trade study: RTDE vs alternative UR30 protocols |
| [`trades/mcu.md`](trades/mcu.md) | Trade study: SKR Pico vs alternative MCU platforms |
| [`docs/skr_pico_specs.md`](docs/skr_pico_specs.md) | SKR Pico V1.0 complete hardware reference |
| [`docs/ur_rtde.md`](docs/ur_rtde.md) | RTDE protocol, register details, latency considerations |
| [`docs/klipper_protocols.md`](docs/klipper_protocols.md) | Klipper API surface and serial protocol |

## Team

| Member | Role | Focus Areas |
|--------|------|-------------|
| Willem | Software / EE | RTDE comms, Klipper integration, firmware, electrical documentation |
| Dawood | Mechanical | Packaging, cabling, end effector mounting, 3D-printed components, procurement |
