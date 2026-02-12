# Trade Study: Lingua Franca vs Klipper

**Project:** W26 Cobot Axis -- ME 472 Winter 2026
**Author:** Willem (Software/EE Lead)
**Date:** 2026-02-12
**Status:** RECOMMENDATION READY
**Originator:** Pannier Review feedback (Canvas); instructor suggested Lingua Franca as a candidate framework

---

## 1. Purpose

This trade study evaluates two candidate software frameworks for controlling a stepper motor (extrusion axis) commanded by a Universal Robots UR30 cobot:

| Option | Description |
|--------|-------------|
| **Klipper** | Mature open-source 3D printer firmware ecosystem. Host process runs on a Raspberry Pi, communicates with an RP2040-based MCU over serial, and manages step timing, kinematics, G-code parsing, and TMC driver support. |
| **Lingua Franca (LF)** | Polyglot coordination language developed at UC Berkeley (and collaborators including UMich) for building deterministic, real-time reactive systems. Programs are composed of *reactors* with formally specified timing semantics. Compiles to C, C++, Python, TypeScript, or Rust. |

The instructor flagged Lingua Franca via Canvas feedback as a technology worth investigating. This document provides the engineering basis for the framework selection decision.

---

## 2. System Context

```
UR30 Controller ──RTDE/TCP-IP──> Pi400 (Host) ──Serial──> BigTreeTech Pico (RP2040) ──> Stepper Motor
   (URScript)                    (framework)               (firmware)                    (extrusion)
```

**Hardware constraints:**
- Host: Raspberry Pi 400 (quad-core ARM Cortex-A72, Linux)
- MCU: BigTreeTech Pico (RP2040, dual Cortex-M0+ at 133 MHz, 264 KB SRAM)
- Actuator: NEMA-style stepper motor, ~24V, likely with TMC driver IC on the BTT Pico board
- Comms: RTDE over Ethernet (UR30 to Pi), Serial/USB (Pi to MCU)

**Functional requirements:**
1. Receive extrusion commands from UR30 via RTDE
2. Translate commands into stepper motor motion (position/velocity control)
3. Drive stepper via step/dir signals or SPI-configured TMC driver
4. (Stretch) Report Stallguard torque data back to URScript

**Schedule constraint:** ~8 weeks accelerated timeline; functional prototype needed by Mar 31, 2026.

---

## 3. Candidate Overview

### 3.1 Klipper

Klipper is a widely-deployed open-source 3D printer firmware project (first released ~2016, thousands of active users, active GitHub with 9,000+ stars and 200+ contributors). Its defining architectural insight is splitting work between a Linux host and a lean MCU:

- **Host side (Python, runs on Pi):** Parses G-code, computes kinematic moves, plans acceleration/deceleration trapezoids, and pre-computes a time-stamped sequence of step events. Sends these events to the MCU well ahead of their execution deadlines.
- **MCU side (C, runs on RP2040):** Receives pre-computed step commands over serial. Executes them at precise clock times using hardware timers. The MCU code is intentionally minimal -- it is essentially a real-time step executor.
- **Clock synchronization:** Klipper synchronizes the host clock with the MCU clock, allowing the host to schedule events in the MCU's time domain. This achieves step timing precision in the low-microsecond range despite the host running non-real-time Linux.
- **RP2040 support:** First-class. Klipper's MCU firmware compiles for RP2040 and is used in production by the 3D printing community on BTT Pico boards specifically.
- **TMC driver support:** Built-in SPI/UART configuration for TMC2209, TMC2130, TMC5160, and others. Stallguard and sensorless homing are supported features.
- **Extensibility:** Klipper supports custom G-code macros (Jinja2 templating), custom kinematic modules (Python), and an API layer (Moonraker) for external control over HTTP/WebSocket/JSON-RPC.

**Key strength for this project:** Klipper is designed from the ground up for exactly the job we need -- driving a stepper motor from a host computer through an RP2040 MCU. The entire motor control stack (step generation, acceleration planning, TMC configuration, serial protocol) already exists and is production-tested.

### 3.2 Lingua Franca

Lingua Franca (LF) is a coordination language developed primarily by Edward A. Lee's group at UC Berkeley, with collaborators at UT Dallas, TU Dresden, and elsewhere. It is a research project with academic publications (PLDI, DATE, etc.) and an open-source compiler/runtime (GitHub: lf-lang/lingua-franca, ~300 stars).

**Core concepts:**
- **Reactor model:** Programs are composed of *reactors* -- concurrent components with typed input/output *ports*, *state variables*, *timers*, and *reactions* (event handlers). Reactors communicate by sending *messages* through connections between ports.
- **Logical time:** Every event has a *logical timestamp*. The runtime guarantees that reactions execute in timestamp order, providing *deterministic concurrency* -- the same inputs always produce the same outputs regardless of physical execution timing.
- **Physical time binding:** LF can bind logical time to physical (wall-clock) time, with configurable deadlines. If a reaction misses its physical-time deadline, a *deadline handler* executes instead. This provides a formal model for reasoning about real-time behavior.
- **Target languages:** LF is a *coordination* language, not a general-purpose language. The body of each reaction is written in a *target language* (C, C++, Python, TypeScript, or Rust). The LF compiler generates a complete program in the target language that includes the runtime scheduler.
- **Compilation:** `.lf` source files are compiled by `lfc` (the LF compiler) into target-language source, which is then compiled by the native toolchain (e.g., `gcc` for C targets).

**Embedded/RP2040 support status:**
- LF's C runtime (`reactor-c`) is the most mature target for embedded use. It can run bare-metal or on RTOS platforms (Zephyr RTOS is the primary supported embedded platform).
- **RP2040 support is not a primary target.** The LF project has demonstrated builds on some ARM Cortex-M platforms via Zephyr, but the RP2040 is not among the prominently documented or tested boards. Getting LF running on bare-metal RP2040 would require porting the `reactor-c` runtime to the Pico SDK or getting Zephyr's RP2040 board support working with LF, both of which are non-trivial integration tasks with limited community precedent.
- On the Pi 400 (Linux host), LF's C or Python targets would work without issue. The challenge is the MCU side.

**What LF does NOT provide:**
- No stepper motor control library
- No step timing / acceleration planning
- No TMC driver configuration
- No serial protocol between host and MCU
- No G-code or motion command parsing
- No clock synchronization between host and MCU

All of the above would need to be designed and implemented from scratch.

---

## 4. Evaluation Criteria

Criteria are weighted based on the project's constraints: a compressed 8-week schedule, a two-person team (one software lead), and the need for a functional prototype controlling a stepper motor.

| # | Criterion | Weight | Description |
|---|-----------|--------|-------------|
| C1 | **Time to functional prototype** | 30% | How quickly can we get a stepper motor spinning under host control? |
| C2 | **Stepper control capability** | 20% | Quality of step timing, acceleration planning, and TMC driver support |
| C3 | **RP2040 platform support** | 15% | Maturity of MCU-side toolchain, build system, and runtime |
| C4 | **Real-time guarantees** | 10% | Formal or practical guarantees on timing determinism |
| C5 | **Extensibility for RTDE integration** | 10% | Ease of adding a custom UR30 RTDE interface on the host side |
| C6 | **Community and documentation** | 10% | Availability of help, examples, and debugging resources |
| C7 | **Academic/pedagogical value** | 5% | Alignment with ME 472 learning objectives and instructor interest |

---

## 5. Scoring

Each candidate is scored 1--5 per criterion (5 = best).

### C1: Time to Functional Prototype (Weight: 30%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **Klipper** | **5** | Install Klipper on Pi, flash MCU firmware, write a `printer.cfg`, send a G-code move command. A stepper can be spinning in under a day. The BTT Pico is a known-supported board with existing config examples. |
| **Lingua Franca** | **1** | Must: (a) port reactor-c runtime to RP2040 or configure Zephyr+LF for RP2040, (b) implement a serial protocol between host and MCU, (c) implement step pulse generation with precise timing, (d) implement acceleration planning, (e) implement TMC SPI configuration. This is months of embedded systems work for an experienced developer; it is infeasible in 8 weeks for a student team. |

### C2: Stepper Control Capability (Weight: 20%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **Klipper** | **5** | Production-grade stepper control with trapezoidal acceleration, pressure advance (useful for extrusion), input shaping, configurable microstepping, and TMC UART/SPI configuration including Stallguard, CoolStep, and StealthChop. Step timing jitter is typically <10 us. |
| **Lingua Franca** | **1** | No motor control exists. Would need to write step generation ISRs in C within reactor bodies. LF's logical-time model could in principle coordinate step events, but translating that into sub-microsecond step pulse timing on RP2040 hardware timers requires deep embedded expertise and significant development effort. The result would be far less capable than Klipper's existing implementation. |

### C3: RP2040 Platform Support (Weight: 15%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **Klipper** | **5** | RP2040 is a first-class Klipper MCU target. The build system (`make menuconfig`) has an RP2040 option. BTT Pico is a popular Klipper board with community-maintained configs. Flashing is via USB boot mode (hold BOOTSEL, drag UF2). Thousands of users run this exact combination. |
| **Lingua Franca** | **2** | LF's embedded C target works on Zephyr RTOS, which does have RP2040 board support, but LF+Zephyr+RP2040 is not a well-trodden path. The LF documentation primarily demonstrates embedded targets on NRF52, STM32, and RISC-V boards. Bare-metal RP2040 (Pico SDK) would require manual porting of the reactor-c platform abstraction layer. Either path involves significant integration risk. |

### C4: Real-Time Guarantees (Weight: 10%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **Klipper** | **4** | Klipper achieves real-time step execution through architectural design rather than formal guarantees. The host pre-computes and buffers step events; the MCU executes them from a hardware timer ISR. In practice, step timing is deterministic at the MCU level because the MCU code path is simple and interrupt-driven. The host side is not real-time (Linux), but this is by design -- the buffering decouples host jitter from step execution. This is "real-time by architecture" and works well in practice. |
| **Lingua Franca** | **4** | LF provides *formal* deterministic concurrency via its logical-time model. Deadline handlers give a structured way to detect timing violations. On a bare-metal or RTOS target, LF's scheduler can achieve hard real-time behavior. However, this is a property of the *framework*, not of any motor control code (which does not exist). The formal guarantees are valuable in safety-critical systems but add complexity without practical benefit for a stepper extrusion axis where Klipper's empirical timing is more than adequate. Scored equal because both approaches can achieve the required timing; LF's formalism is theoretically stronger but practically unnecessary here. |

### C5: Extensibility for RTDE Integration (Weight: 10%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **Klipper** | **4** | Klipper's host is Python-based and extensible. The Moonraker API layer exposes printer control over HTTP/WebSocket/JSON-RPC. A custom Python service on the Pi can receive RTDE data from the UR30 and send G-code commands to Klipper via Moonraker or directly via Klipper's Unix socket API. This is a well-understood integration pattern. The one limitation is that Klipper is designed around G-code, so translating RTDE velocity/position commands into G-code moves requires a translation layer, but this is straightforward. |
| **Lingua Franca** | **3** | LF's reactor model is well-suited to composing RTDE parsing, command translation, and motor control into a single coordinated program. TCP/IP sockets can be handled in C or Python reactor bodies. However, every piece of this integration must be built from scratch. The *architecture* is clean, but the *implementation effort* is enormous. |

### C6: Community and Documentation (Weight: 10%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **Klipper** | **5** | Large active community (Discord, Reddit r/klipperfw, GitHub Discussions). Extensive documentation at klipper3d.org. Hundreds of printer configs available as references. BTT Pico-specific guides exist. Debugging tools include built-in step timing analysis and serial communication diagnostics. |
| **Lingua Franca** | **2** | Academic project with a small user base. Documentation is available at lf-lang.org and through published papers, but it is oriented toward the language/runtime, not toward motor control or RP2040-specific use. Community support is primarily through the research group and GitHub issues. Debugging LF programs requires understanding both the LF coordination layer and the target-language code underneath. |

### C7: Academic/Pedagogical Value (Weight: 5%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **Klipper** | **3** | Using Klipper teaches practical embedded systems integration, Linux administration, serial protocols, and configuration-driven development. It is production-grade software used in industry (3D printing, CNC). However, it is closer to "systems integration" than to "systems design from first principles." |
| **Lingua Franca** | **5** | LF is a cutting-edge research tool from a top concurrent-systems research group. Using it would demonstrate engagement with formal real-time methods, reactor-based design, and deterministic concurrency -- topics directly relevant to advanced mechatronics and cyber-physical systems. The instructor specifically flagged it, suggesting pedagogical value is recognized. |

---

## 6. Weighted Score Summary

| Criterion | Weight | Klipper | LF | Klipper Weighted | LF Weighted |
|-----------|--------|---------|-------|------------------|-------------|
| C1: Time to prototype | 0.30 | 5 | 1 | 1.50 | 0.30 |
| C2: Stepper control | 0.20 | 5 | 1 | 1.00 | 0.20 |
| C3: RP2040 support | 0.15 | 5 | 2 | 0.75 | 0.30 |
| C4: Real-time guarantees | 0.10 | 4 | 4 | 0.40 | 0.40 |
| C5: RTDE extensibility | 0.10 | 4 | 3 | 0.40 | 0.30 |
| C6: Community/docs | 0.10 | 5 | 2 | 0.50 | 0.20 |
| C7: Academic value | 0.05 | 3 | 5 | 0.15 | 0.25 |
| **TOTAL** | **1.00** | | | **4.70** | **1.95** |

---

## 7. Risk Assessment

### 7.1 Klipper Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Klipper's G-code paradigm is a poor fit for RTDE streaming commands | Medium | Medium | Write a thin Python translation layer that converts RTDE position/velocity targets into G1 moves. Klipper accepts commands via its API socket in real time. |
| Stallguard feedback path does not exist in stock Klipper for our use case | Medium | Low | Stallguard is a stretch goal. TMC register reads are already supported in Klipper; surfacing data back to URScript requires custom work but is feasible. |
| Need to fork/modify Klipper for bidirectional UR comms | Low | Medium | Moonraker API already supports status queries and webhooks. Likely no fork needed for basic bidirectionality. |

### 7.2 Lingua Franca Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| RP2040 runtime port takes longer than expected | High | Critical | No clear mitigation within 8-week schedule. Fallback to Klipper would forfeit all LF development time. |
| Motor control quality is poor (missed steps, jitter) | High | Critical | Would require extensive embedded tuning. Team lacks prior stepper driver development experience. |
| Schedule overrun prevents functional prototype | Very High | Critical | No functional demo by Mar 31 would be a project failure per the accelerated schedule. |
| Debugging LF-generated C code on RP2040 is difficult | High | High | LF's source-level debugging on embedded targets is immature. Would need to debug generated C against Pico SDK. |

---

## 8. Hybrid Consideration

One might ask: can we use LF on the Pi host side and Klipper on the MCU? This is technically possible -- LF reactors (compiling to Python or C on Linux) could manage the RTDE interface and send commands to Klipper. However, this adds complexity without clear benefit compared to writing a straightforward Python RTDE-to-Klipper bridge. The LF overhead (learning the language, setting up the toolchain, debugging generated code) is not justified when the host-side task is essentially "receive TCP data, format as G-code, send to socket."

---

## 9. Addressing the Instructor's Suggestion

The Pannier Review notes and Canvas feedback indicate the instructor suggested Lingua Franca as a candidate. This is acknowledged and respected -- LF is a genuinely interesting technology with strong theoretical foundations. The recommendation to use Klipper instead is based on the following practical realities:

1. **LF solves a problem we do not have.** Our system does not require formal verification of timing properties. Klipper's empirical real-time performance (sub-10 us step jitter) exceeds the requirements of extrusion control by orders of magnitude.

2. **LF does not solve the problem we do have.** We need to drive a stepper motor with acceleration planning and TMC configuration. LF provides no motor control primitives. We would be writing a stepper driver from scratch inside LF reactor bodies -- at which point LF is adding syntax and toolchain complexity on top of bare C, not simplifying anything.

3. **The schedule does not allow it.** Building motor control firmware from scratch is a multi-month effort for an experienced embedded engineer. For a student team on an 8-week compressed schedule, it represents unacceptable schedule risk.

4. **We can still discuss LF in the report.** The Phase 2 design memo and final report can document this trade study, demonstrating that LF was evaluated using a structured engineering process. This shows the instructor that the suggestion was taken seriously and analyzed rigorously, which is arguably more valuable from a pedagogical standpoint than a partially-working LF prototype.

---

## 10. Recommendation

**Use Klipper.**

The weighted score analysis (Klipper: 4.70, Lingua Franca: 1.95) strongly favors Klipper across nearly every evaluation criterion. The decisive factors are:

- **Klipper provides the entire motor control stack out of the box** -- step generation, acceleration planning, TMC driver support, serial protocol, and RP2040 firmware -- while Lingua Franca provides none of these and would require building them from scratch.
- **The BTT Pico (RP2040) is a first-class Klipper target** with community-maintained configurations, while LF's RP2040 support is experimental at best.
- **The 8-week schedule is incompatible with LF's development burden.** Klipper can have a stepper spinning in a day; LF would consume the entire schedule on platform porting alone.

Lingua Franca is a compelling technology for research in deterministic cyber-physical systems, but it is the wrong tool for this project given the hardware, timeline, and functional requirements. The team should proceed with Klipper and document this trade study as evidence of rigorous engineering decision-making per Bolton's design process (Step 5: Selection of a suitable solution).

### Immediate Next Steps (Post-Decision)

1. Install Klipper on Pi 400 (MainsailOS or manual install)
2. Flash Klipper MCU firmware to BTT Pico
3. Write `printer.cfg` for single-extruder stepper configuration
4. Verify basic stepper motion via G-code console
5. Begin RTDE-to-Klipper bridge development (Python, host-side)

---

## Appendix A: Reference Information

### Lingua Franca

- Website: https://www.lf-lang.org/
- GitHub: https://github.com/lf-lang/lingua-franca
- Key paper: Lohstroh et al., "Toward a Lingua Franca for Deterministic Concurrent Systems," ACM TECS, 2021
- Principal investigator: Edward A. Lee (UC Berkeley)
- C runtime (embedded target): https://github.com/lf-lang/reactor-c
- Supported embedded platform (primary): Zephyr RTOS

### Klipper

- Website: https://www.klipper3d.org/
- GitHub: https://github.com/Klipper3d/klipper
- Documentation: https://www.klipper3d.org/Overview.html
- RP2040 MCU config: https://www.klipper3d.org/RPi_microcontroller.html
- API (Moonraker): https://github.com/Arksine/moonraker
- BTT Pico config examples: available via Klipper community configs

### Project Context

- Course: ME 472, Mechatronics, Winter 2026, University of Michigan
- Instructor: Prof. Pannier
- Design process reference: Bolton's Mechatronics, 7th Ed., Step 5 (Selection of a suitable solution)
