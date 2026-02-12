# Buck Converter Selection

**For:** Phase 2 Memo, BOM item + Section 2.4a
**Author:** Willem
**Date:** 2026-02-12
**Status:** Rough draft

---

## 1. Requirements

The Raspberry Pi 4B requires a regulated 5V supply. A buck (step-down) switching converter is needed because the source is 24V — a linear regulator would waste 79% of input power as heat (5/24 = 21% efficiency).

| Parameter | Required Value | Basis |
|-----------|---------------|-------|
| Output voltage | 5.0–5.25V (fixed preferred) | Pi 4B PMIC under-voltage threshold: 4.63V |
| Output current | ≥ 1.5A (continuous) | Pi design current with margin |
| Output current (peak) | ≥ 2.0A | Startup / USB peripheral surges |
| Input voltage range | 20–29V (must include 24V ± 1V) | UR30 power block spec |
| Output ripple | < 50 mV peak-to-peak | Pi power quality requirement |
| Form factor | Small module, PCB-mountable | Fits in 3D-printed enclosure |
| Availability | DigiKey, Newark, or Pololu | UMich-approved suppliers |

---

## 2. Candidates Evaluated

| Module | VIN Range | VOUT | I_max | Efficiency | Size (mm) | Price | Supplier |
|--------|-----------|------|-------|-----------|-----------|-------|----------|
| **Pololu D24V22F5** | 4.5–42V | 5.0V fixed | 2.2A | ~90% | 17.8 × 10.2 | ~$8 | Pololu (also DigiKey) |
| Pololu D24V50F5 | 4.5–38V | 5.0V fixed | 5.0A | ~90% | 20.3 × 17.8 | ~$13 | Pololu (also DigiKey) |
| DROK LM2596 module | 4.5–40V | Adjustable | 3.0A | ~85% | 60 × 35 | ~$3 | Amazon (not UMich supplier) |
| Adafruit 5V Buck (P/N 1385) | 7–36V | 5.0V fixed | 3.0A | ~85% | 38.1 × 19.1 | ~$10 | DigiKey |
| Murata OKI-78SR-5/1.5-W36-C | 7–36V | 5.0V fixed | 1.5A | ~90% | 26.0 × 11.5 × 17.5 | ~$5 | DigiKey |
| Traco TSR 1-2450 | 6.5–36V | 5.0V fixed | 1.0A | ~90% | SIP-3 | ~$5 | DigiKey |

---

## 3. Selection: Pololu D24V22F5

**Selected:** Pololu D24V22F5 (5V, 2.2A step-down voltage regulator)

### Rationale

| Criterion | Pololu D24V22F5 | Notes |
|-----------|----------------|-------|
| Output current | 2.2A | Exceeds 1.5A design requirement with 47% headroom |
| Input range | 4.5–42V | Covers UR30's 23–25V with wide margin |
| Fixed output | 5.0V | No adjustment needed; factory-calibrated |
| Efficiency | ~90% at our operating point | Matches or exceeds alternatives |
| Size | 17.8 × 10.2 mm | Smallest option; fits easily in enclosure |
| Documentation | Excellent (Pololu data page, schematic, app notes) | Well-characterized for Pi projects |
| Enable pin | Available (EN) | Can add power sequencing if needed |
| Power Good output | Available (PG) | Can monitor with Pi GPIO |

### Why Not the Alternatives

| Module | Reason Not Selected |
|--------|---------------------|
| Pololu D24V50F5 | Overkill (5A for 1.5A load); larger, more expensive. Good backup if we need more current. |
| DROK LM2596 | Adjustable output (trimpot) is a reliability risk; not available from UMich suppliers; larger form factor. |
| Adafruit 1385 | Larger; lower efficiency (85%); no significant advantage over Pololu. |
| Murata OKI-78SR | Only 1.5A — exactly at our design current with zero margin. Good for a more constrained design. |
| Traco TSR 1-2450 | Only 1.0A — insufficient for Pi 4B under load. |

---

## 4. Specifications (Pololu D24V22F5)

| Parameter | Value | Source |
|-----------|-------|--------|
| Pololu product # | 2858 | pololu.com/product/2858 |
| IC | TPS54331 (TI) | Pololu schematic |
| Input voltage | 4.5–42V | Pololu datasheet |
| Output voltage | 5.0V (fixed, ±2%) | Pololu datasheet |
| Max output current | 2.2A (at VIN > 7V) | Pololu datasheet |
| Max output current (VIN = 24V) | 2.2A | Full rating |
| Quiescent current | ~1 mA (no load) | Pololu datasheet |
| Switching frequency | ~1 MHz | TPS54331 datasheet |
| Output ripple | ~30 mV p-p (typical at 1A) | Pololu measured |
| Efficiency (24V in, 5V/1A out) | ~90% | Pololu efficiency graph |
| Operating temperature | -40°C to +85°C | TPS54331 datasheet |
| PCB dimensions | 17.8 × 10.2 mm | Pololu datasheet |
| Mounting holes | 2× (0.086" / 2.18 mm) | Pololu mechanical drawing |
| Pinout | VIN, GND, VOUT, EN, PG | 5-pin, 0.1" pitch |
| Reverse voltage protection | None (external protection needed) | Add TVS diode |
| Over-temperature protection | Yes (TPS54331 internal) | Shuts down at 165°C junction |
| Short-circuit protection | Yes (cycle-by-cycle current limit) | TPS54331 internal |

---

## 5. Part Numbers for BOM

| Item | Supplier | Part Number | Price | Notes |
|------|----------|-------------|-------|-------|
| Pololu D24V22F5 | Pololu | 2858 | $7.95 | Direct from pololu.com |
| Pololu D24V22F5 | DigiKey | 2183-D24V22F5-ND | ~$8.95 | DigiKey stocked |
| Header pins (0.1" pitch) | Included | — | — | Comes with 5-pin header (unsoldered) |

**Backup option (if unavailable):**

| Item | Supplier | Part Number | Price |
|------|----------|-------------|-------|
| Pololu D24V50F5 | DigiKey | 2183-D24V50F5-ND | ~$14.95 |
| Murata OKI-78SR-5/1.5-W36-C | DigiKey | 811-2692-ND | ~$5.50 |

---

## 6. Application Circuit

```
24V Distribution ──[22 AWG]──▶ VIN ┐
                                    │  Pololu D24V22F5
GND Bus ──────────[22 AWG]──▶ GND ┤  (17.8 × 10.2 mm)
                                    │
                              VOUT ┤──▶ [2A Polyfuse] ──▶ Pi GPIO Pin 2 (+5V)
                                EN ┤  (floating = enabled)
                                PG ┤  (optional: connect to Pi GPIO for monitoring)
                                    │
                               GND ┘──▶ Pi GPIO Pin 6 (GND)
```

### Input Side
- 100nF ceramic capacitor across VIN-GND (close to module)
- TVS diode (SMBJ24CA) and bulk cap (100µF/35V) at the distribution point handle transient protection

### Output Side
- 100nF ceramic capacitor across VOUT-GND (close to module)
- 2A resettable PTC polyfuse between VOUT and Pi 5V rail
- No additional electrolytic needed (module has onboard output cap)

---

## Caption

The Pololu D24V22F5 was selected as the 24V-to-5V buck converter for powering the Raspberry Pi. It provides 2.2A continuous at 5.0V with ~90% efficiency, fitting within a 17.8 × 10.2 mm footprint. The fixed 5V output eliminates adjustment risk, and the wide input range (4.5–42V) accommodates the UR30's 23–25V supply with margin.
