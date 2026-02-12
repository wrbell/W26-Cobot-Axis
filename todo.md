# Project TODO List

## Architecture

```
                         ┌─── Pi400 (optional HMI / SSH / Mainsail web UI)
                         │
UR30  ──RTDE/TCP-IP──▶  Pi (Klipper host + RTDE bridge)  ──USB Serial──▶  SKR Pico (RP2040)  ──▶  Stepper Motor  ──▶  Pump
```

- [ ] **Decide which Pi model** for headless control node (Pi 4B recommended)
- Pump and motor will be **provided to the team** — specs TBD on receipt

---

## Design Process (Bolton's 7 Steps)

### Step 1: The Need — Complete
- [x] Identify the need — UR30 lacks a native extrusion axis for metal paste dispensing
- [x] Document in `reqs/initial_scope.md`

### Step 2: Analysis of the Problem — Complete
- [x] Formal problem analysis → `docs/problem_analysis.md`
- [x] Latency analysis → `docs/latency_analysis.md`

### Step 3: Preparation of a Specification — In Progress
- [x] RTDE register allocation finalized → `docs/register_allocation.md`
- [x] **Formal design specification** → `docs/design_specification.md` — 25 "shall" statements, interface tables, performance targets
- [ ] Pin assignment table
- [ ] Power budget worksheet

### Step 4: Generation of Possible Solutions — In Progress
- [x] Lingua Franca vs Klipper → `trades/lingua_franca_vs_klipper.md` (Klipper: 4.70 vs 1.95)
- [x] Communication protocol → `trades/comms.md` (RTDE: 4.85 vs next-best 3.30)
- [x] MCU platform → `trades/mcu.md` (SKR Pico selected)
- [ ] **Location trade study** — end effector vs base-mounted vs gantry (Dawood)

### Step 5: Selection of a Suitable Solution — Complete
- [x] Klipper selected
- [x] RTDE selected
- [x] SKR Pico selected (on hand)
- [x] Architecture documented in README and CLAUDE.md
- [ ] **Present trade studies to Prof. Pannier** — address Lingua Franca suggestion

### Step 6: Production of a Detailed Design — In Progress
- [ ] Circuit diagram (schematic)
- [ ] Circuit layout (physical arrangement)
- [ ] Block diagram of functions/signals
- [ ] Bill of materials with purchasing instructions
- [ ] Engineering analysis (motor loads, power budget)
- [ ] 3D-printed component designs (Dawood)

### Step 7: Production of Working Drawings — Upcoming
- [ ] Final circuit schematics
- [ ] Final mechanical drawings / CAD
- [ ] Wiring diagrams with pin assignments
- [ ] System block diagram

---

## Phase 1: Ideation and Scope — Complete (Week 5)

- [x] Team formation and role assignment
- [x] Project idea submitted
- [x] Scope defined — `reqs/initial_scope.md`
- [x] Instructor go/no-go received

---

## Phase 2: Design and Preliminary Analysis — In Progress (Weeks 6–8, target Mar 1)

**Deliverable:** Written memo (PDF, ≤5 pages) with preliminary design, BOM, and analysis.

### Required Diagrams
- [ ] **Block diagram of functions/signals** — data flow with feedback path
- [ ] **Circuit diagram (schematic)** — UR30 power → buck converters → Pi + SKR Pico → stepper
- [ ] **Circuit layout** — physical arrangement
- [ ] **Mechanical component sketches** (Dawood)

### Trade Studies
- [x] Lingua Franca vs Klipper → `trades/lingua_franca_vs_klipper.md`
- [x] Communication protocol → `trades/comms.md`
- [x] MCU platform → `trades/mcu.md`
- [ ] **Location trade study** (Dawood)
- [ ] **Present trade studies to Prof. Pannier**

### Electrical Documentation
- [ ] **Pin assignment table** — all devices
- [ ] **Power budget worksheet**
- [ ] **Select buck converters** — Pololu D24V22F5, add to BOM

### Bill of Materials
- [ ] **Draft BOM** with UMich supplier part numbers
- [ ] **Write purchasing instructions**

### 3D-Printed Components (Dawood)
- [ ] Identify which components need 3D printing
- [ ] Design sketches for each part

### Engineering Analysis
- [x] Latency analysis → `docs/latency_analysis.md`
- [x] Problem analysis → `docs/problem_analysis.md`
- [ ] **Motor load calculations** — pending hardware receipt
- [ ] **Torque analysis** — pending hardware receipt
- [ ] **Power budget analysis**

### Phase 2 Submission
- [ ] **Compile Phase 2 PDF** (≤5 pages)
- [ ] **One team member edits entire document**
- [ ] **Submit to instructor** — target Mar 1
- [ ] Use Microsoft Word via UMich Office 365

---

## Software Development — No Hardware Required

All software in `src/`. Can be developed and tested without physical hardware.

### Bridge Daemon (`src/bridge/`)

#### Core — Written
- [x] `config.py` — register mappings, connection defaults, constants
- [x] `klipper_client.py` — klippy Unix socket client (connect, G-code, status query, stepper commands)
- [x] `rtde_client.py` — ur_rtde wrapper with stub fallback for dev without robot
- [x] `bridge_daemon.py` — main loop: RTDE read → translate → Klipper command → status writeback
- [x] `__main__.py` — entry point for `python -m bridge`
- [x] Register allocation implemented matching `docs/register_allocation.md`
- [x] E-stop, homing, enable/disable, mode switching
- [x] Reconnection logic for dropped RTDE or Klipper connections
- [x] `--dry-run` mode for testing without Klipper

#### Enhancements — Written
- [x] **Klipper status subscription** — TMC2209 driver status polling with stall detection (`klipper_status.py`)
- [x] **Speed-proportional extrusion mode** — bridge-computed rate from TCP speed × multiplier
- [x] **Data logging** — 17-column CSV with file rotation and event annotations (`data_logger.py`)
- [x] **Watchdog timer** — RTDE timestamp-based stale detection, 0.5s timeout (`watchdog.py`)
- [x] **Configurable extrusion profiles** — linear, polynomial, lookup table (`extrusion_profile.py`, `profiles.json`)
- [x] **Dashboard Server client** — UR30 port 29999 lifecycle management (`dashboard_client.py`)

#### Testing
- [x] **Unit tests for `klipper_client.py`** — 42 tests, mock Unix socket, JSON protocol, error handling
- [x] **Unit tests for `rtde_client.py`** — 34 tests, stub mode, register read/write
- [x] **Unit tests for `bridge_daemon.py`** — 71 tests, command translation, e-stop, mode switching, reconnection
- [ ] **Set up URSim on Windows** — `docker run --platform=linux/amd64 -e ROBOT_MODEL=UR30 -p 30004:30004 -p 29999:29999 -p 6080:6080 universalrobots/ursim_e-series` (native x86, no emulation needed)
- [ ] **Integration test: bridge + URSim** — verify register read/write, mode transitions, fault injection

### Klipper Configuration (`src/klipper/`)
- [x] `printer.cfg` — SKR Pico config with `[manual_stepper pump]`, TMC2209 UART, E-axis driver
- [x] `moonraker.conf` — Moonraker API config (port 7125, trusted clients, CORS, update manager)
- [x] `mainsail.cfg` — Pump-specific macros (PUMP_STATUS, PUMP_TEST, PUMP_ENABLE/DISABLE, PUMP_ZERO)

### URScript (`src/urscript/`)
- [x] `extrusion_control.script` — helper functions, speed-sync extrusion, retraction, fault checking
- [x] `test_basic.script` — system validation test (9 sub-tests: init, enable/disable, extrude, retract, homing, e-stop, speed-sync, fault handling, readback)
- [x] `test_calibration.script` — pump calibration (4 sub-tests: flow rate linearity, speed-sync gravimetric, retraction effectiveness, latency measurement)

### Deployment — Written
- [x] `requirements.txt` — Python dependencies (ur-rtde)
- [x] `src/systemd/w26-bridge.service` — systemd service, auto-start after Klipper
- [x] `deploy.sh` — 11-step deployment script (deps, configs, firmware, verification)
- [x] `SETUP.md` — step-by-step setup instructions for fresh Pi

### Design Documents — Complete
All software features are being designed before implementation. Design docs in `docs/design/`.

- [x] **Phase 2 deliverables planning** → `docs/design/phase2_deliverables.md`
- [x] **Bridge enhancements design** → `docs/design/bridge_enhancements.md`
- [x] **Testing strategy design** → `docs/design/testing_strategy.md`
- [x] **Klipper/Moonraker config design** → `docs/design/klipper_config.md`
- [x] **URScript programs design** → `docs/design/urscript_programs.md`
- [x] **Deployment design** → `docs/design/deployment.md`
- [x] **Phase 3 integration plan** → `docs/design/integration_plan.md`
- [x] **Phase 4 test procedures** → `docs/design/test_procedures.md`
- [x] **Network architecture** → `docs/design/network_architecture.md`
- [x] **Phase 2 memo outline** → `docs/design/phase2_memo_outline.md`
- [x] **Final report outline** → `docs/design/final_report_outline.md`
- [x] **Update `docs/pi_power.md`** — fixed stale dual-Pi architecture references

---

## Phase 3: Build and Additional Design/Analysis (Weeks 9–11, Mar 2–22)

### Hardware Setup (requires hardware)
- [ ] **Flash Klipper firmware onto SKR Pico** — `make menuconfig` RP2040, W25Q080, USB
- [ ] **Install Klipper + Moonraker on Pi** (MainsailOS or manual)
- [ ] **Deploy `printer.cfg`** to Pi
- [ ] **Test:** send G-code from Pi, confirm stepper moves
- [ ] **Tune TMC2209** — run_current based on actual motor specs, StealthChop threshold
- [ ] **Set up Pi400 as HMI** — same network, Mainsail web UI, SSH

### Integration (requires hardware)
- [ ] **Deploy bridge daemon to Pi** — install deps, test with UR30
- [ ] **Deploy URScript to UR30** — load via teach pendant or SSH
- [ ] **End-to-end smoke test** — UR30 sends extrude command → stepper moves
- [ ] **Tune extrusion multiplier** — calibrate mm extruded per mm/s TCP speed
- [ ] **Tune Klipper accel/velocity limits** — match pump mechanical capabilities

### Mechanical Assembly (Dawood)
- [ ] 3D print mounting components
- [ ] Assemble electronics onto mounting hardware
- [ ] Route and secure cabling
- [ ] Mount to end effector / robot

### Phase 3 Deliverable
- [ ] **Write progress update memorandum** to instructor

---

## Phase 4: Test and Reporting (Weeks 12–13, Mar 23 – Apr 5)

### System Testing (target: complete by Mar 31)
- [ ] **End-to-end functional test** — UR30 → stepper at correct speed
- [ ] **Latency characterization** — oscilloscope on step pin, measure actual latency
- [ ] **Accuracy test** — commanded vs actual speed/position
- [ ] **Fault handling test** — loss of comms, stepper stall, power interruption
- [ ] **Endurance test** — extended run, check thermal / reliability
- [ ] Document test procedures and results with data

### Stretch Goals (if time permits)
- [ ] **StallGuard torque feedback** — TMC2209 DIAG → Klipper → RTDE → URScript
- [ ] **G-code timeshifting** — compensate Klipper lookahead buffer latency
- [ ] **URCap** for teach pendant UI (Java SDK)

### Final Report (Due Apr 23)
- [ ] **Write final report** (PDF, ≤2000 words)
- [ ] **Map to Bolton's 7-step design process**
- [ ] **Relate to course topics** — control systems, circuits, actuators, microcontrollers, system models
- [ ] **Team member work listing**
- [ ] **Figures and tables**
- [ ] **References and citations**
- [ ] **Use Word Styles** via UMich Office 365
- [ ] **One team member edits entire report**
- [ ] **Attach supplementary materials** — code, drawings

### Oral Presentation (Apr 24, 6:30–9:30 PM)
- [ ] Prepare presentation
- [ ] Practice design defense
- [ ] Prepare prototype for demonstration

---

## Research Documents Index

| Document | Location |
|----------|----------|
| Problem analysis (Bolton Step 2) | `docs/problem_analysis.md` |
| RTDE register allocation | `docs/register_allocation.md` |
| Latency analysis | `docs/latency_analysis.md` |
| Trade: Klipper vs Lingua Franca | `trades/lingua_franca_vs_klipper.md` |
| Trade: Communication protocol | `trades/comms.md` |
| Trade: MCU platform | `trades/mcu.md` |
| Information needs tracker | `reqs/information_needs.md` |
| Klipper protocols & API | `docs/klipper_protocols.md` |
| SKR Pico V1.0 specs | `docs/skr_pico_specs.md` |
| SKR Pico + Klipper setup | `docs/skr_pico_klipper_setup.md` |
| UR RTDE research | `docs/ur_rtde.md` |
| Power requirements | `docs/pi_power.md` |
| Design process | `reqs/process.md` |
| Phase 2 requirements | `reqs/phase2.md` |
| Phase 3/4 requirements | `reqs/phase3.md` |
| Project overview | `reqs/about.md` |
| Accelerated schedule | `schedule.md` |

## Source Code Index

| Component | Location | Status |
|-----------|----------|--------|
| Bridge daemon (main loop) | `src/bridge/bridge_daemon.py` | Written |
| Bridge config (registers, constants) | `src/bridge/config.py` | Written |
| Klipper Unix socket client | `src/bridge/klipper_client.py` | Written |
| RTDE client wrapper | `src/bridge/rtde_client.py` | Written |
| Klipper printer config | `src/klipper/printer.cfg` | Written |
| URScript extrusion program | `src/urscript/extrusion_control.script` | Written |
| URScript validation test | `src/urscript/test_basic.script` | Written |
| URScript calibration test | `src/urscript/test_calibration.script` | Written |
