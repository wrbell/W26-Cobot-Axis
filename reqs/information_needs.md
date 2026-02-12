# Information Needs by Task

What data/information we **don't currently have** but need to complete each Phase 2 task. Items marked with a source indicate where to get them.

> **Key decisions made (2026-02-12):**
> - **Extrusion type:** Metal paste dispensing via a stepper-driven pump (mechanism TBD)
> - **Pump and motor:** Will be **provided to the team** — not sized/selected by us. Specs will be filled in once received. Design must accommodate a range of pump types and NEMA 17-class motors.
> - **Pi model:** Use a non-Pi400 Pi as the headless control node. Pi400 is optional HMI — system must run standalone (UR30 → Pi → SKR Pico → stepper) without it.
> - **Budget:** Not a constraint — instructor purchases from UMich suppliers.
> - **BTT board:** Confirmed as SKR Pico V1.0 (product code 1060000513). Full specs in `docs/skr_pico_specs.md`.

---

## Bolton Step 2: Problem Analysis

| Need | What Specifically | Status |
|------|-------------------|--------|
| ~~Extrusion mechanism type~~ | ~~What are we extruding?~~ **RESOLVED: Metal paste via stepper-driven pump** | **Answered** |
| Pump selection / mechanism | What pump? Syringe pump, peristaltic pump, progressive cavity pump? Each has different torque/speed/flow characteristics. | **Will be provided to team — specs TBD on receipt** |
| Metal paste properties | Viscosity, particle size, working temperature, pot life. Drives pump selection and flow rate requirements. | **Get from paste supplier / datasheet** |
| Target flow rate | Volume per second (mL/s or cc/min) needed for the application | **Depends on pump + paste + deposition geometry** |
| Acceptable latency threshold | We estimate 5–20ms, but what is the *maximum* tolerable latency before deposition quality degrades? Paste is more forgiving than FDM filament. | **Engineering judgment + literature on paste dispensing** |
| Mounting space constraints | Physical envelope available on the UR30 end effector for pump + motor + electronics. Dimensions, weight limits. | **Measure on the actual UR30 in the lab** |
| Environmental conditions | Temperature range, vibration levels, dust exposure at the robot cell | **Observe in lab** |

---

## Bolton Step 3: Design Specification

| Need | What Specifically | Status |
|------|-------------------|--------|
| Stepper motor specs | **Motor will be provided to team.** Once received, document: model number, rated voltage, rated current, holding torque, step angle, phase resistance, phase inductance, dimensions, shaft diameter. | **Awaiting provided hardware** |
| Pump torque requirement | How much torque does the pump need? Depends on pump type, paste viscosity, flow rate, back-pressure. | **Awaiting provided hardware — characterize on receipt** |
| Speed range | Min/max RPM for the stepper. Relates to pump flow rate and microstepping. | **Awaiting provided hardware — characterize on receipt** |
| Accuracy/precision targets | What positional/volumetric accuracy is needed for paste deposition? | **Engineering judgment based on deposition geometry** |
| Coupling / gear ratio | How does the motor couple to the pump? Direct drive, geared, belt? | **Decide during mechanical design (Dawood)** |

---

## Block Diagram of Functions/Signals

| Need | What Specifically | Source |
|------|-------------------|--------|
| Finalized register allocation | We have a *proposed* mapping in `docs/ur_rtde.md` but it's not confirmed. Need to decide which registers carry which signals. | **Design decision — finalize from proposal** |
| Feedback signals list | Exactly which status values flow back from Klipper → RTDE → UR30 (position, velocity, fault, temperature?) | **Design decision** |
| URScript program structure | How the UR30 program is organized — what triggers extrusion start/stop, how speed is synchronized with robot TCP speed | **Design decision + URScript programming** |

---

## Circuit Diagram + Circuit Layout

| Need | What Specifically | Source |
|------|-------------------|--------|
| Buck converter selection | We recommend Pololu D24V22F5 but haven't confirmed. Need: one or two units? Pi400 is optional, so maybe just one for the headless Pi. | **Design decision** |
| UR30 power block pinout | Which pins/terminals on the UR30 controller provide 24V, and how to physically connect (screw terminal? connector type?) | **UR30 User Manual** (`docs/`) — look up tool connector and controller I/O pinout |
| UR30 ethernet port location | Which ethernet port on the UR30 controller is available for RTDE? Is it shared with the teach pendant? | **UR30 User Manual** or **test in lab** |
| Cable lengths needed | Distance from UR30 controller to Pi, Pi to SKR Pico, SKR Pico to motor. Affects wire gauge and voltage drop. | **Measure in lab** |
| Connector types | What connectors does the UR30 power block use? SKR Pico uses screw terminals for VIN. | UR30 Manual + `docs/skr_pico_specs.md` |
| Pi model selection | Which non-Pi400 Pi do we have or will purchase? Pi 4B recommended (ethernet + USB). | **Check inventory / purchase** |
| Pi power input method | Power via buck converter to USB-C? Or via GPIO header pins 2+4 (5V) + pin 6 (GND)? GPIO bypasses the onboard voltage regulator. | **Design decision** |

---

## Circuit Layout

| Need | What Specifically | Source |
|------|-------------------|--------|
| Physical board arrangement | How are Pi, BTT Pico, buck converters, and protection components physically arranged? PCB, perfboard, or DIN rail? | **Design decision (Dawood — packaging concept)** |
| Enclosure dimensions | If using an enclosure, what are the internal dimensions? | **Depends on 3D-printed enclosure design** |

---

## Pin Assignment Table

| Need | What Specifically | Source |
|------|-------------------|--------|
| SKR Pico pinout | **We have this** — documented in `docs/skr_pico_specs.md` | Already documented |
| Which stepper driver socket to use | SKR Pico has 4x TMC2209 (X, Y, Z, E). Which one drives our motor? Affects step/dir/enable/DIAG pin assignments. | **Design decision** (E-stepper recommended — most intuitive for pump extrusion) |
| Pi GPIO usage | Are any Pi GPIO pins needed beyond USB serial to BTT Pico? (e.g., status LED, emergency stop input, fan control) | **Design decision** |
| UR30 I/O pin allocation | Which UR30 digital I/O pins (if any) are used beyond RTDE software registers? (e.g., hardware emergency stop) | **Design decision + UR30 I/O panel inspection** |

---

## Power Budget Worksheet

| Need | What Specifically | Source |
|------|-------------------|--------|
| Stepper motor current draw | **Motor will be provided.** Document rated current on receipt. TMC2209 board thermal limit is ~1.2A continuous with cooling. | **Awaiting provided hardware** |
| Pi model power draw | Depends on which Pi we use. Pi 4B: ~3W typical. Pi Zero 2W: ~1W typical. | **Check inventory / purchase** |
| Measured SKR Pico idle draw | Documented as 50-80mA @ 24V, but verify once we have the board powered up. | **Measure in lab (Phase 3)** |

---

## Bill of Materials + Purchasing Instructions

| Need | What Specifically | Source |
|------|-------------------|--------|
| ~~Stepper motor~~ | **RESOLVED: Will be provided to team.** Specs to be documented on receipt. | **Answered** |
| ~~Pump~~ | **RESOLVED: Will be provided to team.** Specs to be documented on receipt. | **Answered** |
| Pi model — buy or on hand? | Which non-Pi400 Pi do we have? If none, need to purchase (Pi 4B recommended). | **Check inventory** |
| ~~BTT SKR Pico — confirm on hand~~ | **RESOLVED: On hand.** SKR Pico V1.0, product code 1060000513, date code 2025.1.10. | **Answered** |
| MicroSD cards — quantity and size | At minimum 1 (for headless Pi). 2 if Pi400 also used. 32GB recommended. | **Design decision** |
| Network switch — specific model | Any unmanaged gigabit switch works. Need a specific part number from a UMich supplier. | **Search DigiKey/Newark** |
| Buck converter — specific model | Pololu D24V22F5 is recommended. Need: part number, quantity. Maybe just 1 if Pi400 is optional. | **Search UMich supplier catalogs** |
| Protection components — specific parts | Fuse (3A blade), TVS diode (SMBJ24CA), bulk cap (100µF/35V), polyfuse (2A). Need specific part numbers. | **Search DigiKey** |
| Ethernet cables — quantity and length | How many cables, what length? Depends on physical layout. | **Measure in lab** |
| USB cable — type and length | USB-C for SKR Pico to Pi. Length depends on packaging. | **Measure in lab** |
| ~~Total budget~~ | ~~What's our budget?~~ **RESOLVED: Budget is not a constraint.** Instructor purchases from UMich suppliers. | **Answered** |

---

## 3D-Printed Components (Dawood)

| Need | What Specifically | Source |
|------|-------------------|--------|
| UR30 end effector interface dimensions | Bolt pattern, flange diameter, mounting hole locations for the UR30 tool flange | **UR30 User Manual** — mechanical interface drawing |
| Motor dimensions | Depends on motor provided. NEMA 17 is 31mm bolt spacing (standard). | **Awaiting provided hardware** |
| SKR Pico mounting holes | Board dimensions: 85 x 56mm, Pi-compatible mounting holes. See `docs/skr_pico_specs.md`. | **Documented** |
| Pi mounting holes | Depends on Pi model selected. Pi 4B: 58x49mm hole pattern. | **Pi documentation** |
| Available 3D printer specs | What printer does Prof. Pannier have? Print volume, material (PLA? PETG? ABS?), layer resolution? | **Ask Prof. Pannier** |

---

## Location Trade Study (Dawood)

| Need | What Specifically | Source |
|------|-------------------|--------|
| UR30 payload capacity | Max payload at end effector (UR30 spec: 30kg, but what's already mounted?) | **UR30 datasheet + check current tooling** |
| Weight estimate for our assembly | Motor + BTT Pico + Pi + enclosure + cabling. Rough estimate needed. | **Sum component weights from datasheets** |
| Cable routing feasibility | Can cables run along the robot arm, or do they need to be external? | **Inspect UR30 cable routing channels in lab** |
| Alternative mounting locations | What other mounting points exist? Robot base, nearby table, overhead gantry? | **Survey the lab space** |

---

## Engineering Analysis

| Need | What Specifically | Source |
|------|-------------------|--------|
| Pump back-pressure / torque requirement | Force/torque needed to drive the pump with metal paste at target flow rate. Characterize once hardware is received. | **Awaiting provided hardware** |
| Motor torque-speed curve | How torque drops off with RPM for our specific motor. | **Motor datasheet — awaiting provided hardware** |
| TMC2209 thermal limits on SKR Pico | Board thermal limit is ~0.8A without fan, ~1.2A with active cooling. See `docs/skr_pico_specs.md`. | **Documented — verify in lab** |
| Microstepping decision | 16x (default) vs 32x vs 64x — affects resolution, max speed, and torque. | **Design decision after knowing speed/torque needs** |

---

## Summary: Critical Unknowns (Must Resolve First)

These block multiple downstream tasks:

| # | Unknown | Status | Blocks |
|---|---------|--------|--------|
| ~~1~~ | ~~What are we extruding?~~ | **RESOLVED: Metal paste via stepper-driven pump** | — |
| ~~2~~ | ~~Which pump type?~~ | **RESOLVED: Will be provided to team** — specs TBD on receipt | — |
| 3 | **Metal paste properties** | Open — viscosity, working temp, particle size | Flow rate targets, latency tolerance |
| ~~4~~ | ~~Stepper motor selection~~ | **RESOLVED: Will be provided to team** — specs TBD on receipt | — |
| 5 | **Which Pi model?** | Open — need to check inventory or purchase | Power budget, BOM, mount design, circuit layout |
| ~~6~~ | ~~Budget~~ | **RESOLVED: Not a constraint** | — |
| 7 | **Physical measurements from lab** | Open — cable lengths, mounting space, UR30 connectors | Circuit layout, BOM quantities, 3D print design |

### Suggested Order of Resolution

1. **Go to the lab** — check Pi inventory, measure cable distances, inspect UR30 connectors and mounting space, check paste properties
2. **Pick the Pi model** — Pi 4B is the safe choice (ethernet + USB + plenty of compute)
3. **Search UMich supplier catalogs** — get part numbers for BOM once components are decided
4. **Receive pump + motor** — document specs, update power budget, torque analysis, and mount designs
5. **Get metal paste datasheet** — viscosity, working temp, particle size from supplier
