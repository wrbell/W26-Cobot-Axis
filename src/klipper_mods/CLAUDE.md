# src/klipper_mods — StallGuard Dual-Core Firmware Overlay

Stretch-goal firmware overlay for the SKR Pico. Uses RP2040's **idle second core** (core1) to monitor the TMC2209 DIAG pin for real-time stall detection, with a Klippy module exposing the result to the rest of the stack.

**Full build/deploy steps live in `README.md` in this directory — don't duplicate them here.** This file is orientation only.

## File roles

| File | Language | Role |
|------|----------|------|
| `stallguard_shared.h` | C | Shared SRAM struct + spinlock #16 helpers (core0 ↔ core1) |
| `core1_stallguard.c` | C | Core1 entry, gpio16 init, debounce loop |
| `stallguard_command.c` | C | Klipper `DECL_COMMAND`s: `stallguard_query`, `stallguard_clear` |
| `Makefile.patch` | diff | Add above .c files to `src/rp2040/` build |
| `main.c.patch` | diff | Call `core1_launch()` immediately before `sched_main()` |
| `klippy_extras/stallguard_monitor.py` | Python | Host-side module, polls MCU @ 20 Hz, exposes status over Klipper API |

## Build flow (summary)

1. `cp *.c *.h $KLIPPER/src/rp2040/`
2. Apply `Makefile.patch` and `main.c.patch` (anchors below).
3. `make menuconfig` → select SKR Pico / RP2040 → `make` → flash via USB boot mode.
4. `cp klippy_extras/stallguard_monitor.py $KLIPPER/klippy/extras/`.
5. Add `[stallguard_monitor]` to `printer.cfg`.

Automated: `deploy.sh` Step 6b does all of the above (cross-platform GNU/BSD `sed`).

## Patch anchors (memorize these — easy to break)

- Linker symbol for Core1 stack setup: **`_ram_vectortable_start`** (do NOT use `_vector_table` — doesn't exist in Klipper).
- Klipper entry point: **`armcm_main()`** (not `main()`).
- Makefile `sed` anchor: after **`rp2040/i2c.c`** (last file in the real rp2040 Makefile).
- Spinlock #16 is safe — not used by Klipper.

## Hardware prerequisite

Install the **DIAG jumper** on the SKR Pico E-stepper header (connects TMC2209 DIAG → gpio16). Without it, gpio16 floats and the monitor will never fire. This is documented in `README.md` but is the #1 silent failure mode.

## Where this fits in the report

Section H (Results / Discussion) stretch-goal paragraph, Section G.2 test plan (HITL test TP-06). Also presentation slide 11. The feedback path `TMC2209 DIAG → Core1 → MCU command → klippy → RTDE input register → URScript` counts as the "sensors" element for the ME472 prompt.

## Patch-freshness CI

`.github/workflows/patch-freshness.yml` runs weekly against an upstream Klipper shallow clone to catch anchor drift before it bites us.
