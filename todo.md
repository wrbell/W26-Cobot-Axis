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
- [x] Pin assignment table (rough draft) → `docs/phase2/pin_assignments.md`
- [x] Power budget worksheet (rough draft) → `docs/phase2/power_budget.md`

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
- [x] Circuit diagram description (rough draft) → `docs/phase2/circuit_schematic.md`
- [ ] Circuit layout (physical arrangement) — Dawood + Willem
- [x] Block diagram of functions/signals (rough draft) → `docs/phase2/block_diagram.md`
- [x] Bill of materials with purchasing instructions (rough draft) → `docs/phase2/bom.md`
- [x] Buck converter selection → `docs/phase2/buck_converter.md` — Pololu D24V22F5
- [ ] Engineering analysis (motor loads — pending hardware receipt)
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
- [x] **Block diagram of functions/signals** — rough draft → `docs/phase2/block_diagram.md` (needs redraw in draw.io/Visio)
- [x] **Circuit diagram (schematic)** — rough draft → `docs/phase2/circuit_schematic.md` (needs redraw in KiCad/draw.io)
- [ ] **Circuit layout** — physical arrangement (Dawood + Willem)
- [ ] **Mechanical component sketches** (Dawood)

### Trade Studies
- [x] Lingua Franca vs Klipper → `trades/lingua_franca_vs_klipper.md`
- [x] Communication protocol → `trades/comms.md`
- [x] MCU platform → `trades/mcu.md`
- [ ] **Location trade study** (Dawood)
- [ ] **Present trade studies to Prof. Pannier**

### Electrical Documentation
- [x] **Pin assignment table** — rough draft → `docs/phase2/pin_assignments.md`
- [x] **Power budget worksheet** — rough draft → `docs/phase2/power_budget.md`
- [x] **Select buck converters** — Pololu D24V22F5 selected → `docs/phase2/buck_converter.md`

### Bill of Materials
- [x] **Draft BOM** with DigiKey/Newark part numbers → `docs/phase2/bom.md` (~$183 total, 28 items, most P/Ns verified)
- [x] **Write purchasing instructions** — included in `docs/phase2/bom.md`

### 3D-Printed Components (Dawood)
- [ ] Identify which components need 3D printing
- [ ] Design sketches for each part

### Engineering Analysis
- [x] Latency analysis → `docs/latency_analysis.md`
- [x] Problem analysis → `docs/problem_analysis.md`
- [ ] **Motor load calculations** — pending hardware receipt
- [ ] **Torque analysis** — pending hardware receipt
- [x] **Power budget analysis** — rough draft → `docs/phase2/power_budget.md`

### Phase 2 Memo Draft
- [x] **Memo text draft** — all 8 sections (~1,400 words) → `docs/phase2/memo_draft.md`
- [ ] Redraw block diagram in draw.io/Visio (from `docs/phase2/block_diagram.md`)
- [ ] Redraw circuit schematic in KiCad/draw.io (from `docs/phase2/circuit_schematic.md`)
- [x] Verify DigiKey/Newark part numbers and stock — 10 of 14 verified/corrected; 2 unverified (MicroSD, USB cable), 2 need final check (wire spools, screw terminals)
- [ ] Dawood: write Section 5 (mechanical concept) + Figures 3–4

### Phase 2 Submission Checklist (due Mar 1)

**Willem (before Feb 28):**
- [ ] Redraw block diagram in draw.io or Visio → export as Figure 1
- [ ] Redraw circuit schematic in KiCad or draw.io → export as Figure 2
- [ ] Paste memo text from `docs/phase2/memo_draft.md` into Word template
- [ ] Insert all 5 tables from memo draft
- [ ] Insert Figures 1–2, add captions

**Dawood (before Feb 28):**
- [ ] Write Section 5 (mechanical concept, ~150 words)
- [ ] Create Figure 3 (physical layout sketch) and Figure 4 (mechanical concept)
- [ ] Location trade study (even a brief rationale is fine for the memo)

**Together (Feb 28 – Mar 1):**
- [ ] One person edits the entire document for consistency
- [ ] Verify total page count ≤ 5
- [ ] Export to PDF, submit to instructor

**Already done (no action needed):**
- [x] Memo text — 8 sections, ~1,400 words → `docs/phase2/memo_draft.md`
- [x] BOM with verified part numbers (~$183) → `docs/phase2/bom.md`
- [x] All electrical docs (pin table, power budget, buck converter)
- [x] 3 trade studies with scores

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
- [ ] **URSim integration testing** — moved to Phase 3 "Pre-Hardware: URSim Validation" section

### Klipper Configuration (`src/klipper/`)
- [x] `printer.cfg` — SKR Pico config with `[manual_stepper pump]`, TMC2209 UART, E-axis driver
- [x] `moonraker.conf` — Moonraker API config (port 7125, trusted clients, CORS, update manager)
- [x] `mainsail.cfg` — Pump-specific macros (PUMP_STATUS, PUMP_TEST, PUMP_ENABLE/DISABLE, PUMP_ZERO)

### URScript (`src/urscript/`)
- [x] `extrusion_control.script` — helper functions, `pump_on()`/`pump_off()` for slicer integration, `extrude_along_path()` for speed-sync, retraction
- [x] `test_basic.script` — system validation test (10 sub-tests: A–I + G2; Sub-test G tests constant-rate multi-waypoint pattern, G2 tests speed-sync)
- [x] `test_calibration.script` — pump calibration (5 sub-tests: A linearity, B speed-sync gravimetric, B2 constant-rate gravimetric, C retraction, D latency)

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
- [x] **Stepper driving design** → `docs/design/stepper_driving.md` — consolidated justification for manual_stepper, TMC2209 config, step generation pipeline, calibration

---

## Phase 3: Build and Additional Design/Analysis (Weeks 9–11, Mar 2–22)

Full integration plan with troubleshooting: `docs/design/integration_plan.md`

### Pre-Hardware: URSim Validation (can start now)

- [ ] **Set up URSim on Windows** — `docker run --platform=linux/amd64 -e ROBOT_MODEL=UR30 -p 30004:30004 -p 29999:29999 -p 6080:6080 universalrobots/ursim_e-series`
- [ ] **Load slicer output into URSim** — verify `src/provided/Mblack0.6mm.script` executes cleanly (no joint limits, no singularities, path looks correct in 3D view)
- [ ] **Test bridge daemon against URSim** — connect via RTDE on port 30004, verify register read/write, mode transitions
- [ ] **Load wrapped slicer program into URSim** — test `pump_on()`/`pump_off()` wrapping of slicer output with bridge daemon running (Klipper side mocked)

### Stage 1: Klipper on Pi (Week 9, Day 1)

- [ ] Flash MainsailOS onto Pi SD card (enable SSH, set hostname `w26-pi`)
- [ ] Boot Pi, verify SSH access: `ssh pi@w26-pi.local`
- [ ] Verify `klipper` and `moonraker` services loaded: `systemctl status klipper moonraker`
- [ ] Verify Mainsail web UI responds at `http://w26-pi.local` (errors OK — no printer.cfg yet)

### Stage 2: SKR Pico Firmware (Week 9, Day 1–2)

- [ ] Build Klipper MCU firmware: `make menuconfig` → RP2040, no bootloader, W25Q080 CLKDIV 2, USB
- [ ] Flash via BOOTSEL: hold button, plug USB, copy `klipper.uf2` to `RPI-RP2` drive
- [ ] Verify USB serial enumeration: `ls /dev/serial/by-id/usb-Klipper_rp2040_*`
- [ ] Deploy `printer.cfg` to `~/printer_data/config/`, update `[mcu]` serial path
- [ ] Restart Klipper, confirm `Printer is ready` in klippy.log and Mainsail shows green

### Stage 3: First Stepper Motion (Week 9, Day 2–3)

- [ ] Wire stepper motor to SKR Pico E-axis connector (identify coils with multimeter)
- [ ] Apply 24V to SKR Pico VIN (verify polarity first)
- [ ] Send test G-code via Mainsail console:
  - `MANUAL_STEPPER STEPPER=pump ENABLE=1`
  - `MANUAL_STEPPER STEPPER=pump SET_POSITION=0`
  - `MANUAL_STEPPER STEPPER=pump MOVE=10 SPEED=5` → observe motor rotates
- [ ] Verify direction: positive MOVE = extrude, negative = retract (flip `dir_pin` polarity if wrong)
- [ ] Test speeds: 5, 25, 50 mm/s
- [ ] Disable stepper: `MANUAL_STEPPER STEPPER=pump ENABLE=0`

### Stage 4: TMC2209 Tuning (Week 9, Day 3–4)

- [ ] Read motor nameplate current rating
- [ ] Set `run_current` to 70–80% of rating, `hold_current` to 50–70% of `run_current`
- [ ] Run sustained motion test: `MOVE=1000 SPEED=25` (~40s), monitor TMC2209 temperature (< 80°C target)
- [ ] Verify StealthChop operation (should be near-silent at low speeds)
- [ ] If motor stalls under pump load: increase `run_current` by 0.1A increments (do not exceed motor rating or 1.2A)
- [ ] `DUMP_TMC STEPPER="manual_stepper pump"` — verify no error flags
- [ ] Commit updated `printer.cfg` with final current settings

### Stage 5: Bridge Daemon on Pi (Week 9, Day 4–5)

- [ ] Clone repo onto Pi (or SCP `src/bridge/`)
- [ ] Install deps: `pip3 install ur-rtde` (fallback: stub mode if ARM build fails)
- [ ] Test dry-run: `python3 -m src.bridge.bridge_daemon --dry-run --log-level DEBUG`
- [ ] Test Klipper connection directly (bypass RTDE):
  ```python
  from bridge.klipper_client import KlipperClient
  k = KlipperClient("/tmp/klippy_uds")
  k.connect()
  k.stepper_move("pump", 5.0, 10.0)  # motor should move
  k.stepper_disable("pump")
  k.disconnect()
  ```

### Stage 6: RTDE Connection to UR30 (Week 10)

- [ ] Verify network: `ping <UR30_IP>`, `nc -zv <UR30_IP> 30004`
- [ ] Update `config.py` with UR30 IP address
- [ ] Test RTDE independently: read output registers, write input registers (see `docs/design/integration_plan.md` Stage 6 for test scripts)
- [ ] Load `extrusion_control.script` onto UR30 teach pendant (USB drive or SSH)
- [ ] Run bridge daemon with RTDE: `python3 -m src.bridge.bridge_daemon --host <UR30_IP> --log-level DEBUG`
- [ ] Verify bridge logs show RTDE read/write cycles at 125 Hz
- [ ] Verify teach pendant shows input register values (status, ready flag)

### Stage 7: End-to-End Smoke Test (Week 10–11)

- [ ] All services running: Klipper + Moonraker + bridge daemon + URScript program
- [ ] From UR30: enable + mode=EXTRUDE + rate=10.0 → **stepper moves** (the milestone)
- [ ] Test speed changes: ramp 0→50 mm/s, verify smooth acceleration
- [ ] Test mode transitions: extrude → retract → off
- [ ] Test e-stop: `output_bit_register_65 = True` → stepper halts immediately
- [ ] Verify status feedback: UR30 reads status=RUNNING during extrusion, IDLE when stopped
- [ ] Run `test_basic.script` Sub-tests A–F, I (no robot motion tests)
- [ ] Teach waypoints, run Sub-test G (constant-rate multi-waypoint path)
- [ ] Latency measurement (if oscilloscope available): probe step pin (gpio14), measure command-to-pulse delay

### Stage 7b: Slicer Integration (Week 11)

- [ ] Wrap `src/provided/Mblack0.6mm.script` with `pump_on()`/`pump_off()` from `extrusion_control.script`
- [ ] Load wrapped program onto UR30, run with bridge daemon active
- [ ] Verify pump runs continuously during 776-waypoint path and stops cleanly at the end
- [ ] Run calibration `test_calibration.script` Sub-test A (flow rate linearity) — determine optimal constant rate
- [ ] Run calibration Sub-test B2 (constant-rate multi-waypoint gravimetric) — verify consistent dispensing
- [ ] Tune `EXTRUSION_MULTIPLIER` and retraction parameters based on calibration results

### Stage 8: Pi400 HMI (Week 11, parallel)

- [ ] Connect Pi400 to same network (switch or WiFi)
- [ ] Verify Mainsail UI at `http://w26-pi.local` — monitor stepper status, send G-code
- [ ] Verify SSH: `ssh pi@w26-pi.local`
- [ ] Configure Moonraker trusted clients if needed

### Mechanical Assembly (Dawood, parallel with Stages 1–7)

- [ ] 3D print mounting components
- [ ] Assemble electronics onto mounting hardware
- [ ] Route and secure cabling
- [ ] Mount to end effector / robot

### Phase 3 Deliverable

- [x] **Progress memo template** drafted → `docs/phase3/progress_memo_draft.md` (fill in after hardware testing)
- [ ] **Fill in test results and placeholders** — after bench and integration testing
- [ ] **Submit progress memorandum** to instructor

---

## Phase 4: Test and Reporting (Weeks 12–13, Mar 23 – Apr 5)

Full test procedures with pass/fail criteria and data sheets: `docs/design/test_procedures.md`

### TP-01: End-to-End Functional Test (45 min, Week 12)

Verifies the full communication chain responds to all commands.

- [ ] Test all mode transitions: enable → extrude (5, 10, 25, 50 mm/s) → retract → off
- [ ] Test rate clamping: command 75 mm/s, verify clamped to 50 mm/s
- [ ] Test e-stop during motion: stepper halts, status=ERROR reported to UR30
- [ ] Test recovery from e-stop: clear fault, re-enable, verify system accepts new commands
- [ ] Test homing: position zeros, status returns to IDLE
- [ ] Record bridge daemon logs and teach pendant register screenshots at each step

### TP-02: Latency Characterization (90 min, Week 12)

Measures actual end-to-end latency; compare against 8 ms prediction in `docs/latency_analysis.md`.

- [ ] **Method A (software):** RTDE timestamp comparison — measures UR30-to-bridge latency segments
- [ ] **Method B (oscilloscope):** Probe step pin (gpio14), single-shot trigger on first pulse after cold-start command — 10 measurements
- [ ] **Method C (step-change):** Steady 10 mm/s → step to 30 mm/s, capture frequency transition — 50 measurements
- [ ] Compute statistics: mean, std dev, P95, P99, min, max
- [ ] **Pass criteria:** P95 < 20 ms, no outlier > 100 ms
- [ ] Generate latency histogram figure for final report

### TP-03: Speed Accuracy Test (60 min, Week 12)

Quantifies commanded vs actual speed across operating range.

- [ ] Steady-state accuracy: measure step frequency at 5, 10, 20, 30, 50 mm/s (extrude + retract), 5 readings each
- [ ] Compute steady-state error for each setpoint (target: < 2%)
- [ ] Transient response: oscilloscope capture of 10→30, 30→10, 0→50, 50→0 mm/s step changes
- [ ] Measure rise/fall times
- [ ] Rapid alternation: 10↔30 mm/s at 1 Hz for 10 cycles — no stalls

### TP-04: Fault Handling Test (75 min, Week 13)

Injects each failure mode from the problem analysis and verifies safe response.

- [ ] **TP-04a: RTDE disconnect** — pull Ethernet cable during extrusion → stepper stops within 2s, ERR_COMMS_LOST reported, auto-reconnects on cable restore
- [ ] **TP-04b: Stepper stall** — manually block motor shaft → document open-loop behavior (no detection without StallGuard), `DUMP_TMC` status, motor temperature
- [ ] **TP-04c: Klipper crash** — `kill -9 klippy` during extrusion → stepper stops (MCU host timeout), bridge detects and reports error, recovers on Klipper restart
- [ ] **TP-04d: USB disconnect** — pull USB cable → stepper stops immediately, Klipper enters shutdown, bridge reports fault, recovers after reconnect + restart

### TP-05: Endurance Test (90 min, Week 13)

60-minute continuous run at representative speeds.

- [ ] Speed profile: ramp to 20 mm/s → alternate 15/25 every 30s → 50 mm/s burst → ramp down
- [ ] Temperature monitoring every 10 min: TMC2209 (< 100°C), motor (< 80°C), Pi CPU (< 80°C), RP2040
- [ ] Zero communication errors in bridge log over 60 min
- [ ] No speed drift: post-test frequency within 1% of initial measurement
- [ ] 24V current draw within 2A budget (if clamp meter available)

### URScript Test Programs on Hardware

- [ ] Run full `test_basic.script` (Sub-tests A–I + G + G2) with taught waypoints — all sub-tests pass
- [ ] Run full `test_calibration.script` (Sub-tests A, B, B2, C, D) — record all calibration data
- [ ] Finalize `EXTRUSION_MULTIPLIER`, retraction parameters, and Klipper accel/velocity from calibration results

### Stretch Goals (if time permits)

- [ ] **StallGuard torque feedback** — TMC2209 DIAG → Klipper → RTDE → URScript (would change TP-04b from open-loop to closed-loop stall detection)
- [ ] **G-code timeshifting** — compensate Klipper lookahead buffer latency
- [ ] **URCap** for teach pendant UI (Java SDK)

### Final Report (Due Apr 23)

- [ ] **Write final report** (PDF, ≤2000 words)
- [ ] **Map to Bolton's 7-step design process**
- [ ] **Relate to course topics** — control systems, circuits, actuators, microcontrollers, system models
- [ ] **Team member work listing**
- [ ] **Figures and tables** — latency histogram (TP-02), speed accuracy chart (TP-03), transient response scope captures, temperature vs time (TP-05), block diagram, circuit schematic, system photo
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
