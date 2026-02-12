# Bill of Materials (Draft)

**For:** Phase 2 Memo, Table 4 + Section 2.7
**Author:** Willem
**Date:** 2026-02-12
**Status:** Rough draft — part numbers are best-effort; verify stock and pricing before ordering

---

## 1. Purchasing Instructions

All components should be ordered through UMich-contracted suppliers: **DigiKey**, **Newark (element14)**, **Grainger**, **MSC Direct**, or **BH Photo Video**. The instructor places orders on behalf of the team.

Before ordering, verify:
- **Lab inventory** — the Pi, Ethernet switch, and some cables may already be available in the ME472 lab
- **Lead times** — DigiKey ships most items next-day; Newark may be 2–3 days
- Items marked "On hand" or "Provided" do not need to be ordered

---

## 2. Bill of Materials — Table 4

### 2.1 Electronics — Must Purchase

| # | Item | Description | Qty | Supplier | Part Number | Est. Unit Price | Est. Total | Notes |
|---|------|-------------|-----|----------|-------------|----------------|-----------|-------|
| 1 | Raspberry Pi 4 Model B | 2GB RAM, Klipper host + RTDE bridge | 1 | Newark | 02AH3162 (2GB) | $45.00 | $45.00 | Check lab inventory first; 4GB model also acceptable ($55) |
| 2 | MicroSD Card | 32GB, Class 10 / A1, for Pi OS + Klipper | 1 | DigiKey | 1597-AF3120-ND (Adafruit) | $9.95 | $9.95 | Any reputable 32GB+ Class 10 card works |
| 3 | Pololu D24V22F5 | 24V-to-5V buck converter, 2.2A, fixed output | 1 | DigiKey | 2183-2858-ND (Pololu 2858) | $8.95 | $8.95 | Powers Pi via GPIO header |
| 4 | Gigabit Ethernet Switch | Unmanaged, 5-port, desktop | 1 | Newark | 15P9155 (Netgear GS105NA) | $59.26 | $59.26 | Check lab inventory first; any 5-port unmanaged gigabit switch works |
| 5 | Ethernet Cable (Cat5e) | 1m, RJ45 both ends | 2 | DigiKey | AE10194-ND (Assmann A-MCSSP60010) | $6.09 | $12.18 | UR30→switch, Pi→switch |
| 6 | Ethernet Cable (Cat5e) | 2m, RJ45 both ends | 1 | DigiKey | AE10199-ND (Assmann A-MCSSP60020) | $7.50 | $7.50 | Pi400→switch (optional) |
| 7 | USB-A to USB-C Cable | 0.5m, shielded, USB 2.0 | 1 | DigiKey | 2944-QUSC2HC050-ND | $5.95 | $5.95 | Pi USB-A → SKR Pico USB-C |

### 2.2 Protection and Passives

| # | Item | Description | Qty | Supplier | Part Number | Est. Unit Price | Est. Total | Notes |
|---|------|-------------|-----|----------|-------------|----------------|-----------|-------|
| 8 | Inline Fuse Holder | Inline fuse holder, 18 AWG leads | 1 | DigiKey | BF310-ND (MPD) | $0.96 | $0.96 | For 24V main input; previous P/N F4275-ND obsolete |
| 9 | Blade Fuse | 3A, ATC/ATO, standard size | 2 | DigiKey | F5040-ND (Littelfuse 0ATO003.V) | $0.50 | $1.00 | 1 active + 1 spare; verify fuse format matches holder |
| 10 | TVS Diode | SMBJ24CA, bidirectional, 24V, SMB package | 1 | DigiKey | SMBJ24CAFSCT-ND (Littelfuse) | $0.19 | $0.19 | Transient/ESD protection at 24V input |
| 11 | Electrolytic Capacitor | 100µF, 35V, radial | 1 | DigiKey | P5551-ND (Panasonic ECA-1VHG101) | $0.35 | $0.35 | 24V bus smoothing |
| 12 | Resettable Fuse (PTC) | 2A hold, 4A trip, radial | 1 | DigiKey | RGE200-ND (Bourns) | $0.75 | $0.75 | Pi 5V rail protection |
| 13 | Ceramic Capacitor (100nF) | 0.1µF, 50V, X7R, radial | 2 | DigiKey | BC1084CT-ND (Vishay K104K15X7RF5TL2) | $0.20 | $0.40 | Buck converter input/output decoupling |

### 2.3 Wiring and Connectors

| # | Item | Description | Qty | Supplier | Part Number | Est. Unit Price | Est. Total | Notes |
|---|------|-------------|-----|----------|-------------|----------------|-----------|-------|
| 14 | Hookup Wire (18 AWG) | Stranded, red, 3m | 1 | DigiKey | C2015R-100-ND (cut to 3m) | $5.00 | $5.00 | 24V power distribution |
| 15 | Hookup Wire (18 AWG) | Stranded, black, 3m | 1 | DigiKey | C2015BK-100-ND (cut to 3m) | $5.00 | $5.00 | GND distribution |
| 16 | Hookup Wire (22 AWG) | Stranded, red, 2m | 1 | DigiKey | C2017R-100-ND (cut to 2m) | $4.00 | $4.00 | 5V power, buck converter |
| 17 | Hookup Wire (22 AWG) | Stranded, black, 2m | 1 | DigiKey | C2017BK-100-ND (cut to 2m) | $4.00 | $4.00 | GND, low-current paths |
| 18 | Screw Terminal Block | 2-position, 5.08mm pitch, PCB mount | 3 | DigiKey | ED2580-ND (On Shore) | $1.50 | $4.50 | Distribution point, Pi power, SKR power |
| 19 | DuPont Jumper Wires | Female-to-female, 20cm, assorted | 1 pack | DigiKey | 1528-4167-ND (Adafruit) | $3.95 | $3.95 | Pi GPIO connections, prototyping |
| 20 | Heat Shrink Tubing | Assorted sizes, 2:1 ratio | 1 kit | DigiKey | Q2F316B-ND | $4.00 | $4.00 | Wire insulation and strain relief |

### 2.4 Items On Hand / Provided

| # | Item | Description | Qty | Source | Est. Price | Notes |
|---|------|-------------|-----|--------|-----------|-------|
| 21 | BTT SKR Pico V1.0 | RP2040 + 4× TMC2209, Klipper MCU | 1 | On hand | $0 | Already in team possession |
| 22 | Raspberry Pi 400 | HMI terminal (keyboard + Pi 4) | 1 | On hand | $0 | Optional; already in team possession |
| 23 | Stepper Motor | NEMA 17 (specs TBD) | 1 | Instructor-provided | $0 | Will be given to team |
| 24 | Pump | Metal paste dispensing (type TBD) | 1 | Instructor-provided | $0 | Will be given to team |
| 25 | Pi 400 USB-C PSU | 5.1V/3A, official | 1 | On hand | $0 | Powers Pi 400 independently |

### 2.5 3D-Printed Components (Dawood)

| # | Item | Description | Qty | Source | Est. Price | Notes |
|---|------|-------------|-----|--------|-----------|-------|
| 26 | Electronics Enclosure | Housing for Pi + SKR Pico + buck + fuse | 1 | Instructor's 3D printer | $0 (material) | Dawood designs; PLA or PETG |
| 27 | Motor/Pump Mount | End effector mounting bracket | 1 | Instructor's 3D printer | $0 (material) | Dawood designs; depends on hardware receipt |
| 28 | Cable Management Clips | Arm-mounted cable routing | TBD | Instructor's 3D printer | $0 (material) | Dawood designs |

---

## 3. Cost Summary

| Category | Est. Total |
|----------|-----------|
| Electronics (items 1–7) | $148.79 |
| Protection and passives (items 8–13) | $3.65 |
| Wiring and connectors (items 14–20) | $30.45 |
| On hand / provided (items 21–25) | $0.00 |
| 3D-printed (items 26–28) | $0.00 (material provided) |
| **Grand Total** | **~$183** |

**Notes:**
- Prices are estimates from DigiKey/Newark as of Feb 2026
- Shipping is typically free for UMich institutional orders
- Some items (Pi, Ethernet switch, cables) may be in lab inventory — verify before ordering
- Wire quantities assume purchase of short lengths; bulk spools are cheaper but unnecessary
- The Pi 4B price varies significantly (~$45 for 2GB, ~$55 for 4GB); 2GB is sufficient for Klipper

---

## 4. Part Number Verification Status

| Item | Status | Notes |
|------|--------|-------|
| Pololu D24V22F5 | **Verified** — DigiKey 2183-2858-ND | In stock, ships same day |
| SMBJ24CA TVS | **Verified** — DigiKey SMBJ24CAFSCT-ND | In stock, ~$0.19 |
| 100nF ceramic cap | **Verified** — DigiKey BC1084CT-ND (Vishay K104K15X7RF5TL2) | In stock |
| 100µF electrolytic cap | **Verified** — DigiKey P5551-ND (Panasonic ECA-1VHG101) | Previous P/N P5148-ND was wrong part (10µF 25V) |
| Netgear GS105NA switch | **Verified** — Newark 15P9155 | $59.26; may be out of stock — check lab inventory first |
| Raspberry Pi 4B | **Corrected** — Newark 02AH3162 (2GB) | Previous P/N 913-2664 was a camera module, not a Pi; ~$45 |
| Ethernet 1m cable | **Verified** — DigiKey AE10194-ND (Assmann A-MCSSP60010) | Previous P/N AE10189-ND was 0.5m |
| Ethernet 2m cable | **Verified** — DigiKey AE10199-ND (Assmann A-MCSSP60020) | Previous P/N AE10190-ND was 1m |
| 3A blade fuse | **Corrected** — DigiKey F5040-ND (Littelfuse 0ATO003.V) | Previous P/N F990-ND was 7.5A mini fuse |
| Inline fuse holder | **Corrected** — DigiKey BF310-ND (MPD) | Previous P/N F4275-ND is obsolete; verify fuse format compatibility |
| MicroSD card | **Unverified** — DigiKey 1597-AF3120-ND | Verify before ordering |
| USB-A to USB-C cable | **Unverified** — DigiKey 2944-QUSC2HC050-ND | Verify before ordering |
| Wire (18/22 AWG) | Sold in 100ft spools at DigiKey | May need to buy spools or find shorter lengths |
| Screw terminals | Many pitch/position options | Verify 5.08mm pitch fits SKR Pico and enclosure |

---

## Table/Section Caption

**Table 4.** Bill of materials listing all components required for the W26 Cobot Axis system. Items are categorized by function: electronics, protection/passives, wiring, on-hand items, and 3D-printed components. The SKR Pico and Pi 400 are already in team possession. The stepper motor and pump will be provided by the instructor. Estimated total cost for purchasable items is approximately $183, subject to lab inventory availability and current pricing.
