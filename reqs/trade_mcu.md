# Trade Study: MCU Platform Selection

**Project:** W26 Cobot Axis -- ME 472 Winter 2026
**Author:** Willem (Software/EE Lead)
**Date:** 2026-02-12
**Status:** RECOMMENDATION READY
**Prerequisite:** Klipper selected as firmware framework (see `trade_lingua_franca_vs_klipper.md`)

---

## 1. Purpose

This trade study evaluates candidate MCU platforms for driving a stepper motor (extrusion axis) under Klipper firmware control, commanded by a Universal Robots UR30 via a Raspberry Pi host. The Klipper framework decision is already made; this study selects the physical board that runs Klipper's MCU firmware and interfaces with the stepper motor.

| Option | Description |
|--------|-------------|
| **BTT SKR Pico V1.0** | RP2040-based 3D printer control board with 4x TMC2209 soldered on-board, UART-configured. Purpose-built for Klipper. 85x56 mm. Product code 1060000513. **Already on hand.** |
| **Raspberry Pi Pico (raw RP2040)** | Bare RP2040 dev board. No motor drivers, no power regulation for motors. Would require external stepper driver breakout(s) and custom wiring. |
| **Arduino Mega 2560 or Due + external driver** | Traditional hobbyist approach. 8-bit ATmega2560 (Mega) or 32-bit SAM3X8E (Due) paired with standalone stepper driver modules (e.g., A4988, DRV8825, or TMC2209 breakout). |
| **Dedicated stepper controller (Gecko G320X / Teknic ClearPath)** | Commercial closed-loop servo or stepper controllers. Step/dir input from host, integrated drive electronics, high-performance motion. |

---

## 2. System Context

```
UR30 Controller ──RTDE/TCP-IP──> Pi (Klipper host) ──USB Serial──> MCU Board ──> Stepper Motor ──> Pump
   (URScript)                    (Klipper + bridge)                 (Klipper MCU firmware)       (metal paste)
```

**Constraints:**
- Klipper firmware must run on the MCU (decided per prior trade study)
- Single stepper axis (extruder-class motion, not multi-axis CNC)
- 24V power available from UR controller power block (2A continuous, 3.5A burst)
- Must fit inside the robot end-effector packaging (compact form factor preferred)
- TMC2209 features desired: UART configuration, StealthChop (quiet), StallGuard (load detection), up to 256 microstepping
- 8-week schedule; prototype needed by Mar 31, 2026

---

## 3. Evaluation Criteria

| # | Criterion | Weight | Description |
|---|-----------|--------|-------------|
| C1 | **Stepper driver integration** | 25% | On-board TMC2209 with UART config, StealthChop, StallGuard, microstepping. Fewer external components = less wiring, less failure risk. |
| C2 | **Software ecosystem** | 25% | Firmware availability, Klipper support maturity, host-side tools (Moonraker/Mainsail), reference configs. |
| C3 | **Development effort** | 20% | Time from unboxing to a working stepper under Klipper control. Includes wiring, config, and debugging. |
| C4 | **Communication capability** | 15% | USB serial and/or UART to Pi host. Klipper protocol compatibility. Reliability of the link. |
| C5 | **Cost and availability** | 15% | Unit cost, lead time, and whether we already have it. Budget is not a hard constraint but is noted for completeness. |

---

## 4. Scoring

Each candidate is scored 1--5 per criterion (5 = best).

### C1: Stepper Driver Integration (Weight: 25%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **BTT SKR Pico** | **5** | 4x TMC2209 soldered on-board with UART bus (gpio8/gpio9, addressed 0--3). StealthChop2, SpreadCycle, StallGuard4, CoolStep, up to 256 microstepping -- all configurable via Klipper `[tmc2209]` config sections. No external wiring needed between MCU and driver. RSENSE = 110 milliohm, up to 1.77A RMS theoretical (0.8A continuous without cooling, ~1.2A with fan). Single driver active for our use case reduces thermal concerns. |
| **Raw RP2040 Pico** | **1** | No motor driver on-board. Must add an external TMC2209 breakout or other driver module. Requires manual wiring of step/dir/enable, UART for TMC config, motor power, and sense resistors. Introduces wiring complexity and failure points. TMC features are technically available but require significant integration effort. |
| **Arduino + external driver** | **2** | Requires external driver module (TMC2209 breakout, A4988, or DRV8825). A4988/DRV8825 lack UART/SPI configuration -- no StealthChop, no StallGuard, limited microstepping options. TMC2209 breakout boards exist but add wiring complexity comparable to the raw Pico option. Arduino Due's 3.3V logic is compatible with TMC2209; Mega's 5V needs level shifting. |
| **Dedicated controller (Gecko/ClearPath)** | **4** | Integrated drive electronics with high-quality current control and step execution. Gecko G320X handles up to 20A; ClearPath integrates servo + drive + controller. However, these are step/dir input only -- no UART-level TMC features like StallGuard or StealthChop. ClearPath has its own closed-loop system which is functionally superior to StallGuard but uses a proprietary protocol, not Klipper-native. |

### C2: Software Ecosystem (Weight: 25%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **BTT SKR Pico** | **5** | First-class Klipper target. Official reference config exists (`generic-bigtreetech-skr-pico-v1.0.cfg`). `make menuconfig` has RP2040 architecture option with correct flash settings (W25Q080/CLKDIV 2). Thousands of production deployments in Voron and similar printers. Moonraker/Mainsail web UI works out of the box. Extensive community configs and troubleshooting resources. |
| **Raw RP2040 Pico** | **3** | Klipper supports RP2040 natively (same MCU as SKR Pico), so `make menuconfig` and firmware build work. However, there is no reference config for a bare Pico board -- pin assignments, driver config, and all peripherals must be configured manually. No TMC sections in config unless external driver is wired and mapped. Workable but requires more config effort. |
| **Arduino Mega 2560** | **2** | Klipper supports ATmega2560 (it was the original Klipper MCU target). However, the 8-bit platform is limited in step rate and has less community momentum as Klipper has shifted to 32-bit boards. Arduino Due (SAM3X8E) has Klipper support but fewer community configs. Neither has a BTT-style reference config with TMC sections. Marlin is the more natural firmware for Arduino boards, but we have already committed to Klipper. |
| **Dedicated controller** | **1** | Not Klipper-compatible. Gecko G320X accepts step/dir pulses -- it would require a separate step-pulse generator, bypassing Klipper's MCU firmware entirely. ClearPath uses its own software (MSP). Integrating either into the Klipper ecosystem would require a custom adapter layer or abandoning Klipper on the MCU side, which contradicts the prior trade study decision. |

### C3: Development Effort (Weight: 20%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **BTT SKR Pico** | **5** | Path to working prototype: (1) build Klipper firmware for RP2040, (2) flash via UF2 to SKR Pico, (3) write `printer.cfg` using reference config as template, (4) connect 24V + stepper + USB, (5) send G-code. Estimated time: under one day. No soldering, no breadboarding. Board-to-stepper connection is a JST-XH 4-pin connector. |
| **Raw RP2040 Pico** | **2** | Same firmware build process, but must: design and wire a driver circuit (TMC2209 breakout + motor power + UART lines + sense resistors), build a custom Klipper config from scratch mapping GPIOs to step/dir/enable/UART pins, and debug the wiring. Estimated time: 2--4 days if experienced, longer for first-time integration. Risk of wiring errors. |
| **Arduino + external driver** | **2** | Similar wiring effort to raw Pico, plus potential 5V/3.3V level shifting (Mega). Klipper build process for ATmega2560 is well-documented but the config is less templated than RP2040-based boards. Arduino Due adds SAM3X complexity. Estimated time: 2--5 days. |
| **Dedicated controller** | **3** | Hardware setup is straightforward (power + step/dir wires). But software integration is the bottleneck: Klipper cannot directly drive these controllers as MCUs. Would need either (a) a separate step-pulse source (defeating the purpose of Klipper), or (b) a custom Klipper module to output step/dir from the Pi GPIO (Klipper supports this via `[mcu host]` but with worse timing than a dedicated MCU). Estimated time: 1--2 weeks to get a workable but suboptimal integration. |

### C4: Communication Capability (Weight: 15%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **BTT SKR Pico** | **5** | USB-C (USB 2.0 Full-Speed, 12 Mbps) for Klipper serial protocol. Also has a dedicated UART header (gpio0/gpio1) for direct Pi UART connection as an alternative. Both paths are supported by Klipper's build options (USBSERIAL or UART0). USB is preferred for our setup (simpler cabling, auto-enumeration, `/dev/serial/by-id/` stable naming). Known issues with USB detection on boot are mitigable (see specs doc Section 6.3). |
| **Raw RP2040 Pico** | **4** | Micro-USB (USB 2.0 Full-Speed). Same RP2040 USB peripheral, same Klipper serial protocol. UART also available on configurable pins. Slightly lower score only because Micro-USB is less robust than USB-C mechanically, and no dedicated Pi UART header (must wire manually). |
| **Arduino Mega 2560** | **3** | USB-B (FTDI or CH340 USB-to-serial). Klipper supports this but at a lower baud rate than native USB on RP2040. Arduino Due has native USB (SAM3X) which is better. No UART header for direct Pi connection without custom wiring. USB-B connector is bulky. |
| **Dedicated controller** | **2** | Step/dir input only -- no bidirectional serial protocol. Gecko G320X has no digital feedback path to the host. ClearPath has USB for configuration but uses a proprietary protocol, not Klipper's. No native way to report status (position, load, temperature) back through Klipper. |

### C5: Cost and Availability (Weight: 15%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **BTT SKR Pico** | **5** | **Already in our possession** (product code 1060000513). Retail ~$25--35 USD. Widely available from BTT official store, Amazon, and Fabreeko. Lead time: 0 days (we have it). |
| **Raw RP2040 Pico** | **4** | ~$4--6 USD for the Pico board itself, but add ~$8--15 for a TMC2209 breakout, plus breadboard/PCB, connectors, and wiring. Total: ~$15--25. Readily available. Would need to be ordered (1--3 day lead time). |
| **Arduino Mega + driver** | **3** | Arduino Mega ~$15--40 (clone vs. official); Due ~$20--45. Add external driver module ~$5--15. Total: $25--55. Readily available. Would need to be ordered. |
| **Dedicated controller** | **2** | Gecko G320X: ~$115 USD. Teknic ClearPath: $200--600+ depending on model. Significant cost increase for a student project. ClearPath may have lead times of 1--2 weeks. Budget is not a hard constraint per project scope, but the cost is disproportionate to the single-axis, low-power requirements. |

---

## 5. Weighted Score Summary

| Criterion | Weight | SKR Pico | Raw RP2040 | Arduino | Dedicated |
|-----------|--------|----------|------------|---------|-----------|
| C1: Driver integration | 0.25 | 5 | 1 | 2 | 4 |
| C2: Software ecosystem | 0.25 | 5 | 3 | 2 | 1 |
| C3: Development effort | 0.20 | 5 | 2 | 2 | 3 |
| C4: Communication | 0.15 | 5 | 4 | 3 | 2 |
| C5: Cost / availability | 0.15 | 5 | 4 | 3 | 2 |
| | | | | | |
| **Weighted total** | **1.00** | **5.00** | **2.55** | **2.25** | **2.55** |

---

## 6. Risk Assessment

### 6.1 BTT SKR Pico Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Non-replaceable TMC2209 failure (soldered on-board) | Low | High | Only one driver active; low electrical stress. Keep a spare SKR Pico (~$30). |
| Heatsink detachment during operation | Medium | Low | Reinforce with thermal tape or mechanical clip before deployment (known issue, see specs doc Section 6.1). |
| USB detection failure on Pi boot | Low | Low | Add startup delay script on Pi, or use UART connection as fallback (see specs doc Section 6.3). |
| 24V required for TMC UART -- power sequencing | Low | Medium | Ensure 24V rail powers up before or simultaneously with Pi. Document in startup procedure. |

### 6.2 Risks of Alternatives (if SKR Pico were unavailable)

| Risk | Applies to | Likelihood | Impact |
|------|-----------|-----------|--------|
| Wiring errors in driver circuit | Raw Pico, Arduino | High | Medium -- wrong step/dir/UART wiring can damage TMC2209 or motor |
| Schedule overrun from custom integration | Raw Pico, Arduino | Medium | High -- days lost to debugging wiring and config |
| Klipper incompatibility | Dedicated controller | Certain | Critical -- would require abandoning Klipper MCU firmware or building a custom adapter |
| Oversized/overspec'd hardware for single-axis use | Dedicated controller | Certain | Low -- functional but wasteful of cost and packaging volume |

---

## 7. Recommendation

**Use the BTT SKR Pico V1.0 with Klipper firmware.**

The SKR Pico achieves a perfect weighted score (5.00/5.00) across all evaluation criteria. The decisive factors are:

1. **Integrated TMC2209 drivers** eliminate external wiring, reduce failure points, and provide StealthChop, StallGuard, and UART microstepping configuration natively through Klipper's `[tmc2209]` config sections.

2. **First-class Klipper support** with an official reference config, community-proven build/flash procedures, and production-grade stability on thousands of identical boards in the 3D printing community.

3. **Zero lead time** -- the board is already on hand and ready for firmware flashing.

4. **Compact form factor** (85x56 mm, Pi mounting hole pattern) suitable for end-effector packaging.

5. **Minimal development effort** -- the path from unboxing to a spinning stepper under Klipper control is measured in hours, not days.

No alternative justifies additional cost, wiring complexity, or development time when the SKR Pico provides a complete, integrated, Klipper-native solution already in our possession.

### Immediate Next Steps (Post-Decision)

1. Flash Klipper MCU firmware to SKR Pico (RP2040 UF2, USBSERIAL mode)
2. Write `printer.cfg` with `[manual_stepper]` for single-axis extruder control
3. Configure `[tmc2209]` section (UART address, run current, StealthChop threshold)
4. Verify stepper motion via Klipper G-code console
5. Proceed to RTDE bridge integration on Pi host

---

## Appendix A: SKR Pico V1.0 Key Specs (Quick Reference)

| Parameter | Value |
|-----------|-------|
| MCU | RP2040 (dual Cortex-M0+, 133 MHz, 264 KB SRAM) |
| Flash | 2 MB W25Q16 QSPI |
| Drivers | 4x TMC2209 (soldered, UART, shared bus gpio8/gpio9) |
| Motor connectors | JST-XH 4-pin (x4) |
| Input voltage | 12--24V DC |
| USB | USB-C (Full-Speed 12 Mbps) |
| UART to Pi | GPIO0 (TX) / GPIO1 (RX), dedicated header |
| Dimensions | 85 mm x 56 mm, 4-layer PCB |
| Klipper ref config | `generic-bigtreetech-skr-pico-v1.0.cfg` |

Full specifications: `tech_docs/BigTree Controller/skr_pico_v1_specs.md`

---

## Appendix B: References

- BigTreeTech SKR-Pico GitHub: https://github.com/bigtreetech/SKR-Pico
- Klipper reference config: https://github.com/Klipper3d/klipper/blob/master/config/generic-bigtreetech-skr-pico-v1.0.cfg
- TMC2209 datasheet: https://www.analog.com/media/en/technical-documentation/data-sheets/TMC2209_datasheet_rev1.09.pdf
- Gecko G320X: https://www.geckodrive.com/g320x.html
- Teknic ClearPath: https://www.teknic.com/products/clearpath-brushless-dc-servo-motors/
- Raspberry Pi Pico: https://www.raspberrypi.com/products/raspberry-pi-pico/
- Arduino Mega 2560: https://store.arduino.cc/products/arduino-mega-2560-rev3
- Bolton, W. *Mechatronics*, 7th Ed. -- Step 5: Selection of a suitable solution
