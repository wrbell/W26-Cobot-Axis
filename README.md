![CI](../../actions/workflows/ci.yml/badge.svg)
![Firmware Build](../../actions/workflows/firmware.yml/badge.svg)
![Patch Freshness](../../actions/workflows/patch-freshness.yml/badge.svg)
[![codecov](https://codecov.io/gh/wrbell/W26-Cobot-Axis/graph/badge.svg)](https://codecov.io/gh/wrbell/W26-Cobot-Axis)

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

## Documentation

**Start here by role:**

- **First-time Pi setup (fresh OS → running system)** → [SETUP.md](SETUP.md)
- **Local development (no hardware needed)** → [DEVELOPMENT.md](DEVELOPMENT.md)
- **Dev bench bring-up (Pi + SKR Pico + URSim)** → [docs/dev_bench_guide.md](docs/dev_bench_guide.md)
- **Hardware calibration & tuning** → [docs/config_guide.md](docs/config_guide.md)
- **Phase 3 hardware integration (8 staged procedure)** → [docs/design/integration_plan.md](docs/design/integration_plan.md)

**Testing & validation:**

- [docs/design/testing_strategy.md](docs/design/testing_strategy.md) — unit / integration / HITL tier architecture
- [docs/design/test_procedures.md](docs/design/test_procedures.md) — formal acceptance tests (TP-01 … TP-05)
- [docs/design/hitl_plan.md](docs/design/hitl_plan.md) — StallGuard + URSim hardware-in-the-loop plan
- [docs/ursim_quickstart.md](docs/ursim_quickstart.md) — URSim Docker runbook
- [src/urscript/test_basic.script](src/urscript/test_basic.script) — on-robot validation (sub-tests A–I)
- [src/urscript/test_calibration.script](src/urscript/test_calibration.script) — pump flow characterization

**CI/CD & deployment:**

- [docs/design/ci_cd_guide.md](docs/design/ci_cd_guide.md) — GitHub Actions Tier 1 / Tier 2 workflows
- [deploy.sh](deploy.sh) — idempotent Pi deployment script
- [scripts/dev-sync.sh](scripts/dev-sync.sh) — fast iterative rsync for the dev bench

**Hardware reference:**

- [docs/skr_pico_specs.md](docs/skr_pico_specs.md) — SKR Pico V1.0 pinout, TMC2209, StallGuard
- [docs/skr_pico_klipper_setup.md](docs/skr_pico_klipper_setup.md) — Klipper on the SKR Pico
- [docs/pi_power.md](docs/pi_power.md) — 24 V power distribution, buck converter selection
- [docs/klipper_protocols.md](docs/klipper_protocols.md) — Klipper host API & MCU protocol
- [docs/ur_rtde.md](docs/ur_rtde.md) — UR30 RTDE protocol & the `ur_rtde` library

**Design & analysis:**

- [docs/design_specification.md](docs/design_specification.md) — 25 formal requirements
- [docs/problem_analysis.md](docs/problem_analysis.md) — Bolton Step 2 problem analysis
- [docs/latency_analysis.md](docs/latency_analysis.md) — end-to-end latency budget
- [docs/register_allocation.md](docs/register_allocation.md) — RTDE register map
- [docs/design/stepper_driving.md](docs/design/stepper_driving.md) — consolidated stepper design
- [docs/phase2/memo_draft.md](docs/phase2/memo_draft.md) — Phase 2 memo (full text + tables)
- [trades/](trades/) — trade studies (comms, MCU, Klipper vs Lingua Franca)

---

## Current Progress (as of Feb 24, 2026 — Week 8)

### Status Summary

| Area | Status |
|------|--------|
| **Phase 1: Ideation** | Complete |
| **Phase 2: Design** | In progress — analysis, trade studies, software design, and memo rough drafts complete. Needs redrawing in draw.io/KiCad, Dawood's sections, and final Word compilation. Due Mar 1. |
| **Software development** | All source code written and unit tested (479 tests across 10 files, 100% coverage, clean lint). 7 bridge enhancements + StallGuard firmware. Waiting on hardware for integration. |
| **CI/CD** | Tier 1 (lint + test + coverage + mypy + shellcheck, Python 3.9/3.11 matrix), Tier 2 (firmware cross-compile + SRAM size check), quality gates (yamllint, pip-audit, codespell, link checker, deploy-check), release workflow, patch freshness (weekly cron), and Dependabot. |
| **StallGuard firmware** | Written — RP2040 core1 DIAG pin monitor (C firmware + klippy extras + patches). Verified against real Klipper source tree. All audit issues resolved. |
| **Deploy tooling** | Written — `deploy.sh` (11-step + StallGuard overlay, cross-platform sed), `scripts/dev-sync.sh` (fast rsync for iterative dev) |
| **HITL test plan** | Written — `docs/design/hitl_plan.md` with TP-06 StallGuard procedures, URSim dev bench topology, deploy workflow |
| **Phase 2 memo drafts** | 7 rough drafts in `docs/phase2/` — ready for draw.io/KiCad redraw and Word compilation |
| **Phase 3: Build** | Not started — hardware arriving soon, deploy tooling ready |
| **Phase 4: Test** | Not started — depends on Phase 3 |

### What's Done

**Analysis and Design (Bolton Steps 1–5):**
- Problem analysis, latency analysis, RTDE register allocation — all complete
- 3 trade studies with weighted scoring: Klipper (4.70), RTDE (4.85), SKR Pico (selected)
- Formal design specification — 25 "shall" statements, interface tables, performance targets
- 14 design documents covering all software subsystems, deployment, integration plan, test procedures, network architecture, HITL testing, and stepper driving
- Stepper driving design — consolidated justification for `[manual_stepper]`, TMC2209 config, step generation pipeline

**Phase 2 Memo Rough Drafts (all in `docs/phase2/`):**
- Block diagram — Mermaid diagram + draw.io redrawing guide with all blocks, signals, power, and feedback paths
- Circuit schematic — full power distribution (UR30 24V → fuse → TVS → buck → Pi; 24V direct → SKR Pico), signal connections, protection components, wire schedule
- Pin assignment table — all devices (SKR Pico E-axis, Pi 4B, UR30, switch, buck converter), 14 external wired connections
- Power budget worksheet — per-device calculations, margin analysis (1.0A typical vs 2.0A budget), thermal considerations
- Buck converter selection — Pololu D24V22F5 chosen over 5 alternatives, DigiKey P/N 2183-2858-ND
- Bill of materials — 28 items, DigiKey/Newark part numbers, ~$183 total estimated cost (most P/Ns verified)
- Memo text — all 8 sections (~1,400 words) with all 5 tables, ready to paste into Word

**Source Code (all in `src/`):**
- Bridge daemon core: config, RTDE client, Klipper client, main loop with mode switching, e-stop, reconnection
- Bridge enhancements: watchdog timer, TMC2209 status polling, CSV data logging, speed-proportional extrusion, configurable profiles, UR Dashboard client, StallGuard accumulator
- Unit tests: 479 tests across 10 test files, 100% coverage, all passing, clean ruff lint
- Klipper configs: `printer.cfg` (SKR Pico, manual_stepper, TMC2209, stallguard_monitor), `moonraker.conf`, `mainsail.cfg` (pump macros)
- URScript: extrusion control library, system validation test (10 sub-tests), pump calibration test (5 sub-tests)
- Deployment: `requirements.txt` (runtime + dev deps), systemd service (portable `%h` paths), 11-step deploy script (with StallGuard overlay, cross-platform sed), full setup guide, dev-sync script
- CI/CD: GitHub Actions Tier 1 (ruff + pytest + coverage + mypy + shellcheck, Python 3.9/3.11 matrix), Tier 2 (ARM firmware cross-compile + SRAM size check), quality gates (yamllint, pip-audit, codespell, link checker, deploy-check), release workflow (v* tags → GitHub Release), patch freshness (weekly cron), and Dependabot (pip + actions)
- Config validation: 24 tests covering register naming, uniqueness, constant sanity

**StallGuard Dual-Core Firmware (`src/klipper_mods/`):**
- RP2040 core1 DIAG pin monitor — tight polling loop with debounce, spinlock-protected shared SRAM
- Klipper MCU commands (`stallguard_query`, `stallguard_clear`) via `DECL_COMMAND`
- Klippy host module (`stallguard_monitor.py`) — 20 Hz polling, Moonraker status object
- Makefile and main.c patches — verified against real Klipper source in `vendor/klipper/`
- `deploy.sh` Step 6b automates overlay deployment (idempotent)

**HITL Test Plan (`docs/design/hitl_plan.md`):**
- TP-06: 5-part StallGuard test procedure with pass/fail criteria and data sheets
- URSim dev bench topology: Windows laptop (Docker URSim) ↔ Pi ↔ SKR Pico
- 8-stage test sequence from bare Pi to full chain
- Deploy workflow documentation (full deploy vs dev-sync)

### What's Remaining

**Phase 2 memo — finishing (target Mar 1):**
- [ ] Redraw block diagram in draw.io/Visio (from rough draft)
- [ ] Redraw circuit schematic in KiCad/draw.io (from rough draft)
- [ ] Circuit layout — physical arrangement (Dawood + Willem)
- [x] ~~Verify DigiKey/Newark part numbers and stock~~ — 10 of 14 verified/corrected
- [ ] Location trade study (Dawood)
- [ ] Mechanical component sketches (Dawood)
- [ ] Dawood: write Section 5 (mechanical concept) + Figures 3–4
- [ ] Compile Phase 2 PDF (≤5 pages) in Microsoft Word
- [ ] Present trade studies to Prof. Pannier

**Phase 3 — hardware integration (target Mar 8–22):**
- [ ] Flash Klipper firmware onto SKR Pico (deploy.sh handles this)
- [ ] Install Klipper + Moonraker on Pi
- [ ] Deploy configs, bridge daemon, and StallGuard overlay to Pi
- [ ] Verify StallGuard firmware builds with overlay (`make` in Klipper tree)
- [ ] Test stepper motion + StallGuard DIAG detection
- [ ] End-to-end smoke test: UR30 → stepper moves
- [ ] Set up URSim on Windows for RTDE integration testing
- [ ] Mechanical assembly (Dawood)

**Phase 4 — testing and reporting (target Mar 23–31):**
- [ ] End-to-end functional test, latency characterization, accuracy test
- [ ] StallGuard HITL testing (TP-06 from `docs/design/hitl_plan.md`)
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
| 3 | Specification | **Mostly complete** — formal spec with 25 requirements (`docs/design_specification.md`). Pin table and power budget drafted (`docs/phase2/`). |
| 4 | Possible Solutions | **Mostly complete** — 3 trade studies done. Location study pending (Dawood). |
| 5 | Solution Selection | **Complete** — Klipper, RTDE, SKR Pico selected and documented |
| 6 | Detailed Design | **In progress** — software design complete (14 docs). Circuit schematic, block diagram, BOM, power budget, pin table, buck converter all drafted. Circuit layout and mechanical drawings pending. |
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
│   │   ├── stallguard_accumulator.py # Pi-side StallGuard history buffer
│   │   ├── profiles.json          # Pre-defined extrusion profiles
│   │   └── tests/                 # pytest suite (479 tests, 100% coverage)
│   │       ├── conftest.py              # Shared fixtures (FakeKlippy, mock sockets)
│   │       ├── test_bridge_daemon.py    # 146 tests
│   │       ├── test_dashboard_client.py # 38 tests
│   │       ├── test_data_logger.py      # 29 tests
│   │       ├── test_extrusion_profile.py # 46 tests
│   │       ├── test_klipper_client.py   # 44 tests
│   │       ├── test_rtde_client.py      # 44 tests
│   │       ├── test_stallguard.py       # 49 tests
│   │       ├── test_config.py                # 24 tests
│   │       ├── test_stallguard_accumulator.py # 34 tests
│   │       └── test_watchdog.py         # 15 tests
│   ├── klipper/                   # Klipper configuration files
│   │   ├── printer.cfg            # SKR Pico, manual_stepper pump, TMC2209, stallguard_monitor
│   │   ├── moonraker.conf         # Moonraker API (port 7125, auth, updates)
│   │   └── mainsail.cfg           # Pump macros (PUMP_STATUS, PUMP_TEST, etc.)
│   ├── klipper_mods/              # StallGuard dual-core firmware overlay
│   │   ├── stallguard_shared.h    # Shared SRAM struct + spinlock #16 helpers
│   │   ├── core1_stallguard.c     # Core1 entry: gpio16 init, debounce loop, FIFO launch
│   │   ├── stallguard_command.c   # Klipper DECL_COMMAND: stallguard_query, stallguard_clear
│   │   ├── Makefile.patch         # Add .c files to Klipper rp2040 build
│   │   ├── main.c.patch           # Call core1_launch() before sched_main()
│   │   ├── klippy_extras/         # Host-side Klipper module
│   │   │   └── stallguard_monitor.py  # 20 Hz polling, Moonraker status object
│   │   └── README.md              # Build & deploy instructions
│   ├── urscript/                  # URScript programs for UR30
│   │   ├── extrusion_control.script  # Helper functions, speed-sync, retraction
│   │   ├── test_basic.script         # System validation (10 sub-tests)
│   │   └── test_calibration.script   # Pump calibration (5 sub-tests)
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
│   ├── phase3/                    # Phase 3 progress memo draft
│   │   └── progress_memo_draft.md # Progress update template with placeholders
│   ├── phase2/                    # Phase 2 memo rough drafts (7 docs)
│   │   ├── block_diagram.md       # System block diagram (Mermaid + redraw guide)
│   │   ├── circuit_schematic.md   # Power distribution + signal connections
│   │   ├── pin_assignments.md     # All devices, all pins, wiring list
│   │   ├── power_budget.md        # Per-device calculations + margin analysis
│   │   ├── buck_converter.md      # Pololu D24V22F5 selection + part numbers
│   │   ├── bom.md                 # 28-item BOM with DigiKey/Newark P/Ns (~$183)
│   │   └── memo_draft.md          # Full memo text (~1,400 words) + all tables
│   └── design/                    # Software design documents (14 docs)
│       ├── stepper_driving.md     # How Klipper drives the stepper (consolidated)
│       ├── bridge_enhancements.md # 6 bridge enhancement designs
│       ├── klipper_config.md      # Moonraker/Mainsail config design
│       ├── urscript_programs.md   # URScript test program designs
│       ├── testing_strategy.md    # Unit + integration test strategy
│       ├── deployment.md          # Deploy script and systemd design
│       ├── network_architecture.md # IP, ports, firewall, DNS
│       ├── integration_plan.md    # Phase 3 step-by-step plan
│       ├── test_procedures.md     # Phase 4 test procedures
│       ├── hitl_plan.md           # HITL test plan (StallGuard, URSim dev bench)
│       ├── ci_cd_guide.md         # CI/CD setup guide (Tiers 1–3)
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
├── scripts/
│   └── dev-sync.sh                # Fast rsync to Pi for iterative development
├── vendor/                        # Vendored dependencies (git-ignored)
│   └── klipper/                   # Klipper source (shallow clone for patch verification)
├── .github/
│   ├── dependabot.yml             # Dependabot: weekly pip + GitHub Actions updates
│   └── workflows/
│       ├── ci.yml                 # Tier 1: lint + test + coverage + mypy + shellcheck + quality gates (7 jobs, Python 3.9/3.11 matrix)
│       ├── firmware.yml           # Tier 2: firmware build + SRAM size check on klipper_mods changes
│       ├── patch-freshness.yml    # Weekly cron: verify StallGuard patches apply against upstream Klipper
│       ├── release.yml            # Release: on v* tag, full CI + firmware + GitHub Release with klipper.uf2
│       ├── dependabot-auto-merge.yml  # Auto-merge passing Dependabot PRs
│       └── pr-size.yml            # PR size labeler (XS/S/M/L/XL)
├── .yamllint                      # yamllint config (relaxed: allow long lines, truthy)
├── pyproject.toml                 # mypy config with per-module overrides
├── .gitignore                     # Ignores vendor/, __pycache__, .DS_Store, etc.
├── deploy.sh                      # 11-step idempotent deployment script (+ StallGuard overlay)
├── SETUP.md                       # Fresh Pi setup guide
├── DEVELOPMENT.md                 # Developer & test environment setup (no hardware)
└── requirements.txt               # Python dependencies (ur-rtde, pytest, ruff)
```

## Key Documents

### Source Code

| Component | Location | Tests |
|-----------|----------|-------|
| Bridge daemon (main loop) | `src/bridge/bridge_daemon.py` | 146 tests |
| Bridge config (registers, constants) | `src/bridge/config.py` | 24 tests |
| Klipper Unix socket client | `src/bridge/klipper_client.py` | 44 tests |
| RTDE client wrapper | `src/bridge/rtde_client.py` | 44 tests |
| StallGuard status integration | `src/bridge/klipper_status.py` | 49 tests |
| Watchdog timer | `src/bridge/watchdog.py` | 15 tests |
| Data logger | `src/bridge/data_logger.py` | 29 tests |
| Extrusion profiles | `src/bridge/extrusion_profile.py` | 46 tests |
| Dashboard client | `src/bridge/dashboard_client.py` | 38 tests |
| StallGuard accumulator | `src/bridge/stallguard_accumulator.py` | 34 tests |
| Klipper printer config | `src/klipper/printer.cfg` | — (config) |
| Moonraker config | `src/klipper/moonraker.conf` | — (config) |
| Mainsail pump macros | `src/klipper/mainsail.cfg` | — (config) |
| Core1 StallGuard firmware | `src/klipper_mods/` (3 C/H files) | — (C, needs hardware) |
| StallGuard klippy module | `src/klipper_mods/klippy_extras/stallguard_monitor.py` | — (Klipper runtime) |
| URScript extrusion program | `src/urscript/extrusion_control.script` | — (URScript) |
| URScript system validation | `src/urscript/test_basic.script` | — (URScript) |
| URScript pump calibration | `src/urscript/test_calibration.script` | — (URScript) |

### Design and Analysis

| Document | Description |
|----------|-------------|
| [`todo.md`](todo.md) | Full task list organized by Bolton's design process and project phases |
| [`docs/design_specification.md`](docs/design_specification.md) | Bolton Step 3: 25 formal requirements, interface tables, performance targets |
| [`docs/problem_analysis.md`](docs/problem_analysis.md) | Bolton Step 2: formal problem analysis |
| [`docs/register_allocation.md`](docs/register_allocation.md) | RTDE register mapping — 6 output, 5 input registers |
| [`docs/latency_analysis.md`](docs/latency_analysis.md) | End-to-end latency analysis (~8ms typical) |
| [`docs/design/stepper_driving.md`](docs/design/stepper_driving.md) | How Klipper drives the stepper — consolidated justification |
| [`docs/design/hitl_plan.md`](docs/design/hitl_plan.md) | HITL test plan: StallGuard TP-06, URSim dev bench, deploy workflow |
| [`trades/lingua_franca_vs_klipper.md`](trades/lingua_franca_vs_klipper.md) | Trade study: Klipper (4.70) vs Lingua Franca (1.95) |
| [`trades/comms.md`](trades/comms.md) | Trade study: RTDE vs alternative protocols |
| [`trades/mcu.md`](trades/mcu.md) | Trade study: SKR Pico vs alternatives |

### Setup and Development

| Document | Description |
|----------|-------------|
| [`SETUP.md`](SETUP.md) | Fresh Raspberry Pi setup (OS through verified operation) |
| [`DEVELOPMENT.md`](DEVELOPMENT.md) | Local dev/test environment setup (no hardware needed) |
| [`docs/ursim_quickstart.md`](docs/ursim_quickstart.md) | URSim quick-start for RTDE integration testing |
| [`docs/design/ci_cd_guide.md`](docs/design/ci_cd_guide.md) | GitHub Actions CI/CD (Tiers 1--3) |

### Phase 2 Memo Drafts

| Document | Description |
|----------|-------------|
| [`docs/phase2/memo_draft.md`](docs/phase2/memo_draft.md) | Full memo text (~1,400 words), all 8 sections + 5 tables |
| [`docs/phase2/block_diagram.md`](docs/phase2/block_diagram.md) | System block diagram — Mermaid + draw.io redrawing guide |
| [`docs/phase2/circuit_schematic.md`](docs/phase2/circuit_schematic.md) | Circuit schematic — power distribution, signal connections, protection |
| [`docs/phase2/pin_assignments.md`](docs/phase2/pin_assignments.md) | Pin assignments — all devices, 14 external wired connections |
| [`docs/phase2/power_budget.md`](docs/phase2/power_budget.md) | Power budget — per-device calculations, ~1.0A typical vs 2.0A budget |
| [`docs/phase2/buck_converter.md`](docs/phase2/buck_converter.md) | Buck converter selection — Pololu D24V22F5, DigiKey P/N |
| [`docs/phase2/bom.md`](docs/phase2/bom.md) | Bill of materials — 28 items, ~$183 total, DigiKey/Newark P/Ns (mostly verified) |

## Team

| Member | Role | Focus Areas |
|--------|------|-------------|
| Willem | Software / EE | RTDE comms, Klipper integration, firmware, electrical documentation |
| Dawood | Mechanical | Packaging, cabling, end effector mounting, 3D-printed components, procurement |
