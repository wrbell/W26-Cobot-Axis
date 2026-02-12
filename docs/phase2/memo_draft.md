# Phase 2 Memo — Draft Text

**For:** Phase 2 submission (PDF, ≤ 5 pages, Microsoft Word)
**Project:** W26 Cobot Axis — UR30 7th Axis for Metal Paste Dispensing
**Course:** ME 472 — Mechatronics, Winter 2026, University of Michigan
**Team:** Willem (Software/EE), Dawood (Mechanical)
**Deadline:** Mar 1, 2026
**Status:** Rough draft — section-by-section text ready to paste into Word

---

## Header (Top of Page 1)

**TO:** Prof. Pannier
**FROM:** Willem _____, Dawood _____
**DATE:** March 1, 2026
**RE:** W26 Cobot Axis — Phase 2 Design Memo

---

## Section 1: Introduction (~150 words)

The Universal Robots UR30 is a 6-axis collaborative robot used in the Mechanical Engineering department for additive manufacturing research with metal pastes. The UR30 lacks a native extrusion axis — dispensing metal paste requires an external stepper motor driving a pump, synchronized with the robot's motion in real time.

The W26 Cobot Axis project delivers a stepper motor driver that functions as a virtual 7th axis of the UR30. The system receives extrusion commands from the UR30 via the Real-Time Data Exchange (RTDE) protocol, translates them into motion commands, and drives a stepper motor through a dedicated microcontroller board. Status feedback (speed, fault conditions) flows back to the robot controller so that the URScript program can react to pump state.

The design targets less than 20 ms end-to-end command latency and operates within the UR30's 2A continuous power budget at 24V. The motor, pump, and metal paste will be provided by the instructor; specific mechanical parameters will be characterized upon receipt.

---

## Section 2: System Architecture (~200 words) + Figure 1

The system follows a four-node signal chain, shown in Figure 1.

**UR30 Robot Controller → Raspberry Pi:** The UR30's teach pendant runs a URScript program that writes extrusion commands (mode, rate, enable, e-stop) to six RTDE output registers at 500 Hz. A Raspberry Pi on the same Ethernet network runs a Python bridge daemon that reads these registers over TCP/IP (port 30004) at 125 Hz.

**Raspberry Pi → SKR Pico:** The bridge daemon translates RTDE register values into Klipper G-code commands (e.g., `MANUAL_STEPPER STEPPER=pump MOVE=... SPEED=...`) and sends them to the Klipper host process (klippy) via a Unix domain socket. Klippy plans the motion trajectory and transmits binary step-timing commands to the SKR Pico microcontroller over USB serial at 12 Mbps.

**SKR Pico → Stepper Motor → Pump:** The RP2040 microcontroller on the SKR Pico generates precisely timed step and direction pulses for the TMC2209 stepper driver, which drives the NEMA 17 motor in silent StealthChop mode at 24V. The motor shaft couples to the pump to dispense metal paste.

**Feedback path:** The TMC2209 reports driver status (stall, thermal, open-load) back through the same chain to the UR30 via five RTDE input registers. An optional Raspberry Pi 400 provides SSH access and a Mainsail web dashboard for monitoring but is not in the real-time control loop.

---

## Section 3: Trade Study Results (~200 words) + Table 1

Three trade studies were conducted using weighted scoring matrices to select key system components. Full scoring details are documented in the project repository.

**Communication Protocol (Table 1, row 1):** RTDE scored 4.85/5.00, significantly outperforming the runner-up Modbus TCP (3.30). RTDE is natively supported by the UR30 controller, operates at 500 Hz with sub-millisecond register access, provides bidirectional data exchange, and is well-supported by the open-source `ur_rtde` Python library. Alternative protocols (Primary Interface, XML-RPC, Dashboard Server) were evaluated and scored lower due to latency, complexity, or limited data throughput.

**Software/Firmware Stack (Table 1, row 2):** Klipper scored 4.70 versus 1.95 for Lingua Franca. While Lingua Franca offers a compelling actor-based concurrency model — and was suggested during Phase 1 review — Klipper provides production-proven motion planning, a pre-built TMC2209 driver stack, real-time step generation via a 100 ms lookahead buffer, and an active community. The development risk of building motor control from scratch in Lingua Franca was judged unacceptable given the 8-week implementation timeline.

**MCU Platform (Table 1, row 3):** The BigTreeTech SKR Pico V1.0 was selected. It is already on hand, integrates four TMC2209 drivers (soldered), runs Klipper natively on its RP2040 MCU, and matches the Raspberry Pi's mounting hole pattern.

*See Table 1 for the summary comparison matrix.*

---

## Section 4: Electrical Design (~300 words) + Figure 2, Table 2

### 4a. Circuit Schematic (Figure 2)

All system power is drawn from the UR30 controller box's internal 24V power block, which provides 2A continuous and 3.5A burst current. The power path begins with a 3A blade fuse for overcurrent protection and a bidirectional TVS diode (SMBJ24CA) for transient suppression, followed by a 100 µF bulk capacitor for input smoothing.

From the distribution point, power splits into two branches. The first branch supplies 24V directly to the SKR Pico's VIN screw terminals, powering both the RP2040 (via the onboard 5V/3.3V regulators) and the TMC2209 motor supply (VMOT). The second branch feeds a Pololu D24V22F5 buck converter, which steps 24V down to 5.0V at up to 2.2A with approximately 90% efficiency. The buck converter output passes through a 2A resettable PTC polyfuse before reaching the Raspberry Pi's GPIO header (pins 2 and 6), providing overcurrent protection since GPIO-header power bypasses the Pi's onboard fuse.

Signal connections include Ethernet (Cat5e, UR30 and Pi to a gigabit switch) for RTDE, USB (Pi to SKR Pico) for Klipper serial communication, and a 4-wire cable from the SKR Pico's E-axis motor header to the stepper motor.

### 4b. Pin Assignments and Power Budget (Table 2, Table 5)

The stepper motor uses the SKR Pico's E-axis driver slot: step on gpio14, direction on gpio13, enable on gpio15 (active low), and TMC2209 UART at address 3 on the shared bus (gpio9 RX, gpio8 TX). The Pi connects via USB serial and Ethernet only — no GPIO signal lines are needed.

Table 2 shows the power budget. At typical operating conditions, the system draws approximately 1.0A from the 24V supply, leaving 1.0A of margin against the 2.0A continuous limit. Peak draw during stepper acceleration is estimated at 1.6A, well within the 3.5A burst rating. Motor current values are placeholders pending hardware receipt; the initial Klipper configuration uses a conservative 0.58A run current.

---

## Section 5: Mechanical Concept (~150 words) + Figure 4

*[Dawood writes this section]*

The electronics (Raspberry Pi, SKR Pico, buck converter, and fuse assembly) are housed in a 3D-printed enclosure mounted at the robot's base. The enclosure provides:
- Secure mounting for all circuit boards using standoffs
- Ventilation slots for passive cooling
- Strain relief for power and Ethernet cables
- Access ports for USB and Ethernet connections

The stepper motor and pump assembly mount at or near the UR30's end effector. A 4-wire motor cable routes along the robot arm with cable clips at each joint, maintaining sufficient slack for full range of motion. The cable uses strain-relief connectors at both ends.

[Placeholder for Dawood's sketches — Figure 3 (physical layout) and Figure 4 (mechanical concept drawings)]

---

## Section 6: Engineering Analysis (~200 words) + Table 3

**Latency Analysis:** End-to-end command latency from UR30 register write to stepper motion onset is estimated at 5–10 ms typical and up to 20 ms worst case (Table 3). The dominant contributors are Ethernet transport (~0.5 ms), Python bridge processing (~1 ms), Klipper host processing (~1 ms), and USB serial to the MCU (~2 ms). At the maximum extrusion speed of 50 mm/s, 20 ms of latency produces a position error of 1.0 mm — within the acceptable range for metal paste dispensing where bead widths are typically 1–5 mm. Full analysis is documented in the project repository.

**Power Analysis:** Total system draw is approximately 1.0A typical and 1.6A peak at 24V (Table 2), within the UR30's 2.0A continuous budget with adequate margin. If the provided motor requires higher current, the UR30's external power input option (6A) serves as a contingency.

**Motor and Pump Analysis:** Torque requirements, flow rate characterization, and acceleration limits will be determined in Phase 3 upon receipt of the motor and pump hardware. The design accommodates a NEMA 17-class motor with up to 1.2A RMS per phase. The Klipper configuration starts at a conservative 0.58A and can be tuned upward based on measured performance.

**Communication Throughput:** RTDE provides a 500 Hz update cycle (2 ms period). The bridge daemon processes commands at 125 Hz. Klipper's 100 ms lookahead buffer pre-queues step commands on the MCU, ensuring microsecond-precision timing despite the non-real-time Linux host. No communication bottleneck exists at expected extrusion rates.

---

## Section 7: Bill of Materials (~100 words) + Table 4

Table 4 lists all components required for the system. The total estimated cost for purchasable items is approximately $183, excluding items already on hand (SKR Pico, Pi 400) and those provided by the instructor (stepper motor, pump).

Components should be ordered from UMich-contracted suppliers (DigiKey, Newark). Before ordering, we recommend checking the ME472 lab inventory for the Raspberry Pi, Ethernet switch, and cables, which may already be available. 3D-printed components (electronics enclosure, motor mount, cable clips) will be fabricated using the instructor's printer; Dawood will provide designs once the motor and pump dimensions are known.

The SKR Pico V1.0 is already in the team's possession and does not need to be purchased.

---

## Section 8: Next Steps (~100 words)

**Phase 3 (Mar 2–22) — Build and Integration:**
- Week 9 (Spring Break): Flash Klipper firmware onto SKR Pico, install Klipper and Moonraker on Pi, verify first stepper motion on the bench
- Week 10: Deploy RTDE bridge daemon, load URScript onto UR30, perform first end-to-end command test
- Week 11: Full signal chain integration, mechanical assembly, tuning, progress memo to instructor

**Phase 4 (Mar 23 – Apr 5) — Testing:**
- End-to-end functional testing, latency measurement with oscilloscope, accuracy characterization
- Fault handling verification (connection loss, motor stall, power interruption)
- Target: all testing complete by March 31

We request feedback on the BOM for purchasing and a go/no-go decision on the overall design approach.

---

## Tables (for Word document)

### Table 1: Trade Study Summary

| Decision | Selected | Score | Runner-Up | Score | Key Differentiator |
|----------|----------|-------|-----------|-------|--------------------|
| Comm. Protocol | RTDE | 4.85 | Modbus TCP | 3.30 | Native UR30, 500 Hz, bidirectional |
| Software Stack | Klipper | 4.70 | Lingua Franca | 1.95 | Proven motion planning, TMC2209 drivers |
| MCU Platform | SKR Pico | — | Custom RP2040 | — | On hand, TMC2209 soldered, Klipper-native |

### Table 2: Power Budget

| Device | Idle (A@24V) | Typical (A@24V) | Peak (A@24V) | Notes |
|--------|-------------|-----------------|-------------|-------|
| Pi 4B (via buck @ 90% eff.) | 0.15 | 0.35 | 0.45 | 1.5A design @ 5.1V |
| SKR Pico (logic) | 0.05 | 0.08 | 0.10 | RP2040 + TMC2209 quiescent |
| Stepper motor | 0.10 | 0.50 | 1.00 | [TBD] Placeholder NEMA 17 |
| Fan (optional) | 0.00 | 0.04 | 0.08 | If TMC2209 cooling needed |
| **Total** | **0.30** | **~0.97** | **~1.63** | **Budget: 2.0A / 3.5A burst** |

### Table 3: Latency Budget

| Segment | Typical (ms) | Worst Case (ms) |
|---------|-------------|-----------------|
| UR30 RTDE output cycle | 0–2 | 4 |
| Ethernet + switch | 0.1–0.5 | 1 |
| Bridge processing (Python) | 0.5–2 | 5 |
| Klipper host processing | 0.5–2 | 5 |
| USB serial to MCU | 1–3 | 5 |
| MCU step generation | <0.1 | 0.5 |
| **Total** | **~5–8** | **~20** |

### Table 4: Bill of Materials

See `docs/phase2/bom.md` for the full BOM with part numbers. Summary:

| Category | Items | Est. Cost |
|----------|-------|-----------|
| Electronics (Pi, buck converter, switch, cables) | 7 | $148.79 |
| Protection and passives (fuse, TVS, caps, polyfuse) | 6 | $3.65 |
| Wiring and connectors | 7 | $30.45 |
| On hand (SKR Pico, Pi 400, PSU) | 3 | $0.00 |
| Provided by instructor (motor, pump) | 2 | $0.00 |
| 3D-printed (enclosure, mount, clips) | 3 | $0.00 |
| **Total** | **28** | **~$183** |

### Table 5: Pin Assignment Summary

| Device | Pin | Signal | Direction | Voltage | Connected To |
|--------|-----|--------|-----------|---------|--------------|
| SKR Pico | gpio14 | E Step | Output | 3.3V | TMC2209 (internal) |
| SKR Pico | gpio13 | E Direction | Output | 3.3V | TMC2209 (internal) |
| SKR Pico | gpio15 | E Enable | Output (act. low) | 3.3V | TMC2209 (internal) |
| SKR Pico | gpio9 | UART RX | Input | 3.3V | TMC2209 shared bus |
| SKR Pico | gpio8 | UART TX | Output | 3.3V | TMC2209 shared bus |
| SKR Pico | VIN | 24V power | Input | 24V | UR30 distribution |
| SKR Pico | USB-C | Klipper serial | Bidir. | USB 2.0 | Pi USB-A |
| Pi 4B | GPIO pin 2 | +5V power | Input | 5.0V | Buck converter out |
| Pi 4B | GPIO pin 6 | GND | — | 0V | GND bus |
| Pi 4B | USB-A | Klipper serial | Bidir. | USB 2.0 | SKR Pico USB-C |
| Pi 4B | Ethernet | RTDE + network | Bidir. | Gigabit | Switch |
| UR30 | Power PWR | +24V | Output | 24V | Blade fuse → dist. |
| UR30 | Power GND | 0V | — | 0V | GND bus |
| UR30 | Ethernet | RTDE | Bidir. | Gigabit | Switch |

---

## Word Formatting Notes

- Use **Word Styles**: Heading 1 for section titles, Heading 2 for subsections, Body Text for paragraphs, Caption for figure/table captions
- All figures embedded (not linked)
- Page margins: 1" all sides (Word default)
- Font: 11pt body text, 10pt for tables and captions
- Figures at ~1/3 page each; tables as compact as possible
- **Total estimated text: ~1,400 words** (well under any word limit)
- **Total pages: 5** (tight but achievable with the layout in `docs/design/phase2_memo_outline.md`)
