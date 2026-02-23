# Week-by-Week Plan

**Team:** Willem (software/EE), Dawood (mechanical)
**Today:** Feb 23, 2026 (Week 8)
**Target completion:** Mar 31 | **Report due:** Apr 23 | **Presentation:** Apr 24

Update this doc each Sunday — check off what's done, carry forward what slipped.

---

## Week 8: Feb 23–Mar 1 — Phase 2 Memo Submission

**Deadline: Phase 2 memo due Mar 1**

Willem:
- [ ] Redraw block diagram in draw.io → export PNG (Figure 1)
- [ ] Redraw circuit schematic in KiCad or draw.io → export PNG (Figure 2)
- [ ] Paste memo text from `docs/phase2/memo_draft.md` into Word template (Office 365)
- [ ] Insert all 5 tables and Figures 1–2 with captions
- [ ] Set up URSim Docker on a Windows/Linux x86 machine (amd64 only)

Dawood:
- [ ] Write Section 5: mechanical concept (~150 words)
- [ ] Create Figure 3 (physical layout sketch) and Figure 4 (mechanical concept)
- [ ] Brief location trade study rationale (end effector vs base-mounted)

Together (Feb 28–Mar 1):
- [ ] One person edits entire document for consistency
- [ ] Verify page count ≤ 5, export PDF, submit

---

## Week 9: Mar 2–8 — Spring Break: Hardware Bring-Up

**No classes — dedicated build time.** Goal: stepper spinning under Klipper control.

Willem (Stages 1–3):
- [ ] Flash MainsailOS onto Pi SD card, boot, verify SSH
- [ ] Verify Klipper + Moonraker services running, Mainsail web UI responds
- [ ] Build Klipper firmware for SKR Pico (RP2040, USB)
- [ ] Flash firmware via BOOTSEL, verify USB serial enumeration
- [ ] Deploy `printer.cfg`, restart Klipper → "Printer is ready"
- [ ] Wire stepper to E-axis connector (identify coils with multimeter)
- [ ] Apply 24V, send test G-code → **first stepper motion** (the milestone)
- [ ] Test speeds: 5, 25, 50 mm/s; verify direction

Willem (Stage 4 — if time):
- [ ] Read motor nameplate, set `run_current` to 70–80%
- [ ] Sustained motion test, monitor TMC2209 temperature
- [ ] `DUMP_TMC` — verify no error flags
- [ ] Commit updated `printer.cfg`

Dawood:
- [ ] Begin 3D printing mounting components
- [ ] Identify all parts that need printing, start CAD

Willem (URSim — parallel if x86 machine available):
- [ ] Load slicer output (`Mblack0.6mm.script`) into URSim
- [ ] Verify path executes cleanly (no joint limits, no singularities)
- [ ] Test bridge daemon against URSim RTDE on port 30004

---

## Week 10: Mar 9–15 — Bridge + RTDE Integration

Willem (Stage 5):
- [ ] Clone repo onto Pi, install `ur-rtde`
- [ ] Test bridge daemon dry-run on Pi
- [ ] Test Klipper connection directly (bypass RTDE) — motor moves from Python

Willem (Stage 6):
- [ ] Verify network to UR30: `ping`, port 30004 reachable
- [ ] Update `config.py` with UR30 IP
- [ ] Test RTDE register read/write independently
- [ ] Load `extrusion_control.script` onto UR30 teach pendant
- [ ] Run bridge daemon with RTDE, verify 125 Hz register cycles

Dawood:
- [ ] Continue mechanical assembly: electronics mounting, cable routing
- [ ] Start end effector mounting design

---

## Week 11: Mar 16–22 — End-to-End + Slicer Integration

**Goal: full chain working — UR30 command → stepper moves.**

Willem (Stage 7):
- [ ] All services running: Klipper + Moonraker + bridge + URScript
- [ ] UR30: enable + EXTRUDE + rate=10 → **stepper moves** (the real milestone)
- [ ] Test speed ramp 0→50 mm/s, mode transitions, e-stop
- [ ] Run `test_basic.script` Sub-tests A–F, I (no-motion tests)
- [ ] Teach waypoints, run Sub-test G (constant-rate multi-waypoint)

Willem (Stage 7b):
- [ ] Wrap slicer output with `pump_on()`/`pump_off()`
- [ ] Load onto UR30, run with bridge active → pump runs during 776 waypoints
- [ ] Run `test_calibration.script` Sub-tests A and B2

Dawood:
- [ ] Mount electronics onto robot / end effector
- [ ] Route and secure all cabling
- [ ] Attach pump to stepper output shaft

Together:
- [ ] **Phase 3 progress memo** — fill in test results from this week
- [ ] Submit progress memorandum

---

## Week 12: Mar 23–29 — Formal Testing

Willem:
- [ ] **TP-01: Functional test** (45 min) — all modes, rate clamping, e-stop, homing
- [ ] **TP-02: Latency** (90 min) — RTDE timestamps, oscilloscope if available
- [ ] **TP-03: Speed accuracy** (60 min) — commanded vs actual at 5/10/20/30/50 mm/s
- [ ] Capture oscilloscope screenshots and log files for report figures
- [ ] Tune `EXTRUSION_MULTIPLIER` and retraction params from calibration data

Dawood:
- [ ] Photograph prototype at each testing stage (for report figures)
- [ ] Record video of working demo (for presentation)
- [ ] Final mechanical adjustments based on test results

Together:
- [ ] Review test results — any retests needed?

---

## Week 13: Mar 30–Apr 5 — Remaining Tests + Start Report

Willem:
- [ ] **TP-04: Fault handling** (75 min) — Ethernet pull, stall, Klipper crash, USB disconnect
- [ ] **TP-05: Endurance** (90 min) — 60-min continuous run, temperature monitoring
- [ ] Run full `test_basic.script` and `test_calibration.script` on hardware
- [ ] Commit final `printer.cfg`, any code fixes from testing
- [ ] **Start report outline** — map sections to Bolton's 7 steps

Dawood:
- [ ] Start writing mechanical sections of report
- [ ] Final prototype photos with labels

Together:
- [ ] Compile all test data into tables/figures
- [ ] **Mar 31 target: functional prototype complete**

---

## Week 14: Apr 6–12 — Report Writing

Willem:
- [ ] Write report sections: introduction, problem analysis, design specification, software design, electrical design, testing results, conclusions
- [ ] Create figures: latency histogram (TP-02), speed accuracy chart (TP-03), block diagram, circuit schematic, system photo
- [ ] Insert all tables: register allocation, BOM summary, test results

Dawood:
- [ ] Write sections: mechanical design, physical layout, assembly
- [ ] Create figures: mechanical sketches, cable routing, end effector photos

Together:
- [ ] Merge drafts into single Word doc (Office 365 shared editing)
- [ ] Check word count (≤ 2000 words, figures/tables don't count)
- [ ] Add references and in-text citations

---

## Week 15: Apr 13–19 — Report Finalization + Presentation Prep

Together:
- [ ] One person edits entire report for consistency and technical writing
- [ ] Verify all figures are high-resolution (avoid Google Docs resizing issues)
- [ ] Use Word Styles (headings, captions)
- [ ] Include team member work listing
- [ ] Attach supplementary materials: code, drawings, configs
- [ ] Prepare presentation slides (10–15 min)
- [ ] Practice design defense — anticipate questions about:
  - Why Klipper over Lingua Franca?
  - Why RTDE over other protocols?
  - Latency performance vs prediction
  - Safety/fault handling approach

---

## Week 16: Apr 20–24 — Submit + Present

- [ ] **Apr 23 (Thu 6:00 PM): Submit final report PDF** + supplementary files
- [ ] **Apr 24 (Thu 6:30–9:30 PM): Oral presentation + design defense**
- [ ] Bring prototype for live demonstration
- [ ] Have backup video in case live demo fails

---

## Risk Triggers

If any of these happen, reassess the plan:

| Trigger | Response |
|---------|----------|
| Parts not arrived by Mar 2 | Order expedited; use Spring Break for URSim-only testing |
| Stepper won't spin by Mar 8 | Debug Klipper config; worst case, swap SKR Pico |
| No UR30 access by Mar 9 | Continue with URSim; defer RTDE testing |
| Bridge daemon won't connect by Mar 15 | Use stub/dry-run mode; isolate which link is failing |
| Tests fail badly in Week 12 | Prioritize TP-01 (functional); skip TP-05 (endurance) if needed |
| Report over 2000 words | Cut mechanical detail, move to appendix |
