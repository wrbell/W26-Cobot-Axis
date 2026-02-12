# Project TODO List

## Architecture

Pi400 serves as HMI (SSH, web UI, development terminal) — not in the real-time control path. A headless Pi runs Klipper + RTDE bridge.

```
                         ┌─── Pi400 (HMI / SSH / Mainsail web UI)
                         │
UR30  ──RTDE/TCP-IP──▶  Pi (Klipper host + RTDE bridge)  ──USB Serial──▶  BTT Pico (RP2040)  ──▶  Stepper Motor
```

- [ ] **Decide which Pi model** for the headless control node (Pi 4B recommended for ethernet + USB; Pi Zero 2W is lower power but lacks wired ethernet)

---

## Design Process (Bolton's 7 Steps)

The course requires that we follow and document Bolton's 7-step design process (see `reqs/process.md`). The final report must explicitly relate our work to this process.

### Step 1: The Need
- [x] Identify the need — additional axis of motion for UR30 cobot, specifically extrusion control
- [x] Document in `reqs/initial_scope.md`

### Step 2: Analysis of the Problem
- [ ] **Write formal problem analysis** — define the true nature of the problem:
  - What does the UR30 lack? (no native extrusion axis)
  - What are the environmental constraints? (industrial cobot cell, 24V power, ethernet comms)
  - What are the performance requirements? (latency, torque, speed range, precision)
  - What failure modes matter? (loss of comms, stepper stall, power fault)
- [ ] Document constraints: UR30 power budget (2A @ 24V), RTDE register limits, physical mounting space

### Step 3: Preparation of a Specification
- [ ] **Write formal design specification** document covering:
  - All required functions (receive commands, drive stepper, report status)
  - Desirable features (Stallguard feedback, web UI monitoring)
  - Mass, dimensions, mounting constraints
  - Input/output requirements for each element
  - Interface specifications (RTDE registers, USB serial, UART)
  - Power requirements (reference `tech_docs/Pi400/power_requirements.md`)
  - Operating environment (cobot cell, temperature, vibration)
  - Accuracy and precision targets
  - Relevant standards

### Step 4: Generation of Possible Solutions
- [x] Lingua Franca vs Klipper trade study → `reqs/trade_lingua_franca_vs_klipper.md`
- [ ] **Location trade study** — end effector mount vs gantry vs base-mounted (per Pannier Review)
- [ ] **Communication approach options** — document alternatives considered:
  - RTDE (selected) vs Dashboard Server vs Primary/Secondary interfaces vs Modbus
  - Reference `tech_docs/UR30/ur_rtde_research.md`
- [ ] **MCU platform options** — document why BTT Pico was selected over alternatives (raw RP2040, Arduino, dedicated stepper controller)

### Step 5: Selection of a Suitable Solution
- [x] Klipper selected (4.70 vs 1.95) — `reqs/trade_lingua_franca_vs_klipper.md`
- [ ] **Document final architecture selection** with rationale for each component choice
- [ ] **Present trade study to Prof. Pannier** — address Lingua Franca suggestion with documented rationale

### Step 6: Production of a Detailed Design
- [ ] Covered by Phase 2 deliverables below (circuit diagrams, analysis, BOM)

### Step 7: Production of Working Drawings
- [ ] Final circuit diagrams (schematic + layout)
- [ ] Final mechanical drawings / CAD for 3D-printed components
- [ ] Wiring diagrams with pin assignments
- [ ] System block diagram (functions and signals)

---

## Phase 1: Ideation and Scope (Complete)

- [x] Team formation and role assignment
  - Willem: Software/EE (RTDE comms, Klipper integration, firmware, electrical docs)
  - Dawood: Mechanical (packaging, cabling, end effector, procurement)
- [x] Project idea submitted — stepper motor driver as 7th axis for UR30
- [x] Scope defined — `reqs/initial_scope.md`
- [x] Instructor go/no-go received — approved with feedback (see Pannier Review notes)

---

## Phase 2: Design and Preliminary Analysis (In Progress)

**Deliverable:** Written memorandum (PDF, ≤5 pages) containing preliminary design, bill of materials, and analysis. Instructor responds with feedback and go/no-go.

### Required Diagrams (phase2.md)

- [ ] **Block diagram of functions/signals** — show data flow: UR30 → RTDE → Pi → Klipper → BTT Pico → stepper, with feedback path
- [ ] **Circuit diagram (schematic)** — UR30 power block → buck converters → Pi + Pi400 + BTT Pico → stepper driver → motor
- [ ] **Circuit layout** — physical arrangement of components and connections
- [ ] **Mechanical component sketches** — end effector mount, electronics packaging (hand sketches or CAD)

### Trade Studies

- [x] Lingua Franca vs Klipper trade study → `reqs/trade_lingua_franca_vs_klipper.md` (Klipper recommended, 4.70 vs 1.95)
- [ ] **Present trade study to Prof. Pannier** — address Lingua Franca suggestion with documented rationale
- [ ] **Location trade study** — end effector mount vs other options (per Pannier Review)

### Electrical Documentation

- [ ] **Pin assignment table** — which pins serve comms vs power vs signal, for each device
- [ ] **Power budget worksheet** — reference `tech_docs/Pi400/power_requirements.md` (total ~1.1A typical @ 24V, fits UR30's 2A continuous)
- [ ] **Select buck converters** — Pololu D24V22F5 (5.1V for Pi + Pi400), add to BOM
- [ ] **Verify stepper motor specs** — get actual datasheet for the stepper we have, confirm voltage/current/torque

### Bill of Materials

- [ ] **Draft BOM** with UMich-contracted suppliers (DigiKey, Newark, Grainger, MSC Direct, BH Photo Video)
- [ ] **Write purchasing instructions** — specific part numbers, quantities, and supplier for each item so instructor can order
- [ ] Items likely needed:
  - [ ] MicroSD cards (for Pi + Pi400)
  - [ ] Gigabit network switch (UR30 ↔ Pi ↔ Pi400 ethernet)
  - [ ] Buck converter(s) — 24V to 5.1V
  - [ ] Cables (USB, ethernet, power)
  - [ ] Fuse + TVS diode for power protection
- [ ] Items on hand (verify):
  - [ ] BigTreeTech Pico board
  - [ ] Raspberry Pi 400
  - [ ] Stepper motor
  - [ ] Additional Raspberry Pi(s)

### 3D-Printed Components (Dawood)

- [ ] **Identify which components need 3D printing** (phase2.md explicitly requires this)
- [ ] **Provide design sketches** (hand or CAD) for each 3D-printed part
- [ ] End effector mounting bracket
- [ ] Electronics enclosure / mounting plate
- [ ] Cable management clips/guides

### CAD / Mechanical (Dawood)

- [ ] End effector mounting design — sketches or CAD
- [ ] Packaging concept for electronics
- [ ] Cabling routing plan

### Engineering Analysis

- [ ] **Motor load calculations** — amperage required vs what the BTT Pico TMC2209 can supply (1.4A RMS max, 2.0A peak)
- [ ] **Torque analysis** — compare stepper motor rated torque vs required torque for extrusion at target speeds
- [ ] **Power budget analysis** — total system draw vs UR30 supply capacity, thermal considerations
- [ ] **Latency analysis** — expected end-to-end latency through communication chain (reference `tech_docs/UR30/ur_rtde_research.md`)

### Phase 2 Submission

- [ ] **Compile Phase 2 PDF** (≤5 pages) containing:
  - Block diagram, circuit diagram, circuit layout, mechanical sketches
  - Bill of materials with purchasing instructions
  - Engineering analysis (motor loads, power budget, latency)
  - Trade study summary
- [ ] **Have one team member edit entire document** for technical writing quality
- [ ] **Submit to instructor** and await feedback + go/no-go decision
- [ ] Use Microsoft Word via UMich Sharepoint/Office 365 (not Google Docs — figure resolution issues)

---

## Phase 3: Build and Additional Design/Analysis

### Build Tasks

#### Klipper Setup (Pi + BTT Pico)
- [ ] **Flash Klipper firmware onto BTT Pico** — `make menuconfig` with RP2040 arch, W25Q080 flash, USB comms (see `tech_docs/BigTree Controller/bigtree_pico_klipper.md`)
- [ ] **Install Klipper + Moonraker on Pi** (MainsailOS or manual install on headless Pi)
- [ ] **Write minimal `printer.cfg`** using `[manual_stepper]` for single-axis control
- [ ] **Test:** Send G-code from Pi, confirm stepper moves
- [ ] **Configure TMC2209 UART** — set run_current, stealthchop threshold
- [ ] **Set up Pi400 as HMI** — connect to same network, access Mainsail/Fluidd web UI, configure SSH to headless Pi

#### RTDE Bridge Daemon (Pi)
- [ ] **Install `ur_rtde` library** on Pi (C++ with Python bindings, or pure Python fallback if ARM build issues)
- [ ] **Write bridge daemon** that:
  - Connects to UR30 via RTDE on port 30004
  - Subscribes to relevant output registers (target TCP speed, digital outputs, general-purpose registers)
  - Translates extrusion commands to Klipper G-code
  - Sends commands to Klipper via Unix socket (`/tmp/klippy_uds`) — lowest latency path
- [ ] **Define register allocation:** Map UR30 general-purpose registers to extrusion parameters (speed, enable, direction, etc.)
- [ ] **Write corresponding URScript program** that writes extrusion commands to RTDE input registers

#### Bidirectional Feedback
- [ ] **Implement status feedback** from Klipper → RTDE bridge → UR30
  - Stepper position/velocity via Klipper object subscriptions
  - Fault/error status

#### Mechanical Assembly (Dawood)
- [ ] 3D print mounting components
- [ ] Assemble electronics onto mounting hardware
- [ ] Route and secure cabling
- [ ] Mount to end effector / robot

### Additional Design/Analysis (expected per about.md)
- [ ] Revisit and refine any design elements based on build experience
- [ ] Update circuit diagrams if build deviates from Phase 2 design
- [ ] Document any design changes with rationale

### Phase 3 Deliverable
- [ ] **Write progress update memorandum** to instructor (required during this phase per `reqs/about.md`)

---

## Phase 4: Test and Reporting

### System Testing
- [ ] **End-to-end functional test** — UR30 sends extrusion command → stepper moves at correct speed
- [ ] **Latency characterization** — measure actual end-to-end latency (estimated 5–20ms)
- [ ] **Accuracy test** — commanded vs actual stepper position/speed
- [ ] **Fault handling test** — loss of comms, stepper stall, power interruption
- [ ] **Endurance test** — run for extended period, check for thermal or reliability issues
- [ ] Document test procedures and results with data

### Stretch Goals (Test if Time Permits)
- [ ] **Stallguard torque feedback** — BTT Pico TMC2209 Stallguard4 via DIAG pins → Klipper `register_remote_method` → RTDE → URScript
- [ ] **G-code timeshifting** — if latency is predictable, use Klipper's ~100ms lookahead buffer
- [ ] **URCap** for teach pendant UI (Java SDK, not needed for MVP)

### Final Report (Due Thu Apr 23, 2026)

**Requirements from `reqs/phase3.md`:**

- [ ] **Write final report** (PDF, ≤2000 words — figures/tables don't count toward limit)
- [ ] **Relate work to course topics:** design process, control systems, system diagrams, sensors, signal conditioners, circuits, electrical actuators, microcontrollers, system models
- [ ] **Map to Bolton's 7-step design process** — show how each step was addressed
- [ ] **Include team member work listing** — who did what
- [ ] **Figures and tables** — use liberally to convey ideas (don't count toward word limit)
- [ ] **References and in-text citations**
- [ ] **Use Word Styles** (headings, caption styles) — use Microsoft Word via UMich Office 365
- [ ] **One team member edits entire report** for technical writing before submission
- [ ] **Attach supplementary materials:** drawings, computer code in native formats, preliminary design

### Oral Presentation (Final Exam Slot — Apr 24, 2026, 6:30–9:30 PM)

- [ ] **Prepare presentation** — brief overview and demonstration of prototype
- [ ] **Practice design defense** — prepare to answer technical questions about design choices and performance
- [ ] **Prepare prototype for demonstration**

---

## Open Investigation Items

- [ ] **Network switch selection** — any gigabit switch works, but verify UR30 controller ethernet port availability
- [ ] **UR communication protocol deep-dive** — RTDE is primary, but evaluate if Dashboard Server (port 29999) is useful for supplementary control (program start/stop/pause)
- [ ] **Klipper forking** — may be needed if we want custom Stallguard data passthrough beyond what stock Klipper provides. Evaluate after basic chain works.

---

## Learning / Ramp-Up Tasks (from Pannier Review)

- [ ] Get familiar with Linux/Bash — [Ubuntu CLI tutorial](https://ubuntu.com/tutorials/command-line-for-beginners#1-overview)
- [ ] Get familiar with Raspberry Pi — [Pi getting started guide](https://www.raspberrypi.com/documentation/computers/getting-started.html)
- [ ] Get familiar with URScript & RTDE — reference `tech_docs/UR30/ur_rtde_research.md`
- [ ] Get familiar with Klipper — [klipper3d.org](https://www.klipper3d.org/) + `tech_docs/Klipper/klipper_protocols.md`
- [ ] Get familiar with stepper motor driving — [Adafruit RP2040 motor guide](https://learn.adafruit.com/use-dc-stepper-servo-motor-solenoid-rp2040-pico/overview) (reference only, not our approach)
- [ ] Review RP2040 hardware design — [RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/hardware-design-with-rp2040.pdf)

---

## Research Documents Index

| Document | Location |
|----------|----------|
| Klipper protocols & API | `tech_docs/Klipper/klipper_protocols.md` |
| BigTree Pico + Klipper | `tech_docs/BigTree Controller/bigtree_pico_klipper.md` |
| UR RTDE research | `tech_docs/UR30/ur_rtde_research.md` |
| Power requirements | `tech_docs/Pi400/power_requirements.md` |
| Lingua Franca vs Klipper trade | `reqs/trade_lingua_franca_vs_klipper.md` |
| Accelerated schedule | `schedule.md` |
| Design process | `reqs/process.md` |
| Phase 2 requirements | `reqs/phase2.md` |
| Phase 3/4 requirements | `reqs/phase3.md` |
| Project overview | `reqs/about.md` |
| Initial scope | `reqs/initial_scope.md` |
