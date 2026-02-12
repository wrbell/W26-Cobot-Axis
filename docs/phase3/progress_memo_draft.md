# Phase 3 Progress Memo -- Draft Text

**For:** Phase 3 submission (PDF, progress update memorandum)
**Project:** W26 Cobot Axis -- UR30 7th Axis for Metal Paste Dispensing
**Course:** ME 472 -- Mechatronics, Winter 2026, University of Michigan
**Team:** Willem (Software/EE), Dawood (Mechanical)
**Deadline:** Mar 22, 2026
**Status:** Draft -- ready for review and hardware-dependent sections to be filled

---

## Header (Top of Page 1)

**TO:** Prof. Pannier
**FROM:** Willem _____, Dawood _____
**DATE:** March 22, 2026
**RE:** W26 Cobot Axis -- Phase 3 Progress Update

---

## Section 1: Progress Summary (~200 words)

This memo reports on the build and integration progress for the W26 Cobot Axis project during Phase 3 (Weeks 9--11, March 2--22). The goal of Phase 3 was to bring up the hardware, integrate the full signal chain from the UR30 controller through the Raspberry Pi and SKR Pico to the stepper motor, and verify basic end-to-end operation.

During Spring Break (Week 9), we focused on hardware bring-up: flashing Klipper firmware onto the SKR Pico, installing Klipper and Moonraker on the Raspberry Pi, wiring the stepper motor, and achieving first motion via G-code commands. Weeks 10--11 were dedicated to deploying the RTDE bridge daemon, establishing communication with the UR30 controller, and running end-to-end integration tests.

[Adjust the following sentence to reflect actual status at time of submission:]

As of March 22, we have completed Stages 1 through [N] of the 8-stage integration plan. The system [is / is not yet] capable of end-to-end operation where a URScript command on the UR30 results in stepper motor motion at the requested speed. The remaining stages are [on track / at risk] for completion before Phase 4 testing begins on March 23.

---

## Section 2: Design Changes Since Phase 2 (~150 words)

[Update this section based on any changes made during build. If no changes were necessary, state that the Phase 2 design was implemented as specified. Below are common changes that may apply:]

The Phase 2 design was implemented largely as specified, with the following modifications discovered during hardware bring-up:

**Raspberry Pi model selection:** [State which Pi model was used -- e.g., Pi 4B 4GB. This was listed as TBD in Phase 2.]

**Motor current tuning:** The stepper motor provided by the instructor is [model/specs]. Based on its rated current of [X] A per phase, the TMC2209 run current was set to [Y] A (approximately [Z]% of rated), compared to the conservative 0.58 A placeholder used in Phase 2. [State whether StealthChop or SpreadCycle was selected and why.]

**Rotation distance:** The `rotation_distance` parameter in `printer.cfg` was updated from the placeholder value of 40 mm/rev to [actual value] mm/rev based on the pump displacement of [X] mL/rev and the desired volumetric-to-linear mapping.

[If no changes: "No significant design changes were required during Phase 3. The system architecture, electrical design, power distribution, and software stack described in the Phase 2 memo were implemented as specified."]

---

## Section 3: Build Status (~200 words) + Table 1

The integration plan defined eight sequential stages. Table 1 summarizes the status of each stage as of March 22.

### Table 1: Integration Stage Status

| Stage | Description | Target Week | Status | Notes |
|-------|-------------|-------------|--------|-------|
| 1 | Klipper on Pi | Week 9 | [Complete / In Progress / Blocked] | [Notes -- e.g., "MainsailOS flashed, SSH verified"] |
| 2 | SKR Pico firmware | Week 9 | [Complete / In Progress / Blocked] | [Notes -- e.g., "UF2 flashed, USB serial enumerated"] |
| 3 | Stepper motion | Week 9 | [Complete / In Progress / Blocked] | [Notes -- e.g., "Motor moves on G-code command"] |
| 4 | TMC2209 tuning | Week 9 | [Complete / In Progress / Blocked] | [Notes -- e.g., "Run current set to X A, thermal OK"] |
| 5 | Bridge daemon | Week 9 | [Complete / In Progress / Blocked] | [Notes -- e.g., "Daemon connects to Klipper, commands stepper"] |
| 6 | RTDE connection | Week 10 | [Complete / In Progress / Blocked] | [Notes -- e.g., "Register read/write verified with UR30"] |
| 7 | End-to-end | Week 10--11 | [Complete / In Progress / Blocked] | [Notes -- e.g., "UR30 extrude command drives stepper"] |
| 8 | Pi400 HMI | Week 11 | [Complete / In Progress / Blocked] | [Notes -- e.g., "Mainsail accessible from Pi400"] |

**Hardware received:** [List all hardware received and its condition. Note any items still pending.]

- Raspberry Pi [model]: [received / on hand / pending]
- SKR Pico V1.0: on hand (from Phase 1)
- Stepper motor: [received -- model and specs / pending from instructor]
- Pump: [received -- type and specs / pending from instructor]
- Gigabit switch: [received / borrowed from lab]
- 24V power supply: [bench supply from lab / UR30 power block]

---

## Section 4: Integration Testing Results (~200 words) + Table 2

[This section reports results from end-to-end testing. Fill in after bench testing is complete.]

### 4a. Stepper Motion Verification (Stage 3)

[Results to be filled after bench testing.]

The stepper motor was wired to the SKR Pico E-axis driver socket and tested with manual G-code commands via the Mainsail console. The following test cases were executed:

| Test | Command | Expected Result | Actual Result |
|------|---------|-----------------|---------------|
| Forward motion | `MANUAL_STEPPER STEPPER=pump MOVE=10 SPEED=5` | Motor rotates [X] degrees | [Result] |
| Reverse motion | `MANUAL_STEPPER STEPPER=pump MOVE=-10 SPEED=5` | Motor reverses | [Result] |
| Speed ramp | `MOVE=80 SPEED=50` | Motor runs at max speed | [Result] |
| Disable | `ENABLE=0` | Motor de-energizes | [Result] |

### 4b. End-to-End Command Chain (Stage 7)

[Results to be filled after UR30 integration.]

The full signal chain was tested with the URScript `test_basic.script` validation program, which exercises nine sub-tests: initialization, enable/disable, extrude, retract, homing, emergency stop, speed-proportional mode, fault handling, and status readback.

| Sub-Test | Result | Latency (ms) | Notes |
|----------|--------|-------------|-------|
| Initialization | [Pass/Fail] | -- | [Notes] |
| Enable/Disable | [Pass/Fail] | -- | [Notes] |
| Extrude at 10 mm/s | [Pass/Fail] | [Measured] | [Notes] |
| Retract at 10 mm/s | [Pass/Fail] | [Measured] | [Notes] |
| Homing | [Pass/Fail] | -- | [Notes] |
| E-stop | [Pass/Fail] | [Measured] | [Notes] |
| Speed-sync extrusion | [Pass/Fail] | -- | [Notes] |
| Fault handling (RTDE disconnect) | [Pass/Fail] | -- | [Notes] |
| Status readback on UR30 | [Pass/Fail] | -- | [Notes] |

### 4c. Latency Measurement

[Results to be filled if oscilloscope measurement was performed during Phase 3. Otherwise, defer to Phase 4.]

End-to-end latency was [measured with an oscilloscope / estimated from software timestamps / deferred to Phase 4]. [If measured:] The observed latency from UR30 register write to first stepper step pulse was [X] ms typical, compared to the design target of 5--20 ms.

### Table 2: Key Measured Parameters

| Parameter | Design Target | Measured Value | Status |
|-----------|--------------|----------------|--------|
| End-to-end latency (typical) | 5--10 ms | [TBD] | [Met / Not met / Deferred] |
| End-to-end latency (worst case) | < 20 ms | [TBD] | [Met / Not met / Deferred] |
| Motor run current | [Motor rated] | [Set value] A | [Configured] |
| TMC2209 temperature (sustained) | < 80 C | [TBD] C | [OK / Requires cooling] |
| Max extrusion speed achieved | 50 mm/s | [TBD] mm/s | [Met / Limited by motor] |
| Power draw (typical) | ~1.0 A @ 24V | [TBD] A | [Within budget / Over budget] |
| Watchdog timeout response | 500 ms | [TBD] ms | [Met / Not met / Deferred] |

---

## Section 5: Issues and Risks (~150 words)

[Update based on actual issues encountered. Below are templates for common issues:]

**Issue 1: [Title -- e.g., Motor/pump not yet received]**
[Description of the issue, its impact on the schedule, and the workaround or resolution. Example: "The stepper motor and pump were not received until Week 10, compressing the integration timeline. We used a spare NEMA 17 motor for Stages 1--4 and re-tuned the current settings when the actual motor arrived."]

**Issue 2: [Title -- e.g., ur-rtde library installation on ARM]**
[Description. Example: "The ur-rtde Python library required compilation from source on the Raspberry Pi's ARM processor. Installing the build dependencies (libboost, cmake) added approximately 1 hour to the setup. The bridge daemon's stub fallback mode was useful for parallel development while the library compiled."]

**Issue 3: [Title -- e.g., UR30 lab access during Spring Break]**
[Description. Example: "The UR30 was not accessible during Spring Break (Week 9), so RTDE integration (Stage 6) was deferred to Week 10. Stages 1--5 were completed independently using the bench power supply."]

**Remaining risks for Phase 4:**
- [Risk 1 -- e.g., "Pump torque requirements not yet characterized under paste load"]
- [Risk 2 -- e.g., "Latency has not been measured with an oscilloscope; software timestamps may not capture worst-case jitter"]
- [Risk 3 -- e.g., "Mechanical assembly and cable routing not yet finalized for robot-mounted operation"]

---

## Section 6: Next Steps -- Phase 4 Testing Plan (~150 words)

Phase 4 (Weeks 12--13, March 23 -- April 5) focuses on systematic testing, characterization, and documentation. Our target is to complete all testing by March 31, reserving the final week for report writing.

**Week 12 (Mar 23--29): System Testing**
- End-to-end functional test under robot arm motion (UR30 moves along a path while commanding extrusion)
- Latency characterization with oscilloscope: measure time from UR30 digital output toggle to first step pulse on SKR Pico gpio14
- Speed accuracy test: commanded vs. actual extrusion rate at 5, 10, 25, and 50 mm/s
- Fault injection tests: RTDE disconnect, Klipper shutdown, motor stall (if pump loaded), power interruption

**Week 13 (Mar 30 -- Apr 5): Documentation**
- Endurance test: 30-minute continuous extrusion run to verify thermal stability and reliability
- Compile test results with data plots and tables
- Begin drafting the final report (due April 23, max 2000 words)
- Prepare oral presentation materials (April 24, 6:30--9:30 PM)

**Stretch goals** (if core testing completes early):
- StallGuard torque feedback from TMC2209 to UR30 via RTDE
- G-code timeshifting to compensate for Klipper's ~100 ms lookahead buffer latency

---

## Word Formatting Notes

- Use **Word Styles**: Heading 1 for section titles, Body Text for paragraphs, Caption for table captions
- Tables as compact as possible; use same formatting as Phase 2 memo
- Font: 11pt body text, 10pt for tables and captions
- Page margins: 1" all sides (Word default)
- **Target length: ~1,000 words** (progress update, shorter than Phase 2's ~1,400 words)
- **Target pages: 2--3** (including tables)
- Compile in Microsoft Word via UMich Office 365

---

## Notes for Authors

This draft contains placeholder brackets `[like this]` throughout. Before submitting:

1. Fill in all `[bracketed placeholders]` with actual results from hardware testing
2. Delete any template options that do not apply (e.g., choose between "received" and "pending")
3. Remove Section 2 alternative text (keep either the "changes made" or "no changes" paragraph)
4. Remove this "Notes for Authors" section
5. Remove the "Word Formatting Notes" section
6. Add last names to the FROM line
7. Have one team member edit the entire memo for consistency before submission
