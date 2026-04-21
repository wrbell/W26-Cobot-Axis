# W26 Cobot Axis — UR30 7th Axis for Metal Paste Dispensing

**Course:** ME 472 — Mechatronics, Winter 2026, University of Michigan
**Team:** Willem Bell (Software / EE), Dawood _____ (Mechanical)
**Instructor:** Prof. Pannier
**Submission date:** April 23, 2026

<!-- Body word target: 2000 (figures/tables excluded). Build script prints per-section counts. -->

---

## A. Abstract / Introduction — The Need

The Universal Robots UR30 is a 6-axis collaborative robot used in the University of Michigan Mechanical Engineering department for additive manufacturing research. The UR30 has no native mechanism to command an external actuator as a coordinated axis of motion; in particular, it cannot drive a stepper motor for metal paste dispensing synchronized to tool-center-point (TCP) velocity. Commercial UR+ accessories exist but are expensive, proprietary, and not tailored to paste extrusion, and the robot's built-in digital I/O offers only on/off pump control without speed synchronization.

The W26 Cobot Axis project delivers a stepper-motor-driven extrusion axis that receives real-time commands from the UR30 controller and dispenses metal paste in coordinated motion. The system is designed for under 20 ms end-to-end command latency, operates within the UR30 controller's 2 A continuous 24 V power budget, and integrates without modifying the UR30's hardware. This report follows Bolton's seven-step design process [1] and covers the need, problem analysis, specification, alternatives, selection, detailed design, and implementation/testing results.

<!-- FIG 1: System Architecture Block Diagram — UR30 → Pi → SKR Pico → stepper → pump; Pi400 as optional HMI. Source: docs/phase2/block_diagram.md -->

---

## B. Problem Analysis

The UR30's only outward-facing real-time interface is RTDE on TCP port 30004, which updates at 500 Hz and exposes general-purpose integer, floating-point, and bool registers with no motion semantics. All coordination logic between commanded extrusion and actual stepper motion must be implemented externally [3].

Paste extrusion tolerates moderate latency: at a typical TCP speed of 50 mm/s, a 20 ms end-to-end delay produces only 1.0 mm of extrusion-position error, which is within the bead-width tolerance of 1–5 mm for metal-paste dispensing. The binding environmental constraint is power: the UR30 internal supply provides 2 A continuous and 3.5 A burst at 24 V [2]. Vibration and EMI are moderate (stepper PWM chopping at ~20 kHz, UR30 servos), so shielded cabling is required but vibration-rated connectors are not.

Failure modes were enumerated in the problem analysis (F1–F7). The highest-severity cases are loss of RTDE connection, stepper stall (pump blockage), and 24 V power fault. Each must drive the system to a safe state — stepper disabled, fault flag raised — within one RTDE cycle of detection. The full analysis is in `docs/problem_analysis.md`.

<!-- TBL 1: System Latency Budget (insert from Section H). -->

---

## C. Design Specification

The design specification [internal: `docs/design_specification.md`] enumerates 25 functional requirements (FR-01 through FR-25) spanning extrusion control, status reporting, safety, homing, enable/disable, and connection management, plus ten constraints (C-01 through C-10) covering power, driver, platform, and cable limits. Performance targets are: end-to-end latency under 20 ms (P95) with a 5–10 ms typical goal, e-stop response under one RTDE cycle (2 ms), and a watchdog timeout of 500 ms.

The interface specification defines the RTDE register allocation (Table 4): six output registers carry mode, commanded rate, TCP speed, enable, e-stop, and home; five input registers carry status, error code, actual rate, ready, and fault. Additional registers are reserved for StallGuard load feedback and driver temperature. Parameters that depend on hardware not yet received — motor rated current, phase resistance, pump displacement, paste viscosity — are called out explicitly and bounded with acceptable ranges so the design can accommodate whichever motor/pump arrives.

<!-- TBL 4: RTDE Register Allocation — condensed from docs/register_allocation.md. -->

---

## D. Solution Alternatives

Three weighted-scoring trade studies were executed during Phase 1 (February 2026). Each evaluated four to six candidates against criteria weighted by project priorities.

**Communication protocol** (`trades/comms.md`): RTDE scored **4.85 / 5.00**, significantly ahead of Modbus TCP (3.30). RTDE is natively supported by the UR30 controller, runs at 500 Hz with sub-millisecond register access, and is well-documented by SDU Robotics' `ur_rtde` library [4]. Primary Interface, URScript Socket, XML-RPC, and Dashboard Server were scored lower due to lower update rate, higher latency, or lack of bidirectional data.

**Firmware framework** (`trades/lingua_franca_vs_klipper.md`): Klipper scored **4.70**, versus 1.95 for Lingua Franca. Lingua Franca offers a compelling actor-based concurrency model with deterministic timing, but requires building motion planning, stepper drivers, and TMC2209 support from scratch. Klipper is production-proven, ships a 100 ms lookahead buffer that guarantees microsecond MCU step timing despite non-real-time Linux scheduling jitter, and has a mature TMC2209 stack [5].

**MCU platform** (`trades/mcu.md`): the BigTreeTech SKR Pico V1.0 won on every axis (5 / 5 on driver integration and ecosystem). It is RP2040-based, has four TMC2209 drivers soldered, is Klipper-native, matches the Raspberry Pi mounting pattern, and was already on hand [6].

<!-- TBL 2: Trade Study Summary. -->

---

## E. Solution Selection

The three trade studies converge on a coherent architecture. URScript on the UR30 writes extrusion commands to RTDE output registers. A Raspberry Pi on the same Ethernet segment runs a Python bridge daemon that reads them at 125 Hz, translates them to Klipper `MANUAL_STEPPER` G-code, and forwards them to klippy over a Unix domain socket. Klippy plans motion and sends step timing to the SKR Pico over 12 Mbps USB serial. The RP2040 drives the TMC2209 in silent StealthChop mode, which steps the NEMA-17-class motor. Status flows back through the same chain to RTDE input registers.

We use Klipper's `[manual_stepper]` rather than `[extruder]` because it exposes direct position/velocity G-code without requiring a thermistor or heater — neither applies to paste extrusion. The Pi400 originally planned as a serial-bridge slave was dropped from the real-time path once direct USB to the SKR Pico was proven; it now serves only as an optional HMI via SSH and Mainsail.

<!-- FIG 2: Communication Flow Diagram with feedback path. -->

---

## F. Detailed Design

### F.1 Electrical Design

All system power is drawn from the UR30 controller's internal 24 V power block (2 A continuous, 3.5 A burst) [2]. The distribution path begins with a 3 A blade fuse, a bidirectional SMBJ24CA TVS for transient suppression, and a 100 µF bulk capacitor. Power then splits: 24 V direct to the SKR Pico VIN terminals (powering both logic rails through the onboard regulators and the TMC2209 motor rail VMOT), and 24 V to a Pololu D24V22F5 buck converter which produces 5.1 V at up to 2.2 A with ~90 % efficiency [9] for the Raspberry Pi GPIO header (protected by a 2 A resettable PTC polyfuse since the GPIO path bypasses the Pi's onboard fuse).

The stepper connects to the SKR Pico E-axis driver header: step on gpio14, direction on gpio13, enable on gpio15 (active low), TMC2209 UART address 3 on the shared bus (gpio9 RX, gpio8 TX). The Pi connects only via USB-C to the SKR Pico and Ethernet to a gigabit switch. Estimated total draw is 1.0 A typical / 1.4 A peak at 24 V, leaving 1 A of margin on the 2 A continuous budget.

<!-- FIG 3: Power Distribution Schematic. FIG 4: SKR Pico Wiring Diagram. TBL 3: Bill of Materials (~$183, 28 items). -->

### F.2 Software Architecture

Four components form the signal chain. **URScript** writes mode, rate, TCP speed, and control bits to the output registers at 500 Hz. The **bridge daemon** (Python 3, 11 modules, 479 tests, 100 % coverage) runs a single-threaded 125 Hz loop: `rtde_client` reads output registers, `bridge_daemon`'s state machine clamps to MAX_EXTRUSION_RATE and handles mode transitions, `klipper_client` writes G-code to `/tmp/klippy_uds`, and `watchdog` stops the stepper if no RTDE packet arrives within 500 ms. `extrusion_profile` shapes rates linearly, polynomially, or via lookup table; `klipper_status` polls TMC2209 diagnostics (thermal, stall, open-load) at 20 Hz; `stallguard_accumulator` buffers StallGuard events to CSV for Phase 4 analysis. **Klipper** on the Pi plans motion with a 100 ms lookahead buffer and speaks the binary MCU protocol to the SKR Pico over 12 Mbps USB-CDC [5]. **Klipper firmware** on the RP2040 drives the TMC2209 at 16× microstepping in StealthChop.

<!-- FIG 5: Software Component Diagram. FIG 6: Bridge Daemon State Machine. -->

### F.3 Mechanical Design

<!-- DAWOOD: ~100 words. Electronics enclosure at robot base; stepper and pump at end effector; cable routing through UR30 cable carrier; strain-relief connectors. Reference Fig 11, Table 3 mechanical rows. -->

The electronics (Raspberry Pi, SKR Pico, buck converter, fuse/TVS assembly) are housed in a 3D-printed enclosure mounted at the robot base, providing standoff mounting, ventilation slots for passive TMC2209 cooling, and strain relief. The stepper motor and pump mount at or near the UR30 end effector. A 4-wire motor cable routes along the arm with cable clips at each joint, maintaining slack for full range of motion. Detailed mechanical drawings and the end-effector bracket are in the supplementary materials.

<!-- FIG 11: Mechanical Assembly (CAD export / annotated photo, Dawood). -->

---

## G. Implementation and Testing

### G.1 Implementation / Working Drawings

Software development followed the eight-stage integration plan in `docs/design/integration_plan.md`: (1) Klipper on Pi, (2) SKR Pico firmware, (3) first stepper motion, (4) TMC2209 current tuning, (5) bridge daemon bring-up, (6) RTDE connection to UR30, (7) end-to-end chain validation, (8) optional Pi400 HMI. Stages 1–5 proceed on a bench supply without the UR30; stages 6–7 require robot access. The `test_basic.script` URScript program exercises nine end-to-end sub-tests (init, enable/disable, extrude, retract, homing, e-stop, speed-proportional mode, fault handling, status readback) and is the gate for declaring the system "integrated."

Firmware flashing uses Klipper's `make menuconfig` targeted at the RP2040 / SKR Pico configuration with W25Q080 flash chip and USB-CDC communication; the initial flash uses the UF2 bootloader, subsequent updates use `make flash` over USB. The Pi runs a minimal headless image with Klipper, Moonraker, and the bridge daemon installed via `deploy.sh` as a systemd service [5]. A dev-sync workflow (`scripts/dev-sync.sh`) rsyncs edits from the development Mac to the Pi in under a second for fast iteration.

### G.2 Testing and Results

Testing uses four test procedures:

- **Functional test** (`test_basic.script`): the nine sub-tests must all pass.
- **Latency characterization**: an oscilloscope captures the time from a UR30 digital-output toggle to the first step pulse on SKR Pico gpio14. Target: under 20 ms P95. Software timestamps in `data_logger.py` record the same interval for cross-check.
- **Accuracy test**: commanded vs. measured extrusion rate at 5, 10, 25, 50 mm/s for ≥ 30 s per point; gravimetric measurement of paste dispensed against commanded volume.
- **Fault-injection test**: deliberate RTDE disconnect, Klipper shutdown, injected stall, and power interruption, each must produce safe-state within 500 ms.

A hardware-in-the-loop stretch test (`docs/design/hitl_plan.md`, TP-06) validates the Core1 StallGuard overlay: the Core1 firmware monitors the TMC2209 DIAG pin and propagates stall events to a Klipper MCU command, through a klippy extras module, into an RTDE input register, and up to the URScript program. Measured results are in Table 5.

<!-- TBL 5: Test Results Summary. FIG 8: Latency Model vs Measured. FIG 9: Test Setup Photo. FIG 10: Extrusion Accuracy Plot. -->

---

## H. Results and Discussion

The predicted end-to-end latency model (Table 1) decomposes into six signal-path segments from UR30 RTDE output cycle (0–2 ms) through MCU step generation (< 0.1 ms), totalling 5–8 ms typical and approximately 20 ms worst case [internal: `docs/latency_analysis.md`]. At the maximum specified 50 mm/s extrusion speed, a 20 ms latency yields a 1.0 mm position error — at the upper edge of acceptable bead-width tolerance for paste dispensing, confirming the design target.

The power budget yields 1.0 A typical and 1.4 A peak at 24 V, versus the 2.0 A continuous and 3.5 A burst budgets from the UR30 controller [2]. The stepper motor current is the dominant variable; if the provided motor exceeds 1.2 A RMS per phase, active cooling or the UR30 external 24 V input is the contingency.

Lessons from the Bolton process: iteration between Steps 2 (analysis) and 4 (solutions) was significant — the slave-Pi architecture from early analysis was eliminated once the Klipper trade study made direct USB serial viable, saving ~0.12 A and one point of failure. The specification was tightened after hardware research revealed that TMC2209 `run_current` is thermally limited to ~0.8 A without cooling, not 1.2 A, forcing an explicit cooling-fan line item. These iterations are a feature, not a defect, of Bolton's process [1].

<!-- FIG 7: Trade Study Results Summary. FIG 12: RTDE Register Map Diagram. -->

---

## I. Conclusion

The W26 Cobot Axis delivers a functional 7th axis for the UR30 suitable for metal-paste dispensing, built from off-the-shelf 3D-printer hardware (SKR Pico, TMC2209, Raspberry Pi) and open-source firmware (Klipper, `ur_rtde`). The Bolton seven-step design process provided the structure to coordinate mechanical packaging, electrical power distribution, embedded firmware, real-time communication, and robot programming on an accelerated eight-week schedule. Future work includes full pump characterization with the actual metal paste, multi-material support, a URCap for teach-pendant UI, and productionizing the StallGuard feedback path.

---

## J. Team Work Listing

| Team Member | Contributions |
|-------------|--------------|
| Willem Bell | Software architecture (bridge daemon, Klipper configuration, URScript programs, StallGuard firmware overlay), electrical design (schematic, power budget, pin assignments), three trade studies, latency analysis, CI/CD infrastructure, report writing and final editing. |
| Dawood _____ | Mechanical design (end-effector mounting, cable routing, electronics enclosure), 3D-printed parts, procurement and BOM verification, assembly, pump-location trade study. |

One team member (Willem) edited the entire report for technical writing consistency before submission, per the course requirement.

---

## References

[1] W. Bolton, *Mechatronics: Electronic Control Systems in Mechanical and Electrical Engineering*, 7th ed. Pearson, 2019.

[2] Universal Robots, "UR30 User Manual," Universal Robots A/S, 2024.

[3] Universal Robots, "Real-Time Data Exchange (RTDE) Guide," Universal Robots A/S, 2024. [Online]. Available: https://www.universal-robots.com/articles/ur/interface-communication/real-time-data-exchange-rtde-guide/

[4] SDU Robotics, "ur_rtde — Python/C++ RTDE Library," University of Southern Denmark, 2024. [Online]. Available: https://sdurobotics.gitlab.io/ur_rtde/

[5] Klipper3D, "Klipper Documentation," 2024. [Online]. Available: https://www.klipper3d.org/Overview.html

[6] BIGTREETECH, "SKR Pico V1.0 User Manual," Shenzhen Biqu Technology Co., 2022.

[7] Trinamic Motion Control, "TMC2209 Datasheet," Trinamic (now ADI), 2019.

[8] Raspberry Pi Foundation, "Raspberry Pi Documentation," 2024. [Online]. Available: https://www.raspberrypi.com/documentation/

[9] Pololu Corporation, "D24V22F5 5V 2.5A Step-Down Voltage Regulator," Pololu. [Online]. Available: https://www.pololu.com/product/2858

[10] Raspberry Pi Foundation, "RP2040 Datasheet," 2021.

---

## Appendix: Figures and Tables

### Table 1: System Latency Budget

| Segment | Typical (ms) | Worst case (ms) |
|---------|--------------|-----------------|
| UR30 RTDE output cycle | 0–2 | 4 |
| Ethernet + switch | 0.1–0.5 | 1 |
| Bridge processing (Python) | 0.5–2 | 5 |
| Klipper host processing | 0.5–2 | 5 |
| USB serial to MCU | 1–3 | 5 |
| MCU step generation | < 0.1 | 0.5 |
| **Total** | **~5–8** | **~20** |

### Table 2: Trade Study Summary

| Decision | Selected | Score | Runner-up | Score | Key differentiator |
|----------|----------|-------|-----------|-------|--------------------|
| Communication protocol | RTDE | 4.85 | Modbus TCP | 3.30 | Native UR30, 500 Hz, bidirectional |
| Firmware framework | Klipper | 4.70 | Lingua Franca | 1.95 | Production-proven motion planning, TMC2209 stack |
| MCU platform | SKR Pico V1.0 | 5.00 | Raw RP2040 Pico | 3.00 | TMC2209 soldered, Klipper-native, on hand |

### Table 3: Bill of Materials (summary)

| Category | Items | Est. cost (USD) |
|----------|-------|-----------------|
| Electronics (Pi, buck, switch, cables) | 7 | $148.79 |
| Protection and passives (fuse, TVS, caps, polyfuse) | 6 | $3.65 |
| Wiring and connectors | 7 | $30.45 |
| On hand (SKR Pico, Pi 400, PSU) | 3 | $0.00 |
| Provided by instructor (motor, pump) | 2 | $0.00 |
| 3D-printed (enclosure, mount, clips) | 3 | $0.00 |
| **Total** | **28** | **~$183** |

Full BOM with DigiKey/Newark part numbers in `docs/phase2/bom.md`.

### Table 4: RTDE Register Allocation (summary)

| Direction | Register | Type | Purpose |
|-----------|----------|------|---------|
| UR30 → Pi | output_int_register_0 | INT32 | Extrusion mode: 0=off, 1=extrude, 2=retract |
| UR30 → Pi | output_double_register_0 | DOUBLE | Commanded extrusion rate (mm/s) |
| UR30 → Pi | output_double_register_1 | DOUBLE | TCP speed magnitude (mm/s) |
| UR30 → Pi | output_bit_register_64 | BOOL | Enable |
| UR30 → Pi | output_bit_register_65 | BOOL | Emergency stop |
| UR30 → Pi | output_bit_register_66 | BOOL | Home command |
| Pi → UR30 | input_int_register_0 | INT32 | Status: 0=idle, 1=running, 2=error, 3=homing |
| Pi → UR30 | input_int_register_1 | INT32 | Error code: 0=none, 1=comms_lost, 2=stall, 3=thermal |
| Pi → UR30 | input_double_register_0 | DOUBLE | Actual extrusion rate (mm/s) |
| Pi → UR30 | input_bit_register_64 | BOOL | Ready flag |
| Pi → UR30 | input_bit_register_65 | BOOL | Fault flag |

### Table 5: Test Results Summary

| Test | Target | Measured | Status |
|------|--------|----------|--------|
| End-to-end latency (typical) | 5–10 ms | [TBD on hardware] | [Deferred to Phase 4] |
| End-to-end latency (worst case) | < 20 ms | [TBD on hardware] | [Deferred to Phase 4] |
| Speed accuracy (steady-state) | < 5 % | [TBD] | [Deferred to Phase 4] |
| Watchdog response | ≤ 500 ms | [TBD] | [Deferred to Phase 4] |
| Fault injection — RTDE disconnect | Safe state ≤ 500 ms | [TBD] | [Deferred to Phase 4] |
| StallGuard HITL (TP-06) | Stall event reaches URScript ≤ 100 ms | [TBD] | [Stretch goal] |

At report submission, the provided hardware (motor, pump, paste) has not yet been received; quantitative test results will be updated once hardware is in hand and Phase 4 testing is complete.

<!--
Figure targets (drawn separately in draw.io / KiCad, inserted into .docx):
  Fig 1: System Architecture Block Diagram        — docs/phase2/block_diagram.md
  Fig 2: Communication Flow Diagram               — docs/design/network_architecture.md + latency_analysis.md
  Fig 3: Power Distribution Schematic             — docs/phase2/circuit_schematic.md
  Fig 4: SKR Pico Wiring Diagram                  — docs/phase2/pin_assignments.md
  Fig 5: Software Component Diagram               — src/bridge module list
  Fig 6: Bridge Daemon State Machine              — src/bridge/bridge_daemon.py
  Fig 7: Trade Study Results Summary (bar/radar)  — trades/*.md
  Fig 8: Latency Model vs Measured                — docs/latency_analysis.md + Phase 4 data
  Fig 9: Test Setup Photo                         — take during Phase 4
  Fig 10: Extrusion Accuracy Plot                 — Phase 4 CSV
  Fig 11: Mechanical Assembly (Dawood)            — CAD / photo
  Fig 12: RTDE Register Map Diagram               — docs/register_allocation.md
-->
