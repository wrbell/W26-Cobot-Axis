# Project reference for AI agents

`AGENTS.md` links this file. It holds the project facts and the file index
that were in the root `CLAUDE.md` until 2026-10-04. Dates and status are in
`README.md`, `todo.md` and `CHANGELOG.md`, not here.

## Project overview

University capstone project (ME 472, Mechatronics) to develop a stepper motor
driver that takes commands from a Universal Robots UR30 controller and works
as an additional (7th) axis of motion. The stepper motor drives a pump for
**metal paste dispensing and extrusion** (pump type TBD: syringe,
peristaltic, or progressive cavity).

## System architecture

```text
                              ┌─── Pi400 (HMI / SSH / monitoring)
                              │       (development terminal, not in real-time loop)
                              │
UR30 Robot Controller  ──RTDE/TCP-IP──▶  Pi (Klipper host + RTDE bridge)  ──USB Serial──▶  SKR Pico (RP2040)  ──▶  Stepper Motor  ──▶  Pump
     (URScript)              (gigabit switch)                                  (Klipper MCU)         (metal paste dispensing)
```

Communication chain:

- UR30 ↔ Pi: RTDE over TCP/IP on port 30004 (ethernet, needs a gigabit
  switch)
- Pi → Klipper: Unix socket (`/tmp/klippy_uds`), the lowest-latency path
- Pi ↔ SKR Pico: USB serial (Klipper's native MCU protocol)
- SKR Pico → stepper: TMC2209 drivers (StealthChop/SpreadCycle)
- Pi400: **optional**. It sits on the same network for SSH access, the
  Moonraker/Mainsail web UI, development, and monitoring. The system must run
  standalone without it (UR30 → Pi → SKR Pico → stepper).
- Estimated end-to-end latency: 5–20 ms typical

**Power:** 5.1 V and 24 V from the UR controller power block (2 A
continuous, 3.5 A burst). Total draw is about 1.1 A typical at 24 V.

**Software stack:** Klipper (chosen over Lingua Franca; see
`trades/lingua_franca_vs_klipper.md`). The RTDE bridge daemon on the Pi
translates UR commands to Klipper G-code. A `[manual_stepper]` config gives
single-axis control.

## Repository structure

- `src/bridge/`: Python RTDE-to-Klipper bridge daemon (config, RTDE client,
  Klipper client, main loop)
- `src/bridge/tests/`: pytest suite, one test file per module
- `src/klipper/`: Klipper configuration (`printer.cfg` for the SKR Pico)
- `src/klipper_mods/`: StallGuard dual-core firmware overlay (C firmware,
  klippy extras, patches)
- `src/urscript/`: URScript programs for the UR30 teach pendant
- `trades/`: trade studies (comms protocol, MCU platform, Klipper vs Lingua
  Franca)
- `docs/`: engineering analysis and technical reference (latency, register
  allocation, hardware specs)
- `docs/design/`: software design documents (stepper driving, bridge
  enhancements, integration plan, HITL plan, CI/CD guide, and others)
- `docs/phase2/`: Phase 2 memo rough drafts (block diagram, circuit
  schematic, pin table, power budget, buck converter, BOM, memo text)
- `reqs/`: course requirements, scope, process docs (course PDFs are local
  only; see `reqs/INDEX.md`)
- `scripts/`: deployment and development helper scripts (`dev-sync.sh`)
- `.github/workflows/`: CI/CD: Tier 1 (lint, test, shellcheck), Tier 2
  (firmware cross-compile), and the collection checks (`standards.yml`)
- `vendor/`: vendored dependencies (git-ignored, cloned locally)
- `schedule.md`: accelerated project schedule
- `todo.md`: master task tracker

## Key technical details

- **Robot:** Universal Robots UR30 (6-axis collaborative robot)
- **Pi (headless):** Raspberry Pi. It runs the Klipper host, Moonraker, and
  the RTDE bridge daemon (the real-time control node).
- **Pi400:** Raspberry Pi 400. HMI, SSH terminal, web UI access
  (Mainsail/Fluidd), development. Not in the real-time loop.
- **Microcontroller:** BigTreeTech SKR Pico V1.0 (RP2040-based, 4x TMC2209
  soldered, Klipper-compatible, 85x56 mm). Product code 1060000513. Full
  specs in `docs/skr_pico_specs.md`.
- **Actuator:** stepper motor and pump, provided to the team (specs TBD on
  receipt; see the README hardware table)
- **Power:** 24 V from the UR controller power block → buck converters →
  5.1 V for the Pi; 24 V direct to the SKR Pico VIN
- **RTDE library:** `ur_rtde` (SDU, C++ with Python bindings), recommended
  over the official UR Python client

## Source code

| Component | Location |
| --- | --- |
| Bridge daemon (main loop) | `src/bridge/bridge_daemon.py` |
| Bridge config (registers, constants) | `src/bridge/config.py` |
| Klipper Unix socket client | `src/bridge/klipper_client.py` |
| RTDE client wrapper | `src/bridge/rtde_client.py` |
| TMC2209 status polling | `src/bridge/klipper_status.py` |
| Watchdog timer | `src/bridge/watchdog.py` |
| CSV data logger | `src/bridge/data_logger.py` |
| Extrusion profiles | `src/bridge/extrusion_profile.py` |
| UR Dashboard client | `src/bridge/dashboard_client.py` |
| StallGuard accumulator | `src/bridge/stallguard_accumulator.py` |
| Klipper printer config | `src/klipper/printer.cfg` |
| URScript extrusion program | `src/urscript/extrusion_control.script` |
| URScript system validation test | `src/urscript/test_basic.script` |
| URScript pump calibration test | `src/urscript/test_calibration.script` |
| URScript wrapped slicer program | `src/urscript/slicer_mblack06mm.script` |
| StallGuard shared header | `src/klipper_mods/stallguard_shared.h` |
| StallGuard core1 firmware | `src/klipper_mods/core1_stallguard.c` |
| StallGuard MCU commands | `src/klipper_mods/stallguard_command.c` |
| StallGuard klippy module | `src/klipper_mods/klippy_extras/stallguard_monitor.py` |
| Deploy script | `deploy.sh` |
| Dev sync script | `scripts/dev-sync.sh` |
| CI workflow (Tier 1) | `.github/workflows/ci.yml` |
| Firmware build workflow (Tier 2) | `.github/workflows/firmware.yml` |
| Patch freshness (weekly cron) | `.github/workflows/patch-freshness.yml` |
| Release workflow (v* tags) | `.github/workflows/release.yml` |
| Dependabot auto-merge | `.github/workflows/dependabot-auto-merge.yml` |
| PR size labeler | `.github/workflows/pr-size.yml` |
| Collection checks | `.github/workflows/standards.yml` |

## Design documents

| Topic | Location |
| --- | --- |
| Problem analysis (Bolton Step 2) | `docs/problem_analysis.md` |
| RTDE register allocation | `docs/register_allocation.md` |
| Latency analysis | `docs/latency_analysis.md` |
| Design specification (25 requirements) | `docs/design_specification.md` |
| Stepper driving design (consolidated) | `docs/design/stepper_driving.md` |
| HITL test plan (StallGuard + URSim) | `docs/design/hitl_plan.md` |
| CI/CD setup guide (Tiers 1–3) | `docs/design/ci_cd_guide.md` |
| URSim quick-start runbook | `docs/ursim_quickstart.md` |
| Fresh Pi setup guide (first-time install) | `SETUP.md` |
| Headless Pi setup (laptop, no switch) | `docs/headless_setup.md` |
| Dev bench bring-up guide | `docs/dev_bench_guide.md` |
| Hardware config & calibration guide | `docs/config_guide.md` |
| Trade: Klipper vs Lingua Franca | `trades/lingua_franca_vs_klipper.md` |
| Trade: Communication protocol | `trades/comms.md` |
| Trade: MCU platform | `trades/mcu.md` |
| Information needs tracker | `reqs/information_needs.md` |

## Phase 2 memo drafts

Rough drafts in `docs/phase2/`: content to paste into Word and redraw in
draw.io or KiCad.

| Topic | Location |
| --- | --- |
| Full memo text (~1,400 words) + tables | `docs/phase2/memo_draft.md` |
| System block diagram | `docs/phase2/block_diagram.md` |
| Circuit schematic (power + signals) | `docs/phase2/circuit_schematic.md` |
| Pin assignment table (all devices) | `docs/phase2/pin_assignments.md` |
| Power budget worksheet | `docs/phase2/power_budget.md` |
| Buck converter selection | `docs/phase2/buck_converter.md` |
| Bill of materials (~$183, 28 items) | `docs/phase2/bom.md` |

## Reference documents

| Topic | Location |
| --- | --- |
| Klipper protocols & API | `docs/klipper_protocols.md` |
| SKR Pico V1.0 hardware specs | `docs/skr_pico_specs.md` |
| SKR Pico + Klipper setup | `docs/skr_pico_klipper_setup.md` |
| UR RTDE protocol & latency | `docs/ur_rtde.md` |
| Power requirements | `docs/pi_power.md` |
| Developer environment setup | `DEVELOPMENT.md` |

## Project phases

| Phase | Description | Duration |
| --- | --- | --- |
| 1 | Ideation and Scope | 2 weeks |
| 2 | Design and Preliminary Analysis | 6 weeks |
| 3 | Build and Additional Design/Analysis | 3 weeks |
| 4 | Test and Reporting | 3 weeks |

Phase status and the course dates are in `README.md` and `schedule.md`.

## Stretch goals

- **StallGuard torque feedback:** TMC2209 DIAG → Core1 monitor → Klipper MCU
  command → klippy extras → RTDE → URScript. See `src/klipper_mods/` and
  `docs/design/hitl_plan.md`. Hardware validation status is in `todo.md`.
- URCap for the teach pendant UI (Java SDK, not needed for the MVP)
- Predictive G-code timeshifting with Klipper's ~100 ms lookahead buffer
