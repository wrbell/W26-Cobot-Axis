# Phase 2 Deliverables — Planning

**Phase 2 deadline:** Mar 1, 2026
**Deliverable:** PDF memo (≤5 pages) with preliminary design, BOM, and analysis.
**Submission format:** Microsoft Word via UMich Office 365, one team member edits entire document.

This document scopes what's required for each Phase 2 deliverable, what information we have vs. need, and what decisions must be made before producing them.

---

## 1. Pin Assignment Table

### What It Is
A single table showing every electrical connection in the system — which pin on which device connects to what, with signal name, direction, and voltage level.

### Devices to Cover

| Device | Interface to Document |
|--------|----------------------|
| SKR Pico V1.0 | E-axis stepper pins, TMC2209 UART, USB-C, power input (VIN/GND), fan port (optional cooling) |
| Raspberry Pi (headless) | USB to SKR Pico, Ethernet to UR30 network, 5V power input (GPIO or USB-C), GND |
| UR30 Controller | Power block (PWR/GND), Ethernet port for RTDE |
| Buck converter | 24V input, 5V output to Pi |
| Stepper motor | 4-wire connection to SKR Pico E-axis JST-XH |

### Information We Have
- **SKR Pico E-axis pins (from `docs/skr_pico_specs.md` Section 3.1):**
  - Step: gpio14, Dir: gpio13, Enable: !gpio15
  - TMC2209 UART: RX gpio9, TX gpio8, Address 3
  - DIAG/filament: gpio16 (available for StallGuard if needed)
- **SKR Pico power:** VIN accepts 12–24V DC, screw terminals
- **SKR Pico USB:** USB-C to Pi for Klipper serial protocol
- **Fan ports:** Fan0 (gpio17), Fan1 (gpio18), Fan2 (gpio20) — one may be used for TMC2209 heatsink cooling
- **UR30 power block:** PWR (+24V), GND (0V), 24V (ext input), 0V (ext GND) — 4 screw terminals
- **Pi GPIO:** Pins 2/4 = 5V power in, Pin 6 = GND (if powering via GPIO header)

### Information We're Missing

| Gap | Impact | How to Resolve |
|-----|--------|----------------|
| **Which Pi model** | Determines USB port type, GPIO header presence, power connector | Check lab inventory or purchase Pi 4B |
| **Pi power method** — USB-C vs GPIO header | Determines whether buck converter output goes to USB-C cable or to GPIO pins 2+4 | Design decision: GPIO recommended (simpler, no USB-C cable needed) |
| **UR30 Ethernet port** — which one, shared with teach pendant? | Determines if we need a switch or direct connection | Check in lab or UR30 manual |
| **Motor wire colors/pinout** | Need to map A1/A2/B1/B2 to JST-XH connector | Awaiting provided motor — document on receipt |
| **Hardware e-stop wiring** | Do we wire a physical e-stop to UR30 digital I/O, or rely solely on RTDE software e-stop? | Design decision: software-only for MVP, note hardware e-stop as future option |

### Decisions Required Before Writing
1. **Pi power input method:** GPIO header (recommended) or USB-C
2. **Fan for TMC2209 cooling:** Use one of Fan0/1/2, or rely on passive heatsink
3. **Hardware e-stop:** Include in pin table or defer to Phase 3

### Format
Single table with columns: Device | Pin/Terminal | Signal Name | Direction | Voltage | Connected To | Notes

---

## 2. Power Budget Worksheet

### What It Is
A table showing every device's current draw from the 24V bus, with idle/typical/peak scenarios, demonstrating the system stays within the UR30's 2A continuous / 3.5A burst rating.

### Information We Have (from `docs/pi_power.md`)

| Device | Current from 24V | Status |
|--------|------------------|--------|
| Pi (via buck @ ~90% eff) | ~0.35A typical | **Known** (assuming Pi 4B, 1.5A @ 5.1V design current) |
| SKR Pico (logic, no motor) | ~0.08A | **Known** (50–80mA quiescent) |
| Stepper motor (via TMC2209) | 0.5–1.0A typical | **Parameterized** — depends on provided motor's rated current |
| Buck converter losses | Included in Pi calculation | **Known** (~90% efficiency) |

**Total known:** ~1.0A typical, ~1.4A peak — within 2A continuous budget.

### Information We're Missing

| Gap | Impact | How to Resolve |
|-----|--------|----------------|
| **Actual motor rated current** | Determines if 2A budget is sufficient or if external PSU is needed | Awaiting provided motor — use 1.0A placeholder (typical NEMA 17) |
| **Fan power** | Small (~0.1A at 24V) but should be included | Add if cooling fan is selected |
| **Protection components** | Fuse, TVS diode — negligible quiescent draw but note in-rush | Already specified in `docs/pi_power.md` Section 6.6 |
| **Pi model confirmation** | Pi 4B vs Pi Zero 2W changes the 5V budget significantly | Use Pi 4B as baseline (worst case for power) |

### Decisions Required Before Writing
1. **Pi model** — affects 5V draw (Pi 4B: 1.5A design, Pi Zero 2W: 0.5A)
2. **Single Pi architecture confirmed** — no slave Pi (already decided, but `docs/pi_power.md` still references old dual-Pi architecture)
3. **External PSU decision** — use internal 24V only, or spec an external PSU as contingency

### What We Can Do Now
- Produce the worksheet with Pi 4B + placeholder motor current (1.0A)
- Mark motor row as "TBD — parameterized on receipt" with a range (0.5–1.2A)
- Show three scenarios: idle, typical extrusion, peak acceleration
- Show margin vs. 2A continuous and 3.5A burst

### Note: `docs/pi_power.md` Needs Updating
The existing power doc still describes the old architecture with a slave Pi and Pi 400 as the Klipper host. The actual architecture uses a single headless Pi. The power budget section (Section 7) numbers are approximately correct for single-Pi but the text and diagrams are stale. We should either:
- Update `docs/pi_power.md` to reflect single-Pi architecture, or
- Write a fresh, concise power budget worksheet as a separate deliverable and reference `pi_power.md` for detailed component specs only

### Format
Table with columns: Device | Idle (A @ 24V) | Typical (A @ 24V) | Peak (A @ 24V) | Notes
Bottom row: Total with margin calculation vs UR30 budget.

---

## 3. Block Diagram of Functions/Signals

### What It Is
A visual diagram showing all functional blocks in the system, the signals flowing between them, and the feedback path. This is the key diagram for the Phase 2 memo — it communicates the entire system design at a glance.

### Blocks to Show

| Block | What It Represents |
|-------|-------------------|
| UR30 Controller | Robot controller running URScript, source of extrusion commands |
| Gigabit Switch | Ethernet network connecting UR30, Pi, and Pi400 |
| Raspberry Pi | Klipper host + Moonraker + RTDE bridge daemon |
| SKR Pico | Klipper MCU firmware, TMC2209 drivers |
| Stepper Motor | NEMA 17 (or similar), drives the pump |
| Pump | Metal paste dispensing mechanism |
| Pi400 (dashed) | Optional HMI — SSH, web UI monitoring |
| 24V Power Supply | UR30 power block → buck converter → distribution |

### Signals to Show

| Signal | From → To | Protocol/Type | Data |
|--------|-----------|---------------|------|
| Extrusion commands | UR30 → Pi | RTDE over TCP/IP (port 30004) | mode, rate, TCP speed, enable, e-stop, home |
| Status feedback | Pi → UR30 | RTDE over TCP/IP | status, error code, actual rate, ready, fault |
| G-code / stepper commands | Pi (klippy) → SKR Pico | USB serial (Klipper protocol) | MANUAL_STEPPER MOVE, SET_POSITION, ENABLE |
| Step/dir pulses | SKR Pico → Motor | TMC2209 driver | step, direction, enable, UART config |
| Klipper status | SKR Pico → Pi | USB serial | position, driver status, temperature |
| TMC2209 config | SKR Pico ↔ TMC2209 | UART (shared bus) | run_current, stealthchop, stallguard |
| 24V power | UR30 → SKR Pico | Direct wire | 24V DC |
| 5V power | Buck converter → Pi | Wire | 5.1V DC |
| Web UI / SSH | Pi ↔ Pi400 | HTTP / SSH over Ethernet | Mainsail dashboard, terminal |

### Information We Have
- **All signal paths are defined** — register allocation finalized (`docs/register_allocation.md`)
- **All protocols chosen** — RTDE, Klipper Unix socket, USB serial, TMC2209 UART
- **Latency per segment** documented in `docs/latency_analysis.md`

### Information We're Missing

| Gap | Impact | How to Resolve |
|-----|--------|----------------|
| **Feedback path from Klipper** | What status do we actually read back? Currently reporting commanded rate, not actual. | Design decision — the bridge enhancement design doc (in progress) will address this |
| **Physical signal routing** | Where cables run (along arm vs. base) | Dawood — location trade study |

### Decisions Required Before Writing
1. **Level of detail** — Phase 2 memo has 5 pages total for everything. Block diagram should be ~1/2 page. Keep it functional, not physical.
2. **Feedback loop emphasis** — the memo should clearly show the closed-loop nature: UR30 commands → stepper action → status feedback → UR30 reads status

### Format Options
- **Mermaid diagram** in markdown (renders on GitHub, easy to edit)
- **ASCII art** (works everywhere, already used in README)
- **Draw.io / Lucidchart** for the actual PDF submission
- Recommend: create in Mermaid for the repo, recreate in draw.io/Word for the PDF

---

## 4. Formal Design Specification (Bolton Step 3)

### What It Is
Bolton Step 3: "Preparation of a Specification." A document listing the required functions, interfaces, accuracy targets, and operating environment constraints. This is the bridge between problem analysis (Step 2, done) and solution generation (Step 4, done).

### Sections Required
1. **Functional requirements** — what the system must do (extrude on command, sync to TCP speed, report status, e-stop, etc.)
2. **Interface specifications** — RTDE registers, Klipper commands, USB serial, power connections
3. **Performance targets** — latency (<20ms), speed range, accuracy (TBD on motor)
4. **Operating environment** — temperature, vibration, power, network
5. **Constraints** — 2A power budget, single axis, SKR Pico form factor, non-RT Linux host
6. **Parameters awaiting hardware** — motor/pump specs, marked as TBD with acceptable ranges

### Information We Have
- Problem analysis covers most of this (`docs/problem_analysis.md`)
- Register allocation is finalized (`docs/register_allocation.md`)
- Latency budget is analyzed (`docs/latency_analysis.md`)
- Trade studies justify all technology choices (`trades/`)

### What's Actually New Work
The design spec mostly consolidates existing analysis into a formal specification format. The new content needed:
- Formal "shall" statements (e.g., "The system shall respond to e-stop within 10ms")
- Interface specification table (register-by-register with data types, ranges, units)
- Accuracy targets with justification (even if some are "TBD — characterize in Phase 4")

### Decisions Required Before Writing
1. **How formal?** — This is a 5-page memo, not a MIL-STD spec. Keep it concise — 1 page of spec in the memo, full spec as a separate repo doc.
2. **Accuracy targets** — we can state latency targets (<20ms) and note motor/pump accuracy as TBD

---

## 5. Bill of Materials

### What It Is
A list of every component needed to build the system, with part numbers from UMich-contracted suppliers (DigiKey, Newark, Grainger, MSC Direct, BH Photo Video), quantities, and unit prices.

### Components

| Component | Qty | Status | Supplier |
|-----------|-----|--------|----------|
| SKR Pico V1.0 | 1 | **On hand** | Already have |
| Stepper motor | 1 | **Provided by instructor** | N/A |
| Pump | 1 | **Provided by instructor** | N/A |
| Raspberry Pi 4B (or similar) | 1 | **Need to check inventory** | DigiKey / Newark |
| MicroSD card (32GB) | 1 | Need to purchase | DigiKey |
| Pololu D24V22F5 buck converter (24V→5V) | 1 | Need to purchase | DigiKey (Pololu distributor) |
| Gigabit Ethernet switch (unmanaged) | 1 | Need to purchase or check lab inventory | Newark / Amazon |
| Ethernet cables (Cat5e/6) | 2–3 | Need to purchase | Newark |
| USB-C cable (Pi to SKR Pico) | 1 | Need to purchase or check inventory | DigiKey |
| 3A blade fuse + holder | 1 | Need to purchase | DigiKey |
| TVS diode (SMBJ24CA) | 1 | Need to purchase | DigiKey |
| Bulk cap (100µF/35V) | 1 | Need to purchase | DigiKey |
| Polyfuse (2A resettable PTC) | 1 | Need to purchase | DigiKey |
| 18 AWG wire (24V power) | ~3m | Need to purchase | DigiKey |
| Screw terminals / connectors | Assorted | Need to purchase | DigiKey |
| 3D-printed enclosure(s) | TBD | **Dawood — design needed** | Instructor's printer |

### Information We're Missing

| Gap | Impact | How to Resolve |
|-----|--------|----------------|
| **Pi model — on hand?** | Determines if we need to purchase | Check lab inventory |
| **Specific DigiKey/Newark part numbers** | Required for purchasing instructions | Search supplier catalogs |
| **3D-printed components** | Dawood needs to identify what needs printing | Dawood — mechanical design |
| **Cable lengths** | Affects wire quantity | Measure in lab |
| **Ethernet switch — in lab?** | May already have one | Check lab |

### Decisions Required Before Writing
1. **Pi model** — Pi 4B is recommended, but need to confirm availability
2. **One or two buck converters** — only 1 needed (single Pi architecture, Pi400 powered independently)
3. **Protection components** — include all from `docs/pi_power.md` Section 6.6 or keep minimal for MVP

### Format
Table with columns: Item | Description | Qty | Supplier | Part Number | Unit Price | Notes
Include purchasing instructions paragraph explaining how instructor orders from UMich suppliers.

---

## 6. Circuit Diagram (Schematic)

### What It Is
A schematic showing electrical connections: power distribution from UR30 → fuse → buck converter → Pi, UR30 → SKR Pico → stepper, with protection components.

### Scope
- **Not a PCB design** — this is a wiring schematic showing how off-the-shelf modules connect
- Show power paths with wire gauges and fuse ratings
- Show signal paths (USB, Ethernet, motor cable)
- Show protection components (fuse, TVS, bulk cap, polyfuse)

### What We Can Draw Now
- Power distribution (UR30 24V → fuse → distribution → buck → Pi, → SKR Pico VIN)
- USB serial connection (Pi USB → SKR Pico USB-C)
- Ethernet connection (UR30 → switch → Pi, Pi400)
- Motor connection (SKR Pico E-axis JST-XH → stepper 4-wire)

### What We Can't Draw Yet
- Motor wire pinout (awaiting motor receipt)
- Exact cable lengths
- Physical layout (Dawood)

### Format
- Can be drawn in KiCad, Fritzing, draw.io, or even neat hand sketches
- For the repo: SVG or PNG exported from a drawing tool
- For the PDF memo: embedded in Word

---

## 7. Circuit Layout (Physical Arrangement)

### What It Is
A sketch showing where components are physically located relative to each other and the robot. Not a PCB layout — this is a packaging/arrangement drawing.

### Primarily Dawood's Responsibility
This depends heavily on the location trade study and mechanical design. Willem provides:
- Component dimensions (SKR Pico: 85×56mm, Pi 4B: ~85×56mm, buck converter: ~20×18mm)
- Heat dissipation requirements (TMC2209 heatsink, Pi passive cooling)
- Cable routing constraints (USB max ~3m, motor cable max ~3m, Ethernet max ~100m)

### What We Can Contribute
- Recommended placement: electronics at robot base, motor/pump at end effector
- Minimum clearances and ventilation requirements
- Mounting hole patterns (SKR Pico matches Pi mounting holes)

---

## Summary: Production Order

Recommended order for producing these deliverables:

| Priority | Deliverable | Blocked By | Estimated Effort |
|----------|-------------|------------|-----------------|
| 1 | **Block diagram** | Nothing — all info available | 1–2 hours |
| 2 | **Pin assignment table** | Pi model decision | 1 hour (once Pi decided) |
| 3 | **Power budget worksheet** | Pi model decision | 1 hour (mostly extracting from `pi_power.md`) |
| 4 | **BOM** | Pi model, supplier part number search | 2–3 hours (catalog searching) |
| 5 | **Design specification** | Nothing — consolidation of existing docs | 2 hours |
| 6 | **Circuit schematic** | Pin table complete | 2–3 hours (drawing tool) |
| 7 | **Circuit layout** | Location trade study (Dawood) | Dawood-led |

**Critical decision gate:** Which Pi model are we using? This unblocks items 2, 3, and 4. Pi 4B is recommended — if we confirm that, everything else follows.
