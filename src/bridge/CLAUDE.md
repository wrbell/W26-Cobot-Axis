# src/bridge — RTDE-to-Klipper Bridge Daemon

Python daemon that translates UR30 RTDE register writes into Klipper G-code. Runs on the Pi as a systemd service. **Stateless** translator between two async systems: RTDE polls at 125 Hz, Klipper responds asynchronously.

## Module index

| File | Role |
|------|------|
| `bridge_daemon.py` | Main control loop — reads RTDE, writes Klipper, handles state transitions |
| `__main__.py` | `python -m bridge` entry point |
| `config.py` | Register mappings (`Out`/`In` classes), connection defaults, constants |
| `rtde_client.py` | Thin wrapper over `ur_rtde` (with stub fallback when lib is missing) |
| `klipper_client.py` | Unix socket client for `~/printer_data/comms/klippy.sock` (JSON-RPC; MainsailOS default) |
| `watchdog.py` | Stops stepper if no RTDE data for 500 ms |
| `extrusion_profile.py` | Linear / polynomial / lookup-table rate shaping; profiles in `profiles.json` |
| `klipper_status.py` | Polls `tmc2209 manual_stepper pump` status (4 Hz) |
| `stallguard_accumulator.py` | StallGuard event buffer + CSV dump |
| `dashboard_client.py` | UR Dashboard Server client (for halting robot on fault) |
| `data_logger.py` | Per-cycle CSV logger for Phase 4 test runs |

## Conventions

- **Single source of truth for register names**: `config.py` `Out` / `In` classes. URScript and the bridge must agree via `docs/register_allocation.md`.
- `MAX_EXTRUSION_RATE` is defined in `config.py` **and** duplicated in URScript safety clamps — update both together.
- Logging: `logging.getLogger("bridge")`; systemd captures stdout.
- No threading — single-threaded main loop. RTDE/Klipper I/O is synchronous on purpose (predictable timing beats throughput here).
- Tests do not touch hardware. Mocks live in `tests/conftest.py` (`FakeKlippy`, fake RTDE socket).

## Test + lint

```bash
python -m pytest src/bridge/tests/ -v   # 479 tests, ~1.5s, 100% coverage target
ruff check src/bridge/
```

One test file per module (e.g. `test_rtde_client.py`). When adding a new bridge module, add a parallel test file in the same commit and keep coverage at 100%.

## Gotchas

- `ur_rtde` is optional at import time — `rtde_client.py` falls back to a stub so tests and dev machines without the C++ library still work. Don't import `ur_rtde` at module top level.
- RTDE register indices (0-based `_0`, `_64`, etc.) look like typos — they aren't. See `docs/register_allocation.md`.
- Watchdog timeout is measured in wall clock, not loop cycles, so it stays correct during scheduling jitter.

## When editing

- Report-relevant? Bridge design is cited in Report Section F.2 (Software Architecture). Keep `bridge_daemon.py` small and readable — figures in the final report reference it.
- Hardware-in-the-loop validation plan: `docs/design/hitl_plan.md`.
