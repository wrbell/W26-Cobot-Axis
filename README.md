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

---

## Current Progress (as of Feb 12, 2026 — Week 6)

### Status Summary

| Area | Status |
|------|--------|
| **Phase 1: Ideation** | Complete |
| **Phase 2: Design** | In progress — trade studies, analysis, and software design complete. Diagrams, BOM, and memo outstanding. Due Mar 1. |
| **Software development** | All source code written and unit tested (147 tests passing). Waiting on hardware for integration. |
| **Phase 3: Build** | Not started — waiting on hardware receipt and Pi model decision |
| **Phase 4: Test** | Not started — depends on Phase 3 |

### What's Done

**Analysis and Design (Bolton Steps 1–5):**
- Problem analysis, latency analysis, RTDE register allocation — all complete
- 3 trade studies with weighted scoring: Klipper (4.70), RTDE (4.85), SKR Pico (selected)
- Formal design specification — 25 "shall" statements, interface tables, performance targets
- 12 design documents covering all software subsystems, deployment, integration plan, test procedures, network architecture, Phase 2 memo outline, and final report outline
- Stepper driving design — consolidated justification for `[manual_stepper]`, TMC2209 config, step generation pipeline

**Source Code (all in `src/`):**
- Bridge daemon core: config, RTDE client, Klipper client, main loop with mode switching, e-stop, reconnection
- Bridge enhancements: watchdog timer, TMC2209 status polling, CSV data logging, speed-proportional extrusion, configurable profiles, UR Dashboard client
- Unit tests: 147 tests across 3 test files (42 + 34 + 71), all passing
- Klipper configs: `printer.cfg` (SKR Pico, manual_stepper, TMC2209), `moonraker.conf`, `mainsail.cfg` (pump macros)
- URScript: extrusion control library, system validation test (9 sub-tests), pump calibration test (4 sub-tests)
- Deployment: `requirements.txt`, systemd service, 11-step deploy script, full setup guide

### What's Remaining

**Phase 2 deliverables (target Mar 1):**
- [ ] Block diagram of functions/signals
- [ ] Circuit diagram (schematic)
- [ ] Circuit layout (physical arrangement)
- [ ] Pin assignment table (blocked on Pi model decision)
- [ ] Power budget worksheet (blocked on Pi model decision)
- [ ] Buck converter selection (Pololu D24V22F5)
- [ ] Bill of materials with supplier part numbers
- [ ] Location trade study (Dawood)
- [ ] Mechanical component sketches (Dawood)
- [ ] Compile Phase 2 PDF (≤5 pages)
- [ ] Present trade studies to Prof. Pannier

**Phase 3 — hardware integration (target Mar 8–22):**
- [ ] Decide Pi model for headless control node
- [ ] Flash Klipper firmware onto SKR Pico
- [ ] Install Klipper + Moonraker on Pi
- [ ] Deploy configs and bridge daemon to Pi
- [ ] End-to-end smoke test: UR30 → stepper moves
- [ ] Set up URSim on Windows for integration testing
- [ ] Mechanical assembly (Dawood)

**Phase 4 — testing and reporting (target Mar 23–31):**
- [ ] End-to-end functional test, latency characterization, accuracy test
- [ ] Fault handling and endurance testing
- [ ] Final report (≤2000 words, due Apr 23)
- [ ] Oral presentation (Apr 24)

---

## Project Schedule

**Target completion:** Mar 31, 2026 | **Final report:** Apr 23 | **Oral presentation:** Apr 24, 6:30–9:30 PM

See [`schedule.md`](schedule.md) for the full weekly timeline.

| Week | Dates | Phase | Milestone | Status |
|------|-------|-------|-----------|--------|
| 5 | Feb 2–8 | **Phase 1** | Planning — team, roles, component selection | **Complete** |
| 6–7 | Feb 9–22 | **Phase 2** | Design — trade studies, analysis, specs | **In Progress** |
| 8 | Feb 23–Mar 1 | **Phase 2** | Design refinement, BOM, Phase 2 memo submission | Upcoming |
| 9 | Mar 2–8 | **Phase 3** | Spring Break — flash firmware, Klipper setup, first stepper test | Upcoming |
| 10 | Mar 9–15 | **Phase 3** | Deploy bridge daemon, URScript, integration | Upcoming |
| 11 | Mar 16–22 | **Phase 3** | Full chain working, tuning, progress memo | Upcoming |
| 12 | Mar 23–29 | **Phase 4** | System testing, latency measurement, fault testing | Upcoming |
| 13 | Mar 30–Apr 5 | **Phase 4** | Final testing by Mar 31, draft report | Upcoming |
| — | Apr 6–23 | Buffer | Report polish, supplementary materials | Upcoming |

---

## Bolton's 7-Step Design Process

| Step | Name | Status |
|------|------|--------|
| 1 | The Need | **Complete** — UR30 lacks native extrusion axis |
| 2 | Problem Analysis | **Complete** — `docs/problem_analysis.md`, `docs/latency_analysis.md` |
| 3 | Specification | **Mostly complete** — formal spec with 25 requirements (`docs/design_specification.md`). Pin table and power budget pending Pi model. |
| 4 | Possible Solutions | **Mostly complete** — 3 trade studies done. Location study pending (Dawood). |
| 5 | Solution Selection | **Complete** — Klipper, RTDE, SKR Pico selected and documented |
| 6 | Detailed Design | **In progress** — software detailed design complete (12 design docs). Circuit schematic, layout, BOM pending. |
| 7 | Working Drawings | **Upcoming** — final schematics, mechanical drawings, wiring diagrams |

---

## Repository Structure

```
├── CLAUDE.md                      # AI assistant context (Claude Code)
├── README.md                      # This file
├── schedule.md                    # Accelerated project schedule
├── todo.md                        # Master task tracker
├── src/
│   ├── bridge/                    # Python RTDE-to-Klipper bridge daemon
│   │   ├── __main__.py            # Entry point (python -m bridge)
│   │   ├── bridge_daemon.py       # Main loop: RTDE read → translate → Klipper command
│   │   ├── config.py              # Register mappings, constants, defaults
│   │   ├── klipper_client.py      # klippy Unix socket client
│   │   ├── rtde_client.py         # ur_rtde wrapper with stub fallback
│   │   ├── watchdog.py            # RTDE timestamp-based stale detection
│   │   ├── klipper_status.py      # TMC2209 driver status polling
│   │   ├── data_logger.py         # 17-column CSV logging with rotation
│   │   ├── extrusion_profile.py   # Linear/polynomial/lookup profiles
│   │   ├── dashboard_client.py    # UR30 Dashboard Server (port 29999)
│   │   ├── profiles.json          # Pre-defined extrusion profiles
│   │   └── tests/                 # pytest suite (147 tests)
│   │       ├── conftest.py        # Shared fixtures (FakeKlippy, mock sockets)
│   │       ├── test_klipper_client.py   # 42 tests
│   │       ├── test_rtde_client.py      # 34 tests
│   │       └── test_bridge_daemon.py    # 71 tests
│   ├── klipper/                   # Klipper configuration files
│   │   ├── printer.cfg            # SKR Pico, manual_stepper pump, TMC2209
│   │   ├── moonraker.conf         # Moonraker API (port 7125, auth, updates)
│   │   └── mainsail.cfg           # Pump macros (PUMP_STATUS, PUMP_TEST, etc.)
│   ├── urscript/                  # URScript programs for UR30
│   │   ├── extrusion_control.script  # Helper functions, speed-sync, retraction
│   │   ├── test_basic.script         # System validation (9 sub-tests)
│   │   └── test_calibration.script   # Pump calibration (4 sub-tests)
│   └── systemd/
│       └── w26-bridge.service     # systemd unit for bridge daemon
├── trades/                        # Trade studies (weighted scoring)
│   ├── lingua_franca_vs_klipper.md
│   ├── comms.md
│   └── mcu.md
├── docs/                          # Engineering analysis and reference
│   ├── problem_analysis.md        # Bolton Step 2
│   ├── register_allocation.md     # RTDE register mapping
│   ├── latency_analysis.md        # End-to-end latency (~8ms typical)
│   ├── design_specification.md    # Bolton Step 3 (25 requirements)
│   ├── klipper_protocols.md       # Klipper API and serial protocol
│   ├── skr_pico_specs.md          # SKR Pico V1.0 hardware reference
│   ├── skr_pico_klipper_setup.md  # Firmware build and flash guide
│   ├── ur_rtde.md                 # RTDE protocol and register details
│   ├── pi_power.md                # Power requirements and budget
│   └── design/                    # Software design documents (12 docs)
│       ├── stepper_driving.md     # How Klipper drives the stepper (consolidated)
│       ├── bridge_enhancements.md # 6 bridge enhancement designs
│       ├── klipper_config.md      # Moonraker/Mainsail config design
│       ├── urscript_programs.md   # URScript test program designs
│       ├── testing_strategy.md    # Unit + integration test strategy
│       ├── deployment.md          # Deploy script and systemd design
│       ├── network_architecture.md # IP, ports, firewall, DNS
│       ├── integration_plan.md    # Phase 3 step-by-step plan
│       ├── test_procedures.md     # Phase 4 test procedures
│       ├── phase2_deliverables.md # Phase 2 memo planning
│       ├── phase2_memo_outline.md # Memo structure and content
│       └── final_report_outline.md # Final report structure
├── reqs/                          # Course requirements
│   ├── about.md
│   ├── initial_scope.md
│   ├── phase2.md
│   ├── phase3.md
│   ├── process.md
│   └── information_needs.md
├── deploy.sh                      # 11-step idempotent deployment script
├── SETUP.md                       # Fresh Pi setup guide
└── requirements.txt               # Python dependencies (ur-rtde)
```

## Key Documents

### Source Code

| Component | Location | Tests |
|-----------|----------|-------|
| Bridge daemon (main loop) | `src/bridge/bridge_daemon.py` | 71 tests |
| Bridge config (registers, constants) | `src/bridge/config.py` | — |
| Klipper Unix socket client | `src/bridge/klipper_client.py` | 42 tests |
| RTDE client wrapper | `src/bridge/rtde_client.py` | 34 tests |
| Klipper printer config | `src/klipper/printer.cfg` | — |
| Moonraker config | `src/klipper/moonraker.conf` | — |
| Mainsail pump macros | `src/klipper/mainsail.cfg` | — |
| URScript extrusion program | `src/urscript/extrusion_control.script` | — |
| URScript system validation | `src/urscript/test_basic.script` | — |
| URScript pump calibration | `src/urscript/test_calibration.script` | — |

### Design and Analysis

| Document | Description |
|----------|-------------|
| [`todo.md`](todo.md) | Full task list organized by Bolton's design process and project phases |
| [`docs/design_specification.md`](docs/design_specification.md) | Bolton Step 3: 25 formal requirements, interface tables, performance targets |
| [`docs/problem_analysis.md`](docs/problem_analysis.md) | Bolton Step 2: formal problem analysis |
| [`docs/register_allocation.md`](docs/register_allocation.md) | RTDE register mapping — 6 output, 5 input registers |
| [`docs/latency_analysis.md`](docs/latency_analysis.md) | End-to-end latency analysis (~8ms typical) |
| [`docs/design/stepper_driving.md`](docs/design/stepper_driving.md) | How Klipper drives the stepper — consolidated justification |
| [`trades/lingua_franca_vs_klipper.md`](trades/lingua_franca_vs_klipper.md) | Trade study: Klipper (4.70) vs Lingua Franca (1.95) |
| [`trades/comms.md`](trades/comms.md) | Trade study: RTDE vs alternative protocols |
| [`trades/mcu.md`](trades/mcu.md) | Trade study: SKR Pico vs alternatives |

## Team

| Member | Role | Focus Areas |
|--------|------|-------------|
| Willem | Software / EE | RTDE comms, Klipper integration, firmware, electrical documentation |
| Dawood | Mechanical | Packaging, cabling, end effector mounting, 3D-printed components, procurement |
