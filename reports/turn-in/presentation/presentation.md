# W26 Cobot Axis
## UR30 7th Axis for Metal Paste Dispensing

**ME 472 — Mechatronics, Winter 2026**
**Willem Bell (Software / EE) · Dawood _____ (Mechanical)**
**April 24, 2026**

<!-- NOTES: 60-second hook. "The UR30 is a 6-axis collaborative robot. We built it a 7th axis — a stepper-driven pump for metal paste dispensing — that takes commands directly from the robot controller in real time. Over the next 15 minutes we'll walk through how we got there, using Bolton's seven-step design process as the backbone." -->

---

# The Need

- UR30 collaborative robot — no native mechanism for an external coordinated motion axis
- Metal-paste additive manufacturing requires a pump synchronized to TCP velocity
- Commercial UR+ accessories: expensive, proprietary, not tuned for paste
- Digital I/O alternative: on/off only — no speed synchronization
- **Goal:** external stepper axis that takes commands from the UR30 controller in real time, dispenses metal paste, reports status

<!-- NOTES: Motivation. Under-fill during acceleration, over-fill during deceleration — bead quality suffers without coordinated extrusion. No off-the-shelf solution for this in the lab. -->

---

# Problem Analysis — Bolton Step 2

- Only real-time interface out of UR30: **RTDE on TCP port 30004, 500 Hz** (register-based, no motion semantics)
- Latency tolerance: **20 ms worst-case** — at 50 mm/s TCP, that's 1.0 mm bead position error (within 1–5 mm bead width)
- Power: **2 A continuous / 3.5 A burst @ 24 V** from UR30 controller — hard limit
- Failure modes: RTDE loss, stepper stall, 24 V fault, Klipper crash, USB disconnect — all must drive safe-state within one RTDE cycle

<!-- NOTES: RTDE exposes 48 INT + 48 DOUBLE + 64 BOOL registers per direction. All coordination logic — clamping, mode handling, watchdog — lives outside the UR30. Paste dispensing is forgiving compared to FDM; that forgiveness is what makes sub-ms latency unnecessary. -->

---

# Design Specification — Bolton Step 3

- **25 functional requirements** (FR-01 through FR-25) — extrusion control, status, safety, homing, connection management
- **10 constraints** (C-01 through C-10) — power, driver limits, platform choices
- Performance targets: P95 latency < 20 ms, e-stop < 1 RTDE cycle, watchdog 500 ms
- **6 output + 5 input** RTDE registers allocated (minimal; ample headroom)
- Parameters awaiting hardware: motor current/torque, pump displacement, paste viscosity — bounded ranges only

<!-- NOTES: Full spec in docs/design_specification.md. TBD parameters are bounded with acceptable ranges so design space doesn't collapse while waiting for the motor/pump to arrive. -->

---

# Solution Space — Bolton Step 4

Three weighted-scoring trade studies:

- **Comm protocol:** RTDE vs Modbus TCP vs Primary Interface vs URScript Socket vs XML-RPC vs Dashboard
- **Firmware framework:** Klipper vs Lingua Franca
- **MCU platform:** BTT SKR Pico vs raw RP2040 Pico vs Arduino + CNC Shield vs Teensy 4.1

Each scored against criteria weighted by update rate, latency, ecosystem, development time, cost

<!-- NOTES: Full matrices in trades/*.md. Weighted scoring is important here — we had strong intuition about the winners but wanted to force ourselves to document why alternatives were rejected. -->

---

# Trade Study Results

| Decision | Winner | Score | Runner-up | Score |
|----------|--------|-------|-----------|-------|
| Comm protocol | **RTDE** | 4.85 | Modbus TCP | 3.30 |
| Firmware framework | **Klipper** | 4.70 | Lingua Franca | 1.95 |
| MCU platform | **SKR Pico V1.0** | 5.00 | Raw RP2040 Pico | 3.00 |

- RTDE: native UR30 support, 500 Hz, bidirectional
- Klipper: proven motion planning + 100 ms lookahead buffer
- SKR Pico: TMC2209 soldered, Klipper-native, on hand

<!-- NOTES: All three winners "click" together — RTDE and Klipper are both well-supported on the Raspberry Pi side, and the SKR Pico is Klipper's reference RP2040 board. The coherence is part of why the architecture works. -->

---

# Selected Architecture

```
UR30 ──RTDE/TCP 500 Hz──▶ Pi (bridge daemon + Klipper) ──USB 12 Mbps──▶ SKR Pico ──STEP/DIR──▶ TMC2209 ──▶ Stepper ──▶ Pump
```

- **UR30:** URScript on teach pendant writes 6 RTDE output registers
- **Pi:** Python bridge daemon (125 Hz) + Klipper host (100 ms lookahead) + Unix socket to klippy
- **SKR Pico (RP2040):** Klipper MCU firmware, 4x TMC2209 soldered, USB-C + 24 V in
- **Feedback:** 5 RTDE input registers (status, error code, actual rate, ready, fault)
- **Pi400:** optional HMI / SSH / Mainsail — not in the real-time loop

<!-- FIG 1 -->
<!-- NOTES: The dotted box around "Pi" hides complexity — inside it are two processes (bridge daemon, klippy) talking over a Unix socket. Pi400 was originally in the path as a slave serial bridge; we removed it after the Klipper trade made direct USB viable. -->

---

# Electrical Design

- **24 V from UR30 power block** → 3 A fuse → SMBJ24CA TVS → 100 µF bulk cap
- **Direct to SKR Pico VIN** (logic + TMC2209 VMOT)
- **Pololu D24V22F5 buck** → 5.1 V @ 2.2 A → Pi GPIO header (behind 2 A PTC polyfuse)
- Signal: Ethernet (RTDE), USB-C (Klipper serial), 4-wire motor cable
- Pin assignments: gpio14 STEP, gpio13 DIR, gpio15 EN, UART addr 3 (gpio8/9)

**Budget: 1.0 A typical / 1.4 A peak at 24 V** — fits in 2 A UR30 continuous limit with 1 A margin

<!-- FIG 3 -->
<!-- NOTES: Every protection component has a reason: fuse for catastrophic short, TVS for the UR30 power block switching transients, bulk cap for motor current pulses, polyfuse because the Pi GPIO path bypasses the onboard fuse. -->

---

# Software Architecture

- **URScript** on UR30: writes mode/rate/enable/e-stop/home to output registers at 500 Hz
- **Bridge daemon** (Python, 11 modules, **479 tests, 100 % coverage**):
    - `rtde_client` (reads) → `bridge_daemon` state machine → `klipper_client` (writes G-code)
    - `watchdog` stops stepper if no RTDE data in 500 ms
    - `extrusion_profile` — linear / polynomial / lookup-table rate shaping
    - `klipper_status` polls TMC2209 diagnostics at 20 Hz
- **Klipper** on Pi: motion planning + 100 ms MCU lookahead buffer
- **Klipper firmware** on RP2040: 16x microstepping, StealthChop mode

<!-- NOTES: Single-threaded, synchronous by design — predictable timing beats throughput. Stateless translator between two async systems. All 479 tests run in ~1.5s, no hardware needed. -->

---

# Latency Model

| Segment | Typical (ms) | Worst (ms) |
|---------|-------------:|-----------:|
| UR30 RTDE cycle | 0–2 | 4 |
| Ethernet + switch | 0.1–0.5 | 1 |
| Bridge (Python) | 0.5–2 | 5 |
| Klipper host | 0.5–2 | 5 |
| USB serial | 1–3 | 5 |
| MCU step gen | <0.1 | 0.5 |
| **Total** | **~5–8** | **~20** |

- 20 ms × 50 mm/s = **1.0 mm** bead position error — within tolerance
- Klipper's 100 ms lookahead *adds* latency but **eliminates step-timing jitter**

<!-- FIG 8 -->
<!-- NOTES: The Klipper lookahead is a latency/precision tradeoff we chose intentionally — at the MCU level, step timing is microsecond-precise even though the Linux host has 1-10 ms scheduling jitter. -->

---

# Stretch Goal: StallGuard Torque Feedback

- TMC2209 has a **DIAG pin** that asserts in microseconds when load crosses the StallGuard threshold
- Klipper polls over UART at ~4 Hz — **250 ms blind window** for stall damage
- **Our solution:** dedicated firmware on RP2040's idle **Core1**
    - Core1 monitors DIAG pin in hardware, debounces, stores event + timestamp in shared SRAM
    - Core0 (Klipper) serves `stallguard_query` / `stallguard_clear` MCU commands
    - Klippy extras module polls at 20 Hz → RTDE input register → URScript can halt robot on stall
- Safe spinlock #16, zero impact on Klipper step timing
- Validated by `docs/design/hitl_plan.md` TP-06

<!-- NOTES: This also satisfies the "sensors" element of the ME472 course prompt. The DIAG signal path is hardware-speed detection that survives the 250ms poll gap. -->

---

# Testing and Validation

- **Functional:** `test_basic.script` — 9 sub-tests (init, enable, extrude, retract, home, e-stop, speed-sync, fault, status)
- **Latency:** oscilloscope from UR30 digital output to SKR Pico gpio14 step pulse
- **Accuracy:** commanded vs measured rate @ 5, 10, 25, 50 mm/s; gravimetric paste dispensed
- **Fault injection:** RTDE disconnect, Klipper shutdown, stall, power loss
- **Stretch:** StallGuard HITL (TP-06) — DIAG event reaches URScript in ≤ 100 ms
- CI/CD: Tier 1 lint+test+shellcheck on every commit; Tier 2 firmware cross-compile; weekly patch-freshness against upstream Klipper

<!-- NOTES: All software testing is mock-based — 479 tests run in 1.5s with zero hardware. Hardware-dependent tests wait on the motor/pump delivery. -->

---

# Results vs Specification

| Target | Result |
|--------|--------|
| End-to-end latency < 20 ms P95 | 5–8 ms predicted; measurement deferred to Phase 4 |
| E-stop response < 2 ms | Implemented; measurement deferred |
| Watchdog < 500 ms | Implemented, 100 % tested |
| Power draw < 2 A @ 24 V | 1.0 A typ / 1.4 A peak predicted |
| Speed accuracy < 5 % | Deferred to hardware |
| 479 unit tests @ 100 % coverage | **Achieved** |

**Status:** software and firmware complete; hardware integration pending motor/pump delivery

<!-- NOTES: Hedge honestly — we have a fully validated software stack, a detailed electrical design, and a stretch-goal firmware overlay that's written and unit-tested, but we don't yet have measured latency numbers on the real motor. -->

---

# Lessons Learned — Bolton Process in Practice

- Step 2 ↔ Step 4 iteration was real: the original "slave Pi as serial bridge" architecture died once the Klipper trade study made direct USB viable → saved 0.12 A, one point of failure
- Specification tightened after driver research: TMC2209 is **thermally limited to 0.8 A** without cooling, not 1.2 A — forced a cooling-fan line item
- Hardware-free development is viable: `FakeKlippy` mocks + `ur_rtde` stub → 479 tests run with zero hardware in 1.5 s
- CI/CD pays for itself: patch-freshness workflow catches Klipper upstream drift weekly before it breaks our overlay

<!-- NOTES: The Bolton iteration is a feature, not a defect. We wrote about this explicitly in Section H of the report — the specification is better for having been revised. -->

---

# Future Work

- Full pump + paste characterization on delivered hardware
- Measured latency + accuracy numbers (Phase 4 completion)
- Multi-material support (swap paste cartridges mid-print)
- URCap for teach-pendant UI (Java SDK, not needed for MVP)
- Predictive G-code timeshifting using Klipper's 100 ms lookahead buffer
- Production StallGuard tuning with real paste loads

<!-- NOTES: The capstone ends April 23, but the project has a life beyond — particularly the multi-material and URCap work that a future team could pick up. -->

---

# Thank You — Questions?

**Repo:** github.com/wrbell/W26-Cobot-Axis
**Team:** Willem Bell (Software/EE) · Dawood _____ (Mechanical)
**Advisor:** Prof. Pannier

Key references:
- W. Bolton, *Mechatronics*, 7th ed., Pearson, 2019
- SDU Robotics, *ur_rtde* library
- Klipper3D documentation
- BTT SKR Pico V1.0 user manual; Trinamic TMC2209 datasheet

<!-- NOTES: Leave 2-3 minutes for Q&A. Likely question topics: latency measurement methodology, why Klipper over ROS/custom, metal paste specifics (defer to instructor-provided info), safety story under fault conditions. -->

---

# Backup: Bill of Materials

| Category | Items | Cost |
|----------|------:|-----:|
| Electronics (Pi, buck, switch, cables) | 7 | $148.79 |
| Protection + passives | 6 | $3.65 |
| Wiring + connectors | 7 | $30.45 |
| On hand (SKR Pico, Pi 400, PSU) | 3 | $0 |
| Provided (motor, pump) | 2 | $0 |
| 3D-printed (enclosure, mount, clips) | 3 | $0 |
| **Total** | **28** | **~$183** |

Full BOM with DigiKey/Newark part numbers: `docs/phase2/bom.md`

---

# Backup: Power Budget

| Device | Idle | Typical | Peak | Notes |
|--------|-----:|--------:|-----:|-------|
| Pi (via buck, 90% eff) | 0.15 A | 0.35 A | 0.45 A | 1.5 A @ 5.1 V design |
| SKR Pico (logic) | 0.05 A | 0.08 A | 0.10 A | RP2040 + TMC2209 quiescent |
| Stepper motor | 0.10 A | 0.50 A | 1.00 A | TBD placeholder NEMA 17 |
| Cooling fan (opt.) | 0.00 A | 0.04 A | 0.08 A | If TMC2209 cooling required |
| **Total** | **0.30 A** | **~0.97 A** | **~1.63 A** | vs 2.0 A / 3.5 A UR30 budget |

---

# Backup: RTDE Register Map

**UR30 → Pi (output)**
- `output_int_register_0` — extrusion mode (0/1/2)
- `output_double_register_0` — commanded rate (mm/s)
- `output_double_register_1` — TCP speed (mm/s)
- `output_bit_register_64/65/66` — enable / e-stop / home

**Pi → UR30 (input)**
- `input_int_register_0` — status (0 idle / 1 running / 2 error / 3 homing)
- `input_int_register_1` — error code (0/1/2/3)
- `input_double_register_0` — actual rate (mm/s)
- `input_bit_register_64/65` — ready / fault

Reserved: StallGuard load, driver temperature, position target
