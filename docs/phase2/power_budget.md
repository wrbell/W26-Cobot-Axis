# Power Budget Worksheet

**For:** Phase 2 Memo, Table 2 + Section 2.4c
**Author:** Willem
**Date:** 2026-02-12
**Status:** Rough draft — motor values are placeholders (TBD on receipt)

---

## 1. Power Source

| Parameter | Value | Source |
|-----------|-------|--------|
| Supply | UR30 Controller Box, Power Block (internal 24V) | UR30 User Manual pp. 82–84 |
| Nominal voltage | 24V DC (23–25V range) | UR30 User Manual |
| Continuous current limit | 2.0 A | UR30 User Manual |
| Burst current limit | 3.5 A (500 ms at 33% duty cycle) | UR30 User Manual |
| Continuous power budget | 48 W | 24V × 2.0A |
| External PSU option | 6 A at 20–29V (with external supply on 24V/0V terminals) | Contingency only |

---

## 2. Device Current Budget at 24V Input

### Table 2 (for memo)

| Device | Idle (A @ 24V) | Typical (A @ 24V) | Peak (A @ 24V) | Notes |
|--------|-----------------|---------------------|------------------|-------|
| Raspberry Pi 4B (via buck, 90% eff.) | 0.15 | 0.35 | 0.45 | Design: 1.5A @ 5.1V → 0.35A @ 24V |
| SKR Pico (logic, TMC2209 quiescent) | 0.05 | 0.08 | 0.10 | RP2040 + 4× TMC2209 standby |
| Stepper motor (TMC2209, E-axis) | 0.10 | 0.50 | 1.00 | **[TBD]** Placeholder NEMA 17 @ 0.58A run |
| Cooling fan (optional, Fan0) | 0.00 | 0.04 | 0.08 | 24V axial fan, ~1W typical |
| **Total** | **0.30** | **~0.97** | **~1.63** | |
| **UR30 Budget** | **2.00** | **2.00** | **3.50** | Continuous / burst |
| **Margin** | **1.70** | **1.03** | **1.87** | Positive = within budget |

---

## 3. Detailed Calculations

### 3.1 Raspberry Pi 4B

| Parameter | Value | Source |
|-----------|-------|--------|
| Operating voltage | 5.1V via GPIO header | Pi 4B datasheet |
| Idle current (headless) | ~600 mA @ 5V | Measured (community) |
| Typical current (klippy + bridge + Ethernet) | ~1.0 A @ 5V | Estimated |
| Design current | 1.5 A @ 5V | With safety margin |
| Peak current | 1.4 A @ 5V | All cores + USB peripherals |
| Buck converter efficiency | ~90% (Pololu D24V22F5) | Pololu datasheet |
| Current from 24V rail (typical) | (1.0 × 5.1) / (24 × 0.90) = **0.24 A** | P_out / (V_in × η) |
| Current from 24V rail (design) | (1.5 × 5.1) / (24 × 0.90) = **0.35 A** | Budget value |
| Current from 24V rail (peak) | (1.4 × 5.1) / (24 × 0.90) = **0.33 A** | Actual peak; use 0.45A with margin |

### 3.2 SKR Pico (Logic Only)

| Parameter | Value | Source |
|-----------|-------|--------|
| RP2040 current (active) | ~50 mA @ 3.3V | RP2040 datasheet |
| Onboard 5V regulator quiescent | ~10 mA | Estimated |
| TMC2209 × 4 standby (UART active) | ~20 mA total | TMC2209 datasheet (5 mA each) |
| Board total from 24V VIN (idle) | ~50 mA | 24V → 5V → 3.3V losses |
| Board total from 24V VIN (active) | ~80 mA | With TMC UART polling |

### 3.3 Stepper Motor (via TMC2209)

The motor current draw from the 24V rail depends on speed, load, and current setting. Key formula:

```
P_motor = I_rms² × R_coil (at standstill / low speed)
I_24V = P_motor / (V_supply × η_driver)
```

**Placeholder calculations (NEMA 17 with R_coil = 1.8Ω, I_rated = 1.7A):**

| Scenario | Motor RMS Current | Power Dissipated | Current from 24V | Notes |
|----------|------------------|-----------------|-------------------|-------|
| Hold (standstill) | 0.400 A (hold_current) | 0.29 W | 0.013 A | Minimal draw |
| Idle (enabled, no motion) | 0.580 A (run_current) | 0.61 W | 0.028 A | Current chopping at V_supply |
| Low-speed extrusion | 0.580 A | ~3 W | ~0.14 A | Includes friction losses |
| Typical extrusion | 0.580 A | ~12 W | ~0.50 A | Mid-speed, loaded |
| Peak (acceleration) | 0.580 A | ~24 W | ~1.00 A | Rapid acceleration burst |

**Note:** These are estimates based on a generic 17HS4401 motor. Actual values depend on the motor and pump provided by the instructor. The `run_current: 0.580` setting in printer.cfg is conservative — well below the SKR Pico's 0.8A thermal limit without cooling.

### 3.4 Cooling Fan (Optional)

| Parameter | Value |
|-----------|-------|
| Fan port | SKR Pico Fan0 (gpio17), VIN voltage (24V) |
| Typical 24V fan | 40×40mm axial, 0.04A (1W) |
| Peak | 0.08A during startup |
| When needed | If run_current > 0.8A or ambient temperature > 30°C |
| Default config | Disabled (commented out in printer.cfg) |

---

## 4. Margin Analysis

### 4.1 Against UR30 Internal 24V (2A Continuous)

| Scenario | Total Draw | Margin | Status |
|----------|-----------|--------|--------|
| System idle (all on, motor holding) | 0.30 A | 1.70 A | OK |
| Normal extrusion operation | 0.97 A | 1.03 A | OK |
| Peak acceleration burst | 1.63 A | 0.37 A | OK (within continuous) |
| Absolute worst case (all peaks simultaneous) | ~1.8 A | 0.2 A | OK — burst rating provides headroom |

### 4.2 Against UR30 Burst Rating (3.5A at 33% Duty)

Even the absolute worst case (1.8A) is well below the 3.5A burst limit. The system has no scenario requiring burst-level current.

### 4.3 Against External 24V Option (6A)

If the provided motor requires more than the placeholder 0.58A run current, an external 24V supply provides 6A — more than 4× the expected peak draw. This is the contingency plan per design specification constraint C-10.

---

## 5. Thermal Considerations

| Component | Max Temp | Heat Generated | Cooling |
|-----------|----------|---------------|---------|
| TMC2209 (E-axis) | 150°C (junction) | ~0.3W at 0.58A (R_DSon × I²) | Onboard heatsink; fan optional |
| Pololu D24V22F5 | 85°C (ambient) | ~0.85W at 0.35A input (10% loss) | Passive; adequate at low current |
| Pi 4B | 85°C (SoC throttle) | ~5W total board | Passive heatsink; enclosed = may need ventilation |
| Stepper motor | 80°C (class B insulation) | ~0.6W (I²R in coils) | Passive; mounted in open air |

### Recommendation
At the conservative `run_current: 0.580` setting, no active cooling is required for the TMC2209. A passive heatsink (included with SKR Pico) is sufficient. Active cooling (Fan0) should be added if:
- Motor current is increased above 0.8A
- Electronics are enclosed without ventilation
- Ambient temperature exceeds 30°C

---

## Table/Section Caption

**Table 2.** Power budget showing current draw per device at idle, typical, and peak operation. Total system draw is approximately 1.0A typical at 24V, well within the UR30's 2.0A continuous budget with 1.0A margin. Motor current values are placeholders pending hardware receipt; the Klipper configuration starts at a conservative 0.58A run current.
