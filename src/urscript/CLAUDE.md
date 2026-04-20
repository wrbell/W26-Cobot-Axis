# src/urscript — URScript Programs for the UR30 Teach Pendant

Programs that run on the UR30 side of the system. They write commands into RTDE output registers, which the bridge daemon on the Pi reads. No unit tests — manual validation on the teach pendant only.

## Program roles

| File | Role |
|------|------|
| `extrusion_control.script` | Production program — synchronizes extrusion to TCP speed; primary demo program |
| `test_basic.script` | Nine sub-test sanity check: init, enable, extrude, retract, home, e-stop, speed-sync, fault, status |
| `test_calibration.script` | Pump displacement characterization (move → measure volume dispensed) |
| `slicer_mblack06mm.script` | Wrapped output from external slicer for 0.6 mm nozzle; demonstrates integration with a CAM workflow |

## Register source of truth

**`docs/register_allocation.md`** is the single source of truth for the RTDE register map. URScript and `src/bridge/config.py` must stay in sync with it. When adding or renaming a register:

1. Update `docs/register_allocation.md`.
2. Update `src/bridge/config.py` (`Out` / `In` classes + `OUTPUT_REGISTERS` / `INPUT_REGISTERS` dicts).
3. Update every `.script` in this directory that references the old name.
4. Run `python -m pytest src/bridge/tests/test_config.py`.

## Shared-constant gotcha

`MAX_EXTRUSION_RATE` is enforced in **two places**:

- Bridge daemon clamp (`config.py`).
- URScript safety check (top of each program).

The URScript clamp is belt-and-braces (the bridge always clamps too), but the UR30 will happily send anything — the teach-pendant side is the first defense. Update both when raising the limit.

## Testing

No `pytest` target. Validation is manual:

1. Load `.script` onto the UR30 via USB or the Dashboard URCap upload.
2. Start it from the teach pendant with the bridge daemon + Klipper running on the Pi.
3. Watch the Mainsail console (if attached) and the bridge's CSV log (`data_logger.py` output) for expected state transitions.

## Where this fits in the report

URScript is the "input side" of the closed-loop controller. Cited in Report Section F.2 (Software Architecture) and Section G.2 (testing — `test_basic.script` is the nine-point acceptance test). Presentation slide 9.
