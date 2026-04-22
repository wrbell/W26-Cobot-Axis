# RTDE Register Allocation — Design Decision

**Project:** W26 Cobot Axis
**Author:** Willem (Software/EE)
**Date:** 2026-02-12
**Status:** Finalized

---

## Overview

This document finalizes the RTDE register mapping between the UR30 controller and the Pi (RTDE bridge daemon). The proposed mapping from `docs/ur_rtde.md` Section 3.4 is adopted with minor refinements.

**Convention:**
- **Output registers** = UR30 → Pi (URScript writes, bridge daemon reads)
- **Input registers** = Pi → UR30 (bridge daemon writes, URScript reads)

---

## Output Registers (UR30 → Pi)

These registers are written by the URScript program on the UR30 and read by the RTDE bridge daemon on the Pi.

| Register | Type | Purpose | Range / Values |
|----------|------|---------|---------------|
| `output_int_register_12` | INT32 | Extrusion mode command | 0=off, 1=extrude, 2=retract |
| `output_double_register_12` | DOUBLE | Commanded extrusion rate | mm/s (0.0 – TBD max) |
| `output_double_register_13` | DOUBLE | Current robot TCP speed magnitude | mm/s (from `norm(get_actual_tcp_speed())`) |
| `output_bit_register_64` | BOOL | Extrusion enable | TRUE=enabled, FALSE=disabled |
| `output_bit_register_65` | BOOL | Emergency stop / halt extrusion | TRUE=halt immediately |
| `output_bit_register_66` | BOOL | Home stepper command | TRUE=initiate homing sequence |

> **Index range:** ur-rtde refuses int/double output register indices outside `[12, 19]` — the lower indices `0..11` are reserved by Universal Robots for URCaps and Installation scripts. All bridge int/double registers are placed in the `12..23` range. Bit registers `64..127` are unrestricted.

### Notes

- `output_double_register_12` (commanded extrusion rate) is the primary control signal. The bridge daemon translates this to a Klipper `MANUAL_STEPPER` speed command.
- `output_double_register_13` (TCP speed) is provided for the bridge daemon to implement speed-proportional extrusion mode, where extrusion rate = f(TCP_speed). This is an alternative to the UR30 computing the extrusion rate itself.
- `output_bit_register_65` (emergency stop) triggers an immediate `MANUAL_STEPPER STEPPER=pump ENABLE=0` and optionally a Klipper `M112` (emergency stop). This is a software e-stop; a hardware e-stop via UR30 digital I/O is recommended as a secondary safety layer.

### Registers Reserved for Future Use

| Register | Reserved For |
|----------|-------------|
| `output_int_register_13` | Commanded stepper position target (steps) — for position mode |
| `output_double_register_14` | Current robot TCP Z-height (mm) — for layer-aware extrusion |
| `output_bit_register_67` | Reserved |

---

## Input Registers (Pi → UR30)

These registers are written by the RTDE bridge daemon on the Pi and read by URScript on the UR30.

| Register | Type | Purpose | Range / Values |
|----------|------|---------|---------------|
| `input_int_register_18` | INT32 | Stepper status | 0=idle, 1=running, 2=error, 3=homing |
| `input_int_register_19` | INT32 | Stepper error code | 0=none, 1=comms_lost, 2=stall_detected, 3=thermal_fault |
| `input_double_register_18` | DOUBLE | Actual extrusion rate | mm/s (measured from Klipper status) |
| `input_bit_register_64` | BOOL | Stepper ready flag | TRUE=ready to accept commands |
| `input_bit_register_65` | BOOL | Stepper fault flag | TRUE=fault condition active |

> **Note**: input int/double register indices have a *different* restriction: ur-rtde requires `[18, 22]` (not `[12, 19]` like outputs). The two ranges do not overlap.

### Notes

- `input_int_register_18` (stepper status) allows the URScript program to gate motion on stepper readiness. For example, the UR30 should not begin a deposition path until `status == 0 (idle)` and `ready == TRUE`.
- `input_double_register_18` (actual extrusion rate) is derived from Klipper's `motion_report.live_extruder_velocity` or equivalent `manual_stepper` status object.
- Error codes in `input_int_register_19` are defined by the bridge daemon. Additional codes can be added as needed.

### Active Registers (Added)

| Register | Type | Purpose | Range / Values |
|----------|------|---------|---------------|
| `input_double_register_19` | DOUBLE | StallGuard load value | 0.0–255.0 (lower = higher load, 0 = stall) |

### Registers Reserved for Future Use

| Register | Reserved For |
|----------|-------------|
| `input_int_register_20` | Current stepper position (steps) |
| `input_double_register_20` | Stepper driver temperature (stretch goal) |
| `input_bit_register_66` | Homing complete flag |

---

## Data Flow Summary

```
URScript (UR30)                    RTDE Bridge (Pi)                   Klipper → SKR Pico
─────────────────                  ────────────────                   ──────────────────
Write output registers   ──RTDE──▶  Read output registers
  - extrusion mode                   - Translate to G-code
  - extrusion rate                   - Send via /tmp/klippy_uds ──▶  MANUAL_STEPPER commands
  - TCP speed
  - enable/disable/e-stop

Read input registers    ◀──RTDE──  Write input registers
  - stepper status                   - Subscribe to Klipper status  ◀── motion_report, tmc2209
  - actual rate                      - Map to register values
  - ready/fault flags
```

---

## URScript Example

```urscript
# URScript program on UR30 — extrusion control via RTDE registers

def extrude_along_path():
    # Enable extrusion
    write_output_boolean_register(64, True)   # extrusion enable (URScript-side write OK; bridge cannot read bit registers via ur_rtde)
    write_output_integer_register(12, 1)      # mode = extrude (output int 12 is the gate)

    # Move along path, updating extrusion rate proportional to TCP speed.
    # Note: bridge cannot read bit input registers either, so the URScript
    # cannot rely on read_input_boolean_register() for ready/fault — use
    # input_int_register_18 (status) and input_int_register_19 (error) instead.
    movel(target_pose, a=0.5, v=0.1)
    while is_steady() == False:
        tcp_speed = norm(get_actual_tcp_speed())
        extrusion_rate = tcp_speed * EXTRUSION_MULTIPLIER
        write_output_float_register(12, extrusion_rate)
        write_output_float_register(13, tcp_speed)

        # Check for faults via int-encoded status register
        if read_input_integer_register(19) != 0:
            popup("Stepper fault!", error=True)
            break
        end

        sync()
    end

    # Stop extrusion
    write_output_integer_register(12, 0)      # mode = off
end
```

---

## Design Rationale

1. **Speed-proportional mode via TCP speed register:** Rather than requiring the UR30 to compute the exact extrusion rate, providing `actual_TCP_speed` to the bridge daemon allows the Pi to apply its own mapping function. This decouples the extrusion math from URScript and makes it easier to tune.

2. **Separate enable and mode registers:** The enable bit (`output_bit_register_64`) acts as a master gate. Even if mode is set to "extrude," the stepper won't move unless enable is TRUE. This provides defense-in-depth.

3. **Software e-stop bit:** `output_bit_register_65` provides a fast software stop. It does not replace a hardware e-stop circuit but provides sub-cycle response (2ms at 500Hz RTDE).

4. **Minimal register usage:** Only 6 output and 5 input registers are used, well within the 48 available per type. Reserved registers are documented for future expansion without protocol changes.
