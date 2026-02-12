# Final Report Outline -- W26 Cobot Axis

**Due:** Thu Apr 23, 2026, 6:00 PM
**Format:** PDF, Microsoft Word (UMich Office 365, Word Styles), <=2000 words (figures/tables excluded)
**Submission:** Upload PDF + supplementary materials (code, drawings, configs)

---

## 1. Section Outline (Mapped to Bolton's 7 Steps)

### Section A: Abstract / Introduction -- The Need (Bolton Step 1)
**Word budget: ~150 words**

Content:
- The UR30 is a 6-axis collaborative robot used in UMich's manufacturing lab. It has no native support for a 7th axis of motion to drive a pump for metal paste dispensing/extrusion.
- Existing solutions: UR+ ecosystem accessories exist but are expensive, proprietary, and not tailored to paste extrusion. Custom solutions using UR I/O are limited to simple on/off control with no speed synchronization.
- Project objective: design, build, and test a stepper-motor-driven extrusion axis that receives real-time commands from the UR30 controller and delivers synchronized metal paste dispensing.
- Scope statement: the system must achieve end-to-end command latency under 50 ms, support variable extrusion rates, and integrate without modifying the UR30 controller hardware or voiding its warranty.

**ME 472 course topics:** system diagrams (introduction of the overall system concept)

---

### Section B: Problem Analysis (Bolton Step 2)
**Word budget: ~200 words**

Content:
- Reference `docs/problem_analysis.md` for full analysis.
- Environmental constraints: industrial robot cell, 24V power from UR controller power block (2A continuous, 3.5A burst), vibration/EMI from robot servos, cable routing through cable carrier.
- Performance requirements: extrusion rate synchronized to TCP speed, variable rate 0-100%, retraction support, latency acceptable for paste viscosity (not sub-millisecond critical like laser or FDM at high speed).
- Communication constraints: UR30 exposes RTDE at 500 Hz on port 30004; host Pi runs non-RT Linux; Klipper provides real-time step generation on RP2040.
- Failure modes: RTDE connection loss, Klipper communication failure, stepper stall, power interruption. Each must result in safe state (extrusion stops, robot notified).
- Latency budget: ~5-20 ms end-to-end is adequate for paste dispensing (see latency analysis).
- Power budget: total system draw ~1.1A typical at 24V (stepper + Pi + SKR Pico).

**ME 472 course topics:** control systems (identifying feedback requirements), system models (latency model, power budget model), circuits (power constraints)

---

### Section C: Design Specification (Bolton Step 3)
**Word budget: ~150 words**

Content:
- Functional requirements: accept extrusion rate commands from UR30 via RTDE, translate to stepper motion, report status back to UR30.
- Interface specification: RTDE register allocation (command register, rate register, status register, fault register -- reference `docs/register_allocation.md`).
- Performance targets: end-to-end latency < 50 ms, extrusion rate accuracy within 5% of commanded, e-stop response < 100 ms.
- Operating environment: UR30 robot cell, 15-40 C ambient, 24V DC input.
- Physical constraints: electronics must fit within end-effector or base-mount envelope, cabling through UR30 cable carrier.
- Power specification: 24V input from UR controller, 5.1V derived via buck converter for Pi.
- Standards: UR30 safety system takes precedence; 7th axis must not interfere with existing safety functions.

**ME 472 course topics:** signal conditioners (RTDE register mapping as data translation layer), system diagrams (interface specification)

---

### Section D: Solution Alternatives (Bolton Step 4)
**Word budget: ~200 words**

Content -- summarize three completed trade studies:

1. **Firmware/software platform** -- Klipper vs Lingua Franca (reference `trades/lingua_franca_vs_klipper.md`).
   - Klipper: mature 3D-printer firmware, real-time step generation on RP2040, G-code API, active community. Score: 4.70.
   - Lingua Franca: academic reactive framework (UC Berkeley), deterministic timing, but requires custom driver development, no stepper ecosystem. Score: 1.95.

2. **Communication protocol** -- RTDE vs Dashboard Server vs Primary/Secondary Interface vs Modbus TCP (reference `trades/comms.md`).
   - RTDE: 500 Hz bidirectional, structured registers, official UR support, `ur_rtde` Python library. Score: 4.85.
   - Next best (Modbus TCP): 3.30.

3. **MCU platform** -- SKR Pico vs Arduino + CNC Shield vs custom RP2040 board vs Teensy 4.1 (reference `trades/mcu.md`).
   - SKR Pico: RP2040-based, 4x TMC2209 soldered, Klipper-native, compact (85x56 mm), already on hand.

4. **Pump location** -- end effector vs base-mounted vs gantry (Dawood's trade study, if completed).

**ME 472 course topics:** microcontrollers (MCU trade study), electrical actuators (stepper driver selection), control systems (firmware architecture comparison)

---

### Section E: Solution Selection (Bolton Step 5)
**Word budget: ~150 words**

Content:
- Weighted decision matrices used for each trade study (criteria: development time, real-time performance, ecosystem support, cost, risk).
- Selected architecture: UR30 -> RTDE over TCP/IP -> Raspberry Pi (Klipper host + RTDE bridge daemon) -> USB serial -> SKR Pico (RP2040 + TMC2209) -> stepper motor -> pump.
- Rationale: Klipper provides proven real-time step generation and eliminates custom firmware development. RTDE provides the highest-bandwidth bidirectional interface to UR30. SKR Pico is Klipper-native with integrated TMC2209 drivers, minimizing wiring and board count.
- Key design decision: use Klipper `[manual_stepper]` configuration rather than treating the axis as an extruder, giving explicit position/velocity control via G-code.
- Pi400 relegated to optional HMI role; system runs standalone without it.

**ME 472 course topics:** system diagrams (selected architecture block diagram), control systems (closed-loop architecture rationale)

---

### Section F: Detailed Design (Bolton Step 6)
**Word budget: ~400 words**

Content -- three subsections:

**F.1 Electrical Design (~130 words)**
- Power distribution: 24V from UR controller power block -> buck converter (Pololu D24V22F5 or similar) -> 5.1V @ 3A for Pi; 24V direct to SKR Pico VIN for stepper drivers.
- SKR Pico wiring: TMC2209 UART on E-axis driver, stepper motor connections, USB to Pi.
- Pin assignments table (reference pin assignment doc).
- EMI considerations: shielded cables, separation of power and signal runs.

**F.2 Software Architecture (~170 words)**
- Four software components: URScript on UR30, RTDE bridge daemon on Pi, Klipper host on Pi, Klipper firmware on SKR Pico.
- Bridge daemon architecture: main loop reads RTDE registers at 125 Hz, translates command/rate to Klipper G-code (`MANUAL_STEPPER MOVE`), writes status/fault back to RTDE output registers.
- Klipper configuration: `[manual_stepper pump]` with TMC2209 UART, acceleration/velocity limits tuned to pump mechanics.
- Communication flow: URScript writes to output registers -> RTDE -> bridge daemon -> Unix socket -> Klipper -> USB serial -> SKR Pico -> step/dir signals -> TMC2209 -> stepper.
- Error handling: bridge daemon monitors connection health, implements watchdog, sets fault register on any failure, Klipper's native stall detection (if StallGuard implemented).

**F.3 Mechanical Design (~100 words)**
- Mounting solution for electronics enclosure (Dawood's design).
- Cable routing through UR30 cable carrier.
- Pump mounting to end effector or robot base (per location trade study).
- 3D-printed components: mounting brackets, cable guides, enclosure.

**ME 472 course topics:** circuits (power distribution, buck converter, schematic), electrical actuators (stepper motor, TMC2209 driver characteristics -- StealthChop vs SpreadCycle), microcontrollers (RP2040 on SKR Pico, Klipper firmware operation), signal conditioners (RTDE register translation, data type mapping), control systems (bridge daemon feedback loop), system diagrams (software block diagram, communication flow)

---

### Section G: Implementation and Testing (Bolton Step 7 + Phase 3/4 Results)
**Word budget: ~400 words**

Content -- two subsections:

**G.1 Implementation / Working Drawings (~200 words)**
- Firmware flashing: Klipper `make menuconfig` for RP2040, W25Q080 flash chip, USB communication.
- Pi setup: MainsailOS or manual Klipper + Moonraker installation, bridge daemon deployed as systemd service.
- Integration sequence: (1) Klipper + stepper verified standalone, (2) bridge daemon + URSim tested in simulation, (3) full chain with UR30 hardware.
- Calibration procedure: extrusion multiplier calibration (dispense known volume, measure actual vs commanded).
- Reference working drawings in supplementary materials.

**G.2 Testing and Results (~200 words)**
- Test procedures and results for each test category:
  - **Functional test:** UR30 sends extrude command, stepper moves at correct speed. Pass/fail criteria.
  - **Latency characterization:** oscilloscope measurement on step pin relative to RTDE command timestamp. Target: < 50 ms.
  - **Accuracy test:** commanded vs actual extrusion rate/position over a test run. Measured error percentage.
  - **Fault handling:** deliberate RTDE disconnect, stepper stall injection, power interruption. Verify safe state achieved.
  - **Endurance test:** extended continuous run, monitor thermal behavior and reliability.
- Summarize quantitative results (latency measurements, accuracy percentages).
- Note any deviations from specification and root causes.

**ME 472 course topics:** sensors (TMC2209 StallGuard for stall detection, if implemented), control systems (measured closed-loop performance), system models (predicted vs measured latency), microcontrollers (firmware flashing and configuration)

---

### Section H: Results and Discussion
**Word budget: ~200 words**

Content:
- Summary of achieved performance vs design specification targets (latency, accuracy, reliability).
- Comparison of predicted latency model to measured values.
- Discussion of what worked well and what required iteration (Bolton process iteration between steps).
- Limitations: non-RT Linux host jitter, paste-specific calibration needed per pump/material, single-axis only.
- Potential improvements: StallGuard torque feedback (stretch goal status), predictive G-code timeshifting, URCap teach pendant UI.
- Lessons learned about the mechatronics design process and integrating mechanical, electrical, and software subsystems.

**ME 472 course topics:** system models (model validation), control systems (performance evaluation)

---

### Section I: Conclusion
**Word budget: ~100 words**

Content:
- Restate the need and how the design addresses it.
- Key achievement: functional 7th axis for UR30 metal paste dispensing using off-the-shelf 3D printer components and open-source firmware.
- The Bolton design process provided structure for a complex mechatronics integration project spanning mechanical packaging, electrical power distribution, embedded firmware, real-time communication, and robot programming.
- Future work: pump characterization with actual metal paste, multi-material support, integration into production workflows.

---

### Section J: Team Work Listing
**Word budget: ~50 words**

Content:

| Team Member | Contributions |
|-------------|--------------|
| Willem | Software architecture, RTDE bridge daemon, Klipper configuration, URScript programming, electrical design (schematic, power budget, pin assignments), trade studies (firmware, comms, MCU), latency analysis, system integration, report writing and editing |
| Dawood | Mechanical design (end effector mounting, cable routing, enclosure), 3D-printed components, procurement/BOM, assembly, location trade study |

---

**Word count summary:**

| Section | Bolton Step | Words |
|---------|------------|-------|
| A. Abstract / Introduction | Step 1: The Need | ~150 |
| B. Problem Analysis | Step 2: Analysis | ~200 |
| C. Design Specification | Step 3: Specification | ~150 |
| D. Solution Alternatives | Step 4: Possible Solutions | ~200 |
| E. Solution Selection | Step 5: Selection | ~150 |
| F. Detailed Design | Step 6: Detailed Design | ~400 |
| G. Implementation and Testing | Step 7: Working Drawings + Phase 3/4 | ~400 |
| H. Results and Discussion | -- | ~200 |
| I. Conclusion | -- | ~100 |
| J. Team Work Listing | -- | ~50 |
| **Total** | | **~2000** |

---

## 2. Course Topic Mapping

Each ME 472 course topic must appear in at least one report section. This matrix tracks coverage.

| Course Topic | Report Section(s) | Specific Content |
|---|---|---|
| **Control systems** | B, D, E, F, G, H | Feedback loop architecture: UR30 commands -> bridge daemon -> Klipper -> stepper, with status feedback via RTDE. Closed-loop extrusion rate control. Measured vs designed performance. |
| **System diagrams** | A, C, E, F | System architecture block diagram, communication flow diagram, software component diagram, signal flow with feedback paths. |
| **Sensors** | G | TMC2209 StallGuard as stall/torque sensor (stretch goal). If not implemented, discuss as future work in Section H. |
| **Signal conditioners** | C, F | RTDE register mapping as signal conditioning: raw UR30 floating-point register values translated to Klipper G-code commands. Data type conversion, scaling, range checking. |
| **Circuits** | B, F | Power distribution circuit: 24V input, buck converter to 5.1V, SKR Pico VIN. Full schematic. EMI considerations. |
| **Electrical actuators** | D, F | Stepper motor driven by TMC2209 (StealthChop for quiet operation, SpreadCycle for high torque). Current limiting, microstepping configuration. |
| **Microcontrollers** | D, F, G | RP2040 on SKR Pico running Klipper firmware. Firmware flashing process, real-time step generation, USB serial communication with host. |
| **System models** | B, G, H | Latency model (predicted ~8 ms typical end-to-end), power budget model (~1.1A at 24V). Validation against measured values in testing. |

---

## 3. Figures List

Target: 8-12 figures. Figures do not count toward the 2000-word limit.

| # | Figure | Section | Description | Source |
|---|--------|---------|-------------|--------|
| 1 | System Architecture Block Diagram | A, E | Top-level block diagram showing UR30 -> Pi -> SKR Pico -> stepper -> pump, with Pi400 as optional HMI. Show protocols on each link (RTDE, Unix socket, USB serial, STEP/DIR). | Draw new (draw.io or similar) |
| 2 | Communication Flow Diagram | F | Detailed signal flow: URScript writes output registers -> RTDE 125 Hz -> bridge daemon -> Klipper Unix socket -> USB serial -> RP2040 -> TMC2209 -> stepper. Show feedback path (status registers). | Draw new |
| 3 | Power Distribution Schematic | F | Circuit schematic: 24V from UR controller power block -> buck converter -> 5.1V for Pi; 24V -> SKR Pico VIN -> TMC2209 -> motor. Show connector pinouts, fuse/protection. | Draw new (KiCad or similar) |
| 4 | SKR Pico Wiring Diagram | F | Physical wiring diagram showing SKR Pico board with connections: USB to Pi, motor connector to stepper, power input, TMC2209 UART jumper. Reference pin assignment table. | Draw new, overlay on board photo |
| 5 | Software Component Diagram | F | UML-style component diagram: URScript, RTDE bridge daemon (with subcomponents: rtde_client, klipper_client, config, main loop), Klipper host, Klipper MCU firmware. Show interfaces between components. | Draw new |
| 6 | Bridge Daemon State Machine | F | State diagram of bridge daemon: INIT -> CONNECTING -> RUNNING -> FAULT -> RECONNECTING. Show transitions (RTDE connected, Klipper connected, e-stop, connection lost, etc.). | Draw new |
| 7 | Trade Study Results Summary | D | Bar chart or radar chart comparing weighted scores across all three trade studies (firmware, comms, MCU). Visual summary of decision rationale. | Generate from trade study data |
| 8 | Latency Model vs Measured | G, H | Dual bar chart or waterfall diagram: predicted latency per link (from `docs/latency_analysis.md`) vs measured latency (from Phase 4 oscilloscope data). | Generate from test data |
| 9 | Test Setup Photo | G | Annotated photograph of the complete test setup: UR30, Pi, SKR Pico, stepper motor, pump, cabling. Label each component. | Take photo during Phase 3/4 |
| 10 | Extrusion Accuracy Plot | G, H | Time-series plot: commanded extrusion rate vs measured actual rate over a test run. Show error band. | Generate from test data CSV |
| 11 | Mechanical Assembly | F | CAD rendering or annotated photo of mechanical assembly: electronics enclosure, mounting brackets, cable routing through UR30 cable carrier. (Dawood) | CAD export or photo |
| 12 | RTDE Register Map Diagram | C | Visual diagram of RTDE register allocation: input registers (command, rate, config) and output registers (status, fault, actual_rate) with data types and scaling. | Draw new from `docs/register_allocation.md` |

---

## 4. Tables List

Target: 4-6 tables. Tables do not count toward the 2000-word limit.

| # | Table | Section | Content |
|---|-------|---------|---------|
| 1 | System Latency Budget | B, G | Link-by-link latency: UR30-to-Pi (2-5 ms), Pi-to-Klipper (<1 ms), Pi-to-SKR Pico (1-3 ms), SKR Pico-to-stepper (<0.1 ms), total predicted vs measured. |
| 2 | Trade Study Summary | D | Condensed table: each trade study (firmware, comms, MCU), alternatives considered, winning score, runner-up score. One row per trade study. |
| 3 | Bill of Materials | F | Component, quantity, supplier, part number, unit cost, total cost. Include SKR Pico, Pi, buck converter, stepper motor, connectors, enclosure, fasteners. |
| 4 | RTDE Register Allocation | C | Register name, direction (input/output), data type, range, description. Condensed from `docs/register_allocation.md`. |
| 5 | Test Results Summary | G | Test name, pass/fail criteria, measured result, pass/fail status. One row per test (functional, latency, accuracy, fault handling, endurance). |
| 6 | Team Work Listing | J | Team member, contributions. Two rows. |

---

## 5. References List

Minimum references to cite (add more as needed). Use IEEE citation style.

| # | Reference | In-text citation context |
|---|-----------|--------------------------|
| 1 | W. Bolton, *Mechatronics: Electronic Control Systems in Mechanical and Electrical Engineering*, 7th ed. Pearson, 2019. | Bolton's 7-step design process (Sections A-G), course topic framing |
| 2 | Universal Robots, "UR30 User Manual," Universal Robots A/S, 2024. | UR30 specifications, power block ratings, cable carrier specs |
| 3 | Universal Robots, "Real-Time Data Exchange (RTDE) Guide," Universal Robots A/S, 2024. [Online]. Available: https://www.universal-robots.com/articles/ur/interface-communication/real-time-data-exchange-rtde-guide/ | RTDE protocol specification, register types, 500 Hz update rate |
| 4 | SDU Robotics, "ur_rtde -- Python/C++ RTDE Library," University of Southern Denmark, 2024. [Online]. Available: https://sdurobotics.gitlab.io/ur_rtde/ | RTDE Python library used for bridge daemon |
| 5 | Klipper3D, "Klipper Documentation," 2024. [Online]. Available: https://www.klipper3d.org/Overview.html | Klipper firmware architecture, manual_stepper, G-code reference, API protocol |
| 6 | BIGTREETECH, "SKR Pico V1.0 User Manual," Shenzhen Biqu Technology Co., 2022. | SKR Pico hardware specs, pin assignments, TMC2209 integration |
| 7 | Trinamic Motion Control, "TMC2209 Datasheet," Trinamic (now ADI), 2019. | TMC2209 driver specs: StealthChop, SpreadCycle, StallGuard, UART configuration |
| 8 | Raspberry Pi Foundation, "Raspberry Pi Documentation," 2024. [Online]. Available: https://www.raspberrypi.com/documentation/ | Pi hardware specs, power requirements, USB/GPIO |
| 9 | Pololu Corporation, "D24V22F5 5V 2.5A Step-Down Voltage Regulator," Pololu. [Online]. Available: https://www.pololu.com/product/2858 | Buck converter selection for 24V-to-5.1V conversion |
| 10 | Raspberry Pi Foundation, "RP2040 Datasheet," 2021. | RP2040 microcontroller specifications (dual Cortex-M0+, PIO, USB) |

---

## 6. Supplementary Materials

Attach the following with the final report PDF. These are referenced in the report but submitted as separate files.

| Material | File(s) | Description |
|----------|---------|-------------|
| Source code: Bridge daemon | `src/bridge/bridge_daemon.py`, `config.py`, `klipper_client.py`, `rtde_client.py`, `__main__.py` | Complete RTDE-to-Klipper bridge daemon Python package |
| Source code: URScript | `src/urscript/extrusion_control.script` | URScript program for UR30 teach pendant |
| Klipper configuration | `src/klipper/printer.cfg` | Klipper printer configuration for SKR Pico with manual_stepper |
| Trade study: Firmware | `trades/lingua_franca_vs_klipper.md` | Full weighted decision matrix: Klipper vs Lingua Franca |
| Trade study: Communication | `trades/comms.md` | Full weighted decision matrix: RTDE vs alternatives |
| Trade study: MCU | `trades/mcu.md` | Full weighted decision matrix: SKR Pico vs alternatives |
| Problem analysis | `docs/problem_analysis.md` | Bolton Step 2: formal problem analysis |
| Latency analysis | `docs/latency_analysis.md` | End-to-end latency model and analysis |
| Register allocation | `docs/register_allocation.md` | RTDE register map specification |
| Circuit schematic | TBD (KiCad export) | Full electrical schematic (PDF or PNG) |
| Mechanical drawings | TBD (CAD export from Dawood) | 3D-printed component drawings, assembly drawing |
| Wiring diagram | TBD | Physical wiring diagram with pin assignments |
| Test data | TBD (CSV files from Phase 4) | Raw test data: latency measurements, accuracy data, logs |

---

## 7. Writing Assignments

### Willem (Software/EE) -- Primary Author
- **Section A:** Abstract / Introduction (draft + final)
- **Section B:** Problem Analysis (draft + final)
- **Section C:** Design Specification (draft + final)
- **Section D:** Solution Alternatives -- firmware, comms, MCU trade studies (draft + final)
- **Section E:** Solution Selection (draft + final)
- **Section F.1:** Electrical Design (draft + final)
- **Section F.2:** Software Architecture (draft + final)
- **Section G.2:** Testing and Results (draft + final)
- **Section H:** Results and Discussion (draft + final)
- **Section I:** Conclusion (draft + final)
- **All figures** except mechanical (Figs 1-8, 10, 12)
- **All tables** except BOM mechanical items
- **Full report edit** for technical writing consistency (Willem is the designated editor per Phase 3 requirements)
- **References** and in-text citations
- **Word Styles** setup in Word template (Heading 1-3, Caption, Body, Table styles)

### Dawood (Mechanical) -- Contributing Author
- **Section D:** Solution Alternatives -- location trade study paragraph (draft)
- **Section F.3:** Mechanical Design (draft + final)
- **Section G.1:** Implementation -- mechanical assembly paragraph (draft)
- **Fig 9:** Test setup photo (take + annotate)
- **Fig 11:** Mechanical assembly CAD rendering / photo
- **Table 3:** BOM -- mechanical items (3D-printed parts, fasteners, enclosure)
- **Section J:** Team Work Listing -- review Dawood's contributions for accuracy

### Joint
- **Section G.1:** Implementation -- integration sequence (co-authored, as both team members participate in hardware integration)

---

## 8. Timeline (Working Backward from Apr 23)

| Date | Milestone | Owner | Notes |
|------|-----------|-------|-------|
| **Mar 31** | All testing complete | Both | Phase 4 functional target; all test data collected |
| **Apr 1-2** | Compile test data, generate plots | Willem | Figs 8, 10; Table 5 |
| **Apr 3-5** | Draft Sections A-E | Willem | Introduction through Solution Selection (~850 words) |
| **Apr 3-5** | Draft Section F.3, mechanical figures | Dawood | Mechanical design, Fig 11, BOM mechanical items |
| **Apr 6-8** | Draft Sections F.1, F.2 | Willem | Electrical + software detailed design (~300 words) |
| **Apr 6-8** | Draft Section D location trade, G.1 mech assembly | Dawood | Contributing paragraphs |
| **Apr 9-10** | Draft Sections G, H, I | Willem | Implementation, results, conclusion (~700 words) |
| **Apr 11** | **First complete draft** | Willem | All sections assembled in Word, all figures/tables placed |
| **Apr 12-13** | Dawood reviews full draft | Dawood | Check mechanical content accuracy, flag issues |
| **Apr 14-16** | Willem edits full report | Willem | Technical writing edit pass (designated editor per course requirements) |
| **Apr 16** | **Second draft complete** | Willem | Edited for consistency, word count verified <= 2000 |
| **Apr 17-18** | Both review second draft | Both | Final comments, fact-checking, figure quality check |
| **Apr 19-20** | Final revisions | Willem | Incorporate all feedback, finalize Word Styles, check references |
| **Apr 21** | **Final draft complete** | Willem | Word count verified, all figures high-resolution, references complete |
| **Apr 22** | Export PDF, assemble supplementary materials | Willem | PDF export from Word, zip supplementary files |
| **Apr 23 (6 PM)** | **SUBMIT** | Willem | Upload PDF + supplementary materials |
| **Apr 24 (6:30 PM)** | Oral presentation and design defense | Both | Separate preparation track (not covered in this outline) |

### Critical Path

1. **Testing must finish by Mar 31** -- all quantitative data (latency, accuracy, fault handling) needed for Sections G and H.
2. **First complete draft by Apr 11** -- gives 12 days for editing and polish.
3. **Willem is the bottleneck** -- responsible for ~85% of writing. Dawood's contributions (F.3, location trade paragraph, mechanical figures) should be submitted to Willem by Apr 8.
4. **Figures drive the schedule** -- Figs 8, 10 require test data (not available until Apr 1). Figs 1-7, 12 can be drawn in parallel with Phase 3/4 work.
5. **Word count discipline** -- at 2000 words across 10 sections, every sentence must earn its place. Offload detail to figures, tables, and supplementary materials.

---

## Notes

- **Word Styles:** Set up the Word template early (Week 11 or 12) with Heading 1 (sections), Heading 2 (subsections), Body Text, Caption, Table Caption styles. This avoids formatting scrambles at the end.
- **Figure resolution:** Use Word (not Google Docs) per instructor recommendation. Insert figures at final size to avoid resolution loss from resizing. Export source figures at 300 DPI minimum.
- **Simultaneous editing:** Use UMich Office 365 SharePoint for shared editing. Share via umich.edu email addresses.
- **In-text citations:** Use IEEE style: [1], [2], etc. Place citation immediately after the relevant claim.
- **Supplementary materials:** Zip all code, configs, drawings, and trade studies into a single archive. Include a README in the archive listing contents.
