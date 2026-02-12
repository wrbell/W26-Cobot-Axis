# Project TODO List

## Architecture

Pi400 serves as HMI (SSH, web UI, development terminal) — not in the real-time control path. A headless Pi runs Klipper + RTDE bridge.

```
                         ┌─── Pi400 (HMI / SSH / Mainsail web UI)
                         │
UR30  ──RTDE/TCP-IP──▶  Pi (Klipper host + RTDE bridge)  ──USB Serial──▶  BTT Pico (RP2040)  ──▶  Stepper Motor
```

- [ ] **Update block diagram** for Phase 2 deliverable to reflect this architecture
- [ ] **Decide which Pi model** for the headless control node (Pi 4B recommended for ethernet + USB; Pi Zero 2W is lower power but lacks wired ethernet)

---

## Phase 2 Deliverables (Design & Preliminary Analysis)

### Trade Studies
- [x] Lingua Franca vs Klipper trade study → `reqs/trade_lingua_franca_vs_klipper.md` (Klipper recommended, 4.70 vs 1.95)
- [ ] **Present trade study to Prof. Pannier** — address Lingua Franca suggestion with documented rationale
- [ ] Location trade study — end effector mount vs other options (per Pannier Review)

### Electrical Documentation
- [ ] **Create circuit/block diagram** showing physical layer: UR30 power block → buck converters → Pi + Pi400 + BTT Pico → stepper
- [ ] **Pin assignment table** — which pins serve comms vs power vs signal, for each device
- [ ] **Power budget worksheet** — reference `tech_docs/Pi400/power_requirements.md` (total ~1.1A typical @ 24V, fits UR30's 2A continuous)
- [ ] **Select buck converters** — Pololu D24V22F5 (5.1V for Pi + Pi400), add to BOM
- [ ] **Verify stepper motor specs** — get actual datasheet for the stepper we have, confirm voltage/current/torque

### Bill of Materials
- [ ] **Draft BOM** with UMich-contracted suppliers (DigiKey, Newark, Grainger, MSC Direct, BH Photo Video)
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

### CAD / Mechanical (Dawood)
- [ ] End effector mounting design — sketches or CAD for 3D-printed components
- [ ] Packaging concept for electronics
- [ ] Cabling routing plan

### Analysis
- [ ] **Motor load calculations** — amperage required vs what the BTT Pico TMC2209 can supply (1.4A RMS max, 2.0A peak)
- [ ] Compare against stepper motor rated current and required torque for extrusion

---

## Software — Immediate Next Steps

### 1. Klipper Setup (Pi + BTT Pico)
- [ ] **Flash Klipper firmware onto BTT Pico** — `make menuconfig` with RP2040 arch, W25Q080 flash, USB comms (see `tech_docs/BigTree Controller/bigtree_pico_klipper.md`)
- [ ] **Install Klipper + Moonraker on Pi** (MainsailOS or manual install on headless Pi)
- [ ] **Write minimal `printer.cfg`** using `[manual_stepper]` for single-axis control
- [ ] **Test:** Send G-code from Pi, confirm stepper moves
- [ ] **Configure TMC2209 UART** — set run_current, stealthchop threshold
- [ ] **Set up Pi400 as HMI** — connect to same network, access Mainsail/Fluidd web UI, configure SSH to headless Pi

### 2. RTDE Bridge Daemon (Pi)
- [ ] **Install `ur_rtde` library** on Pi (C++ with Python bindings, or pure Python fallback if ARM build issues)
- [ ] **Write bridge daemon** that:
  - Connects to UR30 via RTDE on port 30004
  - Subscribes to relevant output registers (target TCP speed, digital outputs, general-purpose registers)
  - Translates extrusion commands to Klipper G-code
  - Sends commands to Klipper via Unix socket (`/tmp/klippy_uds`) — lowest latency path
- [ ] **Define register allocation:** Map UR30 general-purpose registers to extrusion parameters (speed, enable, direction, etc.)
- [ ] **Write corresponding URScript program** that writes extrusion commands to RTDE input registers

### 3. Bidirectional Feedback
- [ ] **Implement status feedback** from Klipper → RTDE bridge → UR30
  - Stepper position/velocity via Klipper object subscriptions
  - Fault/error status
- [ ] **Stretch: Stallguard torque feedback**
  - BTT Pico TMC2209 supports Stallguard4 via DIAG pins (requires jumper install on board)
  - Read `sg_result` via Klipper's `register_remote_method` callback
  - Push torque data upstream through RTDE registers to URScript

---

## Open Investigation Items

- [ ] **Latency characterization** — once chain is working, measure actual end-to-end latency (estimated 5–20ms). If predictable, implement G-code timeshifting using Klipper's lookahead buffer (~100ms)
- [ ] **Network switch selection** — any gigabit switch works, but verify UR30 controller ethernet port availability
- [ ] **UR communication protocol deep-dive** — RTDE is primary, but evaluate if Dashboard Server (port 29999) is useful for supplementary control (program start/stop/pause)
- [ ] **URCap feasibility** (stretch goal) — Java-based SDK, would give a teach pendant UI. Not needed for MVP.
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
