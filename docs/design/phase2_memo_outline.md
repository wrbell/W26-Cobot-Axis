# Phase 2 Memo Outline

**Project:** W26 Cobot Axis -- UR30 7th Axis for Metal Paste Dispensing
**Course:** ME 472, Winter 2026, University of Michigan
**Team:** Willem (Software/EE), Dawood (Mechanical)
**Deadline:** Mar 1, 2026
**Format:** PDF via Microsoft Word (UMich Office 365), max 5 pages

This document is a planning outline for the Phase 2 memo. It specifies what goes on each page, the section structure with word budgets, every figure and table needed, writing assignments, and the submission checklist.

---

## 1. Page-by-Page Layout

The memo has a hard 5-page limit. Figures and tables do not count toward the word limit but they consume page space. The layout below balances text and visuals so everything fits.

### Page 1: Introduction + System Architecture

| Element | Type | Space |
|---------|------|-------|
| Title, team, course header | Text | ~3 lines |
| Introduction / problem statement | Text (~150 words) | ~1/4 page |
| System architecture description | Text (~200 words) | ~1/3 page |
| **Figure 1:** System block diagram (functions/signals) | Figure | ~1/3 page |

### Page 2: Trade Studies + Electrical Design (Part 1)

| Element | Type | Space |
|---------|------|-------|
| Trade study results summary | Text (~200 words) | ~1/3 page |
| **Table 1:** Trade study comparison matrix | Table | ~1/6 page |
| Electrical design intro + power distribution | Text (~150 words) | ~1/4 page |
| **Figure 2:** Circuit schematic (power + signal paths) | Figure | ~1/3 page |

### Page 3: Electrical Design (Part 2) + Mechanical Concept

| Element | Type | Space |
|---------|------|-------|
| Pin assignments + power budget discussion | Text (~150 words) | ~1/4 page |
| **Figure 3:** Circuit layout (physical arrangement) | Figure | ~1/4 page |
| **Table 2:** Power budget summary | Table | ~1/6 page |
| Mechanical concept description (Dawood) | Text (~150 words) | ~1/4 page |
| **Figure 4:** Mechanical component sketch(es) | Figure | ~1/6 page |

### Page 4: Engineering Analysis + BOM

| Element | Type | Space |
|---------|------|-------|
| Engineering analysis summary | Text (~200 words) | ~1/3 page |
| **Table 3:** Latency budget breakdown | Table | ~1/6 page |
| Bill of materials description + purchasing instructions | Text (~100 words) | ~1/6 page |
| **Table 4:** Bill of materials | Table | ~1/3 page |

### Page 5: Next Steps + Overflow

| Element | Type | Space |
|---------|------|-------|
| Next steps / Phase 3 plan | Text (~100 words) | ~1/6 page |
| Overflow from BOM table if needed | Table | variable |
| **Table 5:** Pin assignment table (if space allows, otherwise fold into Figure 2 annotations) | Table | ~1/3 page |
| White space / margin | -- | remainder |

**Total estimated text:** ~1,400 words (well under the 2,000-word limit that applies to the final report; the Phase 2 memo has no explicit word limit, only a 5-page limit).

---

## 2. Section Outline with Estimated Word Counts

### 2.1 Introduction / Problem Statement (~150 words)

**Purpose:** Frame the project for the instructor. Establish the need (Bolton Step 1) and the problem (Bolton Step 2) concisely.

Content:
- The UR30 is a 6-axis collaborative robot used for metal paste dispensing research
- It lacks a native extrusion axis -- the paste pump must be driven by an external stepper motor synchronized with robot motion
- The project delivers a stepper motor driver that functions as a 7th axis, receiving real-time commands from the UR30 via RTDE
- Mention the pump/motor are TBD (provided by instructor)
- State the design goal: <20ms end-to-end latency, within 2A continuous power budget from UR30

### 2.2 System Architecture + Block Diagram (~200 words + Figure 1)

**Purpose:** Present the full system architecture and communication chain. This is the core of the memo.

Content:
- Walk through the signal chain: UR30 -> Pi -> SKR Pico -> stepper -> pump
- Describe each communication link and its protocol (RTDE over TCP/IP, Klipper Unix socket, USB serial, TMC2209)
- Describe the feedback path: stepper status -> Klipper -> bridge -> RTDE -> URScript
- Note the Pi400 as optional HMI (dashed box in diagram)
- Reference Figure 1 for the visual

**Figure 1** shows: all functional blocks, all signal paths with protocol labels, feedback loop, power paths (24V/5V), and the Pi400 as dashed/optional.

### 2.3 Trade Study Results Summary (~200 words + Table 1)

**Purpose:** Justify the three major design decisions with quantitative trade study scores.

Content:
- Communication protocol: RTDE selected (4.85) over Modbus TCP (3.30), Primary Interface (2.95), XML-RPC (2.25), Dashboard Server (1.65)
- Firmware/software stack: Klipper selected (4.70) over Lingua Franca (1.95) -- address Prof. Pannier's suggestion directly
- MCU platform: SKR Pico selected (on hand, Klipper-native, TMC2209 soldered)
- Note the location trade study (Dawood, in progress) for pump/electronics mounting
- Reference full trade study documents in the repo for detailed scoring criteria

**Table 1:** 3-row summary table:

| Decision | Selected | Score | Runner-Up | Score | Key Differentiator |
|----------|----------|-------|-----------|-------|--------------------|
| Protocol | RTDE | 4.85 | Modbus TCP | 3.30 | Native UR30 support, 500Hz, bidirectional |
| Software | Klipper | 4.70 | Lingua Franca | 1.95 | Production-proven, motion planning, driver support |
| MCU | SKR Pico | -- | Custom RP2040 | -- | On hand, TMC2209 soldered, Klipper-native |

### 2.4 Electrical Design (~300 words total + Figures 2-3 + Table 2)

**Purpose:** Present the circuit schematic, physical layout, pin assignments, and power budget. This is Willem's primary contribution.

#### 2.4a Circuit Schematic (~100 words + Figure 2)

Content:
- Power path: UR30 24V -> 3A blade fuse -> distribution node -> (a) SKR Pico VIN, (b) Pololu D24V22F5 buck -> 5.1V -> Pi GPIO header
- Protection: TVS diode (SMBJ24CA) at UR30 output, bulk cap (100uF/35V), polyfuse (2A resettable) on Pi 5V rail
- Signal paths: Pi USB -> SKR Pico USB-C (Klipper serial), UR30 Ethernet -> switch -> Pi Ethernet (RTDE), SKR Pico E-axis -> stepper 4-wire

**Figure 2:** Schematic showing power distribution and signal connections. Draw in KiCad or draw.io. Show wire gauges (18 AWG for 24V, 22 AWG for 5V).

#### 2.4b Circuit Layout (~50 words + Figure 3)

Content:
- Physical arrangement of components relative to each other
- Electronics at robot base (Pi + SKR Pico + buck converter + fuse) in a 3D-printed enclosure
- Motor cable routed along robot arm to end effector
- Ethernet cable to UR30 controller cabinet

**Figure 3:** Top-down sketch of physical component arrangement with dimensions. Primarily Dawood's drawing; Willem provides component dimensions.

#### 2.4c Pin Assignments + Power Budget (~150 words + Table 2)

Content:
- Summarize key pin assignments (full table in supplementary materials or Table 5 if space allows):
  - SKR Pico E-axis: Step gpio14, Dir gpio13, Enable gpio15, TMC2209 UART RX gpio9/TX gpio8
  - Pi: USB-A to SKR Pico, Ethernet to switch, GPIO pins 2/4 for 5V power input
  - UR30: Power block (PWR/GND), Ethernet for RTDE
- Power budget summary referencing Table 2

**Table 2:** Power budget:

| Device | Idle (A@24V) | Typical (A@24V) | Peak (A@24V) | Notes |
|--------|-------------|-----------------|-------------|-------|
| Pi 4B (via buck @ 90% eff) | 0.15 | 0.35 | 0.50 | 1.5A design @ 5.1V |
| SKR Pico (logic) | 0.05 | 0.08 | 0.10 | RP2040 + TMC2209 quiescent |
| Stepper motor | 0.00 | 0.50-1.00 | 1.20 | TBD -- placeholder NEMA 17 |
| Fan (optional) | 0.00 | 0.05 | 0.10 | If TMC2209 cooling needed |
| **Total** | **0.20** | **~1.0** | **~1.9** | **Budget: 2.0A cont / 3.5A burst** |

### 2.5 Mechanical Concept (~150 words + Figure 4)

**Purpose:** Dawood's section. Describe the physical packaging, mounting, enclosure, and cable routing concept.

Content:
- Enclosure concept for electronics (3D-printed, mounts at robot base or on arm)
- End effector mounting for pump/motor assembly
- Cable management approach (along arm, strain relief, connectors)
- Identify which components need 3D printing and provide design sketches
- Ventilation/cooling considerations

**Figure 4:** Hand sketch or CAD screenshot of the mechanical concept. Show enclosure, mounting points, cable routing. Can be multiple sub-sketches if needed.

### 2.6 Engineering Analysis Summary (~200 words + Table 3)

**Purpose:** Present the quantitative analyses that support design feasibility.

Content:
- **Latency analysis:** End-to-end ~5-20ms typical, ~35ms worst case. Adequate for paste dispensing (not high-speed CNC). Reference `docs/latency_analysis.md` for full breakdown.
- **Power analysis:** System draws ~1.0A typical at 24V, within UR30's 2A continuous budget with margin. Reference Table 2 and `docs/pi_power.md`.
- **Motor/pump analysis:** Noted as pending hardware receipt. Will characterize torque requirements, flow rate vs. RPM, and acceleration limits in Phase 3. State placeholder assumptions (NEMA 17, 1.0A rated, 0.4 N-m holding torque).
- **Communication throughput:** RTDE at 500Hz provides 2ms command cycle. Klipper processes commands with ~100ms lookahead buffer. No bottleneck at expected extrusion rates.

**Table 3:** Latency budget:

| Segment | Typical (ms) | Worst Case (ms) |
|---------|-------------|-----------------|
| UR30 RTDE output cycle | 0-2 | 4 |
| Ethernet + switch | 0.1-0.5 | 1 |
| Bridge processing (Python) | 0.5-2 | 5 |
| klippy host processing | 0.5-2 | 5 |
| USB serial to MCU | 1-3 | 5 |
| MCU step generation | <0.1 | 0.5 |
| **Total** | **~5-8** | **~20** |

### 2.7 Bill of Materials (~100 words + Table 4)

**Purpose:** List every component needed with supplier part numbers and purchasing instructions.

Content:
- Brief paragraph on purchasing: instructor orders from UMich-contracted suppliers (DigiKey, Newark, Grainger, MSC Direct, BH Photo Video). Some items may be in lab inventory -- verify before ordering.
- Note: motor and pump provided by instructor, SKR Pico already on hand
- Identify 3D-printed components (designed by Dawood, printed using instructor's printer)

**Table 4:** Bill of materials:

| Item | Description | Qty | Supplier | Part Number | Est. Price | Notes |
|------|-------------|-----|----------|-------------|-----------|-------|
| Raspberry Pi 4B | Klipper host, 2GB+ | 1 | DigiKey / Newark | TBD | ~$35-55 | Check lab inventory first |
| MicroSD card | 32GB, Class 10 | 1 | DigiKey | TBD | ~$8 | For Pi OS + Klipper |
| Pololu D24V22F5 | 24V-to-5V buck, 2.5A | 1 | DigiKey (Pololu) | TBD | ~$10 | Powers Pi via GPIO |
| Gigabit switch | Unmanaged, 5-port | 1 | Newark | TBD | ~$15-25 | Check lab inventory |
| Ethernet cables | Cat5e, various lengths | 2-3 | Newark | TBD | ~$5 ea | UR30-switch, switch-Pi |
| USB-C cable | Pi USB-A to SKR Pico USB-C | 1 | DigiKey | TBD | ~$5 | Klipper serial |
| Blade fuse + holder | 3A, inline | 1 | DigiKey | TBD | ~$3 | 24V main protection |
| TVS diode | SMBJ24CA | 1 | DigiKey | TBD | ~$1 | Transient suppression |
| Bulk capacitor | 100uF/35V electrolytic | 1 | DigiKey | TBD | ~$1 | Input smoothing |
| Polyfuse | 2A resettable PTC | 1 | DigiKey | TBD | ~$1 | Pi 5V rail protection |
| Wire | 18 AWG, ~3m | 1 lot | DigiKey | TBD | ~$5 | 24V power distribution |
| Screw terminals | Assorted | 1 lot | DigiKey | TBD | ~$5 | Connections |
| 3D-printed enclosure | Electronics housing | 1 | Instructor printer | N/A | N/A | Dawood designs |
| SKR Pico V1.0 | RP2040 + TMC2209 | 1 | -- | -- | -- | Already on hand |
| Stepper motor | NEMA 17 (TBD) | 1 | -- | -- | -- | Provided by instructor |
| Pump | Metal paste dispensing | 1 | -- | -- | -- | Provided by instructor |

### 2.8 Next Steps / Phase 3 Plan (~100 words)

**Purpose:** Briefly state what happens after Phase 2 approval.

Content:
- Phase 3 (Mar 2-22): Build and integration
  - Week 9 (Spring Break): Flash Klipper firmware, first stepper test on bench
  - Week 10: Deploy RTDE bridge daemon, integrate with UR30
  - Week 11: Full chain integration, mechanical assembly, progress memo
- Phase 4 (Mar 23 - Apr 5): System testing (latency, accuracy, fault handling)
- Request go/no-go decision and feedback on BOM for purchasing

---

## 3. Figures List

| # | Title | Description | Source / Tool | Author |
|---|-------|-------------|---------------|--------|
| 1 | System Block Diagram | All functional blocks (UR30, switch, Pi, SKR Pico, motor, pump, Pi400-dashed), all signal paths with protocol labels, feedback loop, power distribution (24V/5V). Shows closed-loop nature of the system. | draw.io or Visio (for Word); Mermaid (for repo) | Willem |
| 2 | Circuit Schematic | Power distribution: UR30 24V -> fuse -> TVS -> bulk cap -> distribution to SKR Pico VIN and buck converter -> Pi 5V. Signal connections: USB, Ethernet, motor 4-wire. Wire gauges annotated. Protection components shown. | KiCad or draw.io | Willem |
| 3 | Circuit Layout / Physical Arrangement | Top-down sketch of component placement. Electronics cluster (Pi, SKR Pico, buck, fuse) in enclosure at robot base. Motor/pump at end effector. Cable routing along arm. Dimensions annotated. | Hand sketch or Fusion 360 screenshot | Dawood (layout), Willem (component dimensions) |
| 4 | Mechanical Component Sketches | Enclosure design, end effector mount, cable management. May be multiple sub-sketches. Shows mounting points, ventilation holes, access ports. | Hand sketch or CAD | Dawood |

### Notes on Figures
- All figures should be created at high resolution for the PDF
- Use consistent visual style (line weights, fonts, colors) across all figures
- Figure 1 (block diagram) is the most important -- it communicates the entire design at a glance
- Figures do not count toward the word limit but they take page space; keep each to roughly 1/4 to 1/3 page
- For the repo: also commit SVG/PNG versions alongside the Word document

---

## 4. Tables List

| # | Title | Description | Columns | Author |
|---|-------|-------------|---------|--------|
| 1 | Trade Study Summary | One row per trade decision (protocol, software, MCU). Shows selected option, score, runner-up, key differentiator. | Decision, Selected, Score, Runner-Up, Score, Key Differentiator | Willem |
| 2 | Power Budget | Current draw per device at idle/typical/peak. Bottom row shows total vs. UR30 2A/3.5A budget. | Device, Idle (A@24V), Typical (A@24V), Peak (A@24V), Notes | Willem |
| 3 | Latency Budget | Per-segment latency breakdown. Bottom row shows total. | Segment, Typical (ms), Worst Case (ms) | Willem |
| 4 | Bill of Materials | Every component with supplier, part number, price, notes. | Item, Description, Qty, Supplier, Part Number, Est. Price, Notes | Willem (electrical), Dawood (mechanical) |
| 5 | Pin Assignment Summary (if space) | Key pin assignments for SKR Pico, Pi, UR30. | Device, Pin, Signal, Direction, Voltage, Connected To | Willem |

### Notes on Tables
- Tables do not count toward the word limit
- Keep tables compact -- use abbreviations where clear
- Table 4 (BOM) is the largest and may span ~1/3 page; part numbers must be filled in before submission by searching DigiKey/Newark catalogs
- If Table 5 does not fit on page 5, fold the pin information into annotations on Figure 2 or reference the full table in supplementary materials

---

## 5. Writing Assignments

### Willem (Software/EE) -- Primary Author

| Section | Est. Words | Notes |
|---------|-----------|-------|
| 2.1 Introduction / problem statement | ~150 | Frame the project |
| 2.2 System architecture + block diagram | ~200 | Walk through Figure 1 |
| 2.3 Trade study results summary | ~200 | Summarize three trade studies |
| 2.4 Electrical design (schematic, pins, power) | ~300 | Core EE content |
| 2.6 Engineering analysis summary | ~200 | Latency + power analysis |
| 2.7 Bill of materials | ~100 | Purchasing instructions |
| 2.8 Next steps / Phase 3 plan | ~100 | Brief schedule |
| **Subtotal** | **~1,250** | |

### Willem -- Figures and Tables

| Deliverable | Notes |
|-------------|-------|
| Figure 1: System block diagram | draw.io or Visio |
| Figure 2: Circuit schematic | KiCad or draw.io |
| Tables 1-5 | All tables except mechanical BOM rows |

### Dawood (Mechanical) -- Contributing Author

| Section | Est. Words | Notes |
|---------|-----------|-------|
| 2.5 Mechanical concept | ~150 | Enclosure, mounting, cable routing |
| BOM rows for 3D-printed / mechanical parts | -- | Add to Table 4 |
| **Subtotal** | **~150** | |

### Dawood -- Figures

| Deliverable | Notes |
|-------------|-------|
| Figure 3: Circuit layout (physical arrangement) | Collaborate with Willem on component dimensions |
| Figure 4: Mechanical component sketches | Enclosure, end effector mount |

---

## 6. Review Process

Per the course requirement, **one team member edits the entire document** for consistency of voice, formatting, and style.

### Proposed Process

1. **Willem** writes all sections listed above in a shared Word document (UMich Office 365, OneDrive)
2. **Dawood** writes Section 2.5 and provides Figures 3-4 in the same document
3. **Willem** performs the final edit of the entire document:
   - Ensure consistent formatting (Word Styles: Heading 1, Heading 2, Body Text, Caption)
   - Ensure consistent terminology (e.g., always "SKR Pico" not "BTT Pico" or "Pico board")
   - Check all figure/table references in text
   - Verify all figures are legible at print scale
   - Proofread for grammar, spelling, and clarity
   - Verify page count is exactly 5 or fewer
4. **Dawood** reviews the final edit for mechanical accuracy
5. **Willem** exports to PDF and submits

### Timeline

| Date | Milestone |
|------|-----------|
| Feb 19 | All figures drafted (Willem: Figs 1-2; Dawood: Figs 3-4) |
| Feb 21 | Willem completes first draft of all text sections |
| Feb 23 | Dawood completes Section 2.5 text, reviews full draft |
| Feb 25 | DigiKey/Newark part numbers filled in for BOM (Table 4) |
| Feb 26 | Willem completes final edit of entire document |
| Feb 27 | Dawood reviews final edit |
| Feb 28 | Final PDF exported, both team members approve |
| **Mar 1** | **Submit via UMich Office 365** |

---

## 7. Submission Checklist

### Format Requirements

- [ ] Written in Microsoft Word via UMich Office 365
- [ ] Uses Word Styles for headings, body text, captions (not manual formatting)
- [ ] Exported to PDF
- [ ] PDF is 5 pages or fewer
- [ ] All figures are legible at printed size (no text smaller than 8pt in figures)
- [ ] All tables are legible and properly formatted

### Content Requirements

- [ ] Block diagram of functions/signals (Figure 1)
- [ ] Circuit diagram / schematic (Figure 2)
- [ ] Circuit layout / physical arrangement (Figure 3)
- [ ] Mechanical component sketches (Figure 4)
- [ ] Bill of materials with purchasing instructions (Table 4 + text)
- [ ] Engineering analysis (latency, power) (Section 2.6 + Tables 2-3)
- [ ] Trade study results referenced or summarized (Section 2.3 + Table 1)
- [ ] 3D-printed components identified with design sketches
- [ ] Specific purchasing instructions for UMich suppliers (DigiKey, Newark, Grainger, MSC Direct, BH Photo Video)

### Process Requirements

- [ ] One team member (Willem) edited the entire document for consistency
- [ ] Both team members reviewed and approved the final version

### Pre-Submission Checks

- [ ] All "TBD" items resolved or explicitly marked as pending hardware receipt
- [ ] Part numbers filled in for all purchasable BOM items
- [ ] Figures are embedded (not linked) in the Word document
- [ ] Page breaks are intentional (no orphaned headings or split tables)
- [ ] File named according to course convention (check with instructor)
- [ ] Submitted to correct location (UMich Office 365 assignment submission)

---

## 8. Open Items to Resolve Before Writing

These items from `docs/design/phase2_deliverables.md` must be resolved before the memo can be completed:

| Item | Owner | Deadline | Impact |
|------|-------|----------|--------|
| Confirm Pi model (Pi 4B recommended) | Willem | Feb 17 | Unblocks pin table, power budget, BOM |
| Location trade study | Dawood | Feb 19 | Unblocks Figure 3, Section 2.5 |
| Look up DigiKey/Newark part numbers for BOM | Willem | Feb 25 | Required for Table 4 purchasing instructions |
| Check lab inventory (Pi, Ethernet switch, cables) | Both | Feb 17 | Determines what to purchase vs. already have |
| Present trade studies to Prof. Pannier | Both | Feb 19 | May result in feedback that changes design |
| Decide Pi power method (GPIO header vs USB-C) | Willem | Feb 17 | Affects schematic and pin table |
| Decide on TMC2209 cooling fan | Willem | Feb 19 | Affects BOM and power budget |
