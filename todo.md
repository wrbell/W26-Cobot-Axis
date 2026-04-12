# Project TODO List

## Architecture

```
                         ┌─── Pi400 (optional HMI / SSH / Mainsail web UI)
                         │
UR30  ──RTDE/TCP-IP──▶  Pi (Klipper host + RTDE bridge)  ──USB Serial──▶  SKR Pico (RP2040)  ──▶  Stepper Motor  ──▶  Pump
```

- [ ] **Decide which Pi model** for headless control node (Pi 4B recommended)
- Pump and motor will be **provided to the team** — specs TBD on receipt

---

## Design Process (Bolton's 7 Steps)

### Step 1: The Need — Complete
- [x] Identify the need — UR30 lacks a native extrusion axis for metal paste dispensing
- [x] Document in `reqs/initial_scope.md`

### Step 2: Analysis of the Problem — Complete
- [x] Formal problem analysis → `docs/problem_analysis.md`
- [x] Latency analysis → `docs/latency_analysis.md`

### Step 3: Preparation of a Specification — In Progress
- [x] RTDE register allocation finalized → `docs/register_allocation.md`
- [x] **Formal design specification** → `docs/design_specification.md` — 25 "shall" statements, interface tables, performance targets
- [x] Pin assignment table (rough draft) → `docs/phase2/pin_assignments.md`
- [x] Power budget worksheet (rough draft) → `docs/phase2/power_budget.md`

### Step 4: Generation of Possible Solutions — In Progress
- [x] Lingua Franca vs Klipper → `trades/lingua_franca_vs_klipper.md` (Klipper: 4.70 vs 1.95)
- [x] Communication protocol → `trades/comms.md` (RTDE: 4.85 vs next-best 3.30)
- [x] MCU platform → `trades/mcu.md` (SKR Pico selected)
- [ ] **Location trade study** — end effector vs base-mounted vs gantry (Dawood)

### Step 5: Selection of a Suitable Solution — Complete
- [x] Klipper selected
- [x] RTDE selected
- [x] SKR Pico selected (on hand)
- [x] Architecture documented in README and CLAUDE.md
- [ ] **Present trade studies to Prof. Pannier** — address Lingua Franca suggestion

### Step 6: Production of a Detailed Design — In Progress
- [x] Circuit diagram description (rough draft) → `docs/phase2/circuit_schematic.md`
- [ ] Circuit layout (physical arrangement) — Dawood + Willem
- [x] Block diagram of functions/signals (rough draft) → `docs/phase2/block_diagram.md`
- [x] Bill of materials with purchasing instructions (rough draft) → `docs/phase2/bom.md`
- [x] Buck converter selection → `docs/phase2/buck_converter.md` — Pololu D24V22F5
- [ ] Engineering analysis (motor loads — pending hardware receipt)
- [ ] 3D-printed component designs (Dawood)

### Step 7: Production of Working Drawings — Upcoming
- [ ] Final circuit schematics
- [ ] Final mechanical drawings / CAD
- [ ] Wiring diagrams with pin assignments
- [ ] System block diagram

---

## Phase 1: Ideation and Scope — Complete (Week 5)

- [x] Team formation and role assignment
- [x] Project idea submitted
- [x] Scope defined — `reqs/initial_scope.md`
- [x] Instructor go/no-go received

---

## Phase 2: Design and Preliminary Analysis — In Progress (Weeks 6–8, target Mar 1)

**Deliverable:** Written memo (PDF, ≤5 pages) with preliminary design, BOM, and analysis.

### Required Diagrams
- [x] **Block diagram of functions/signals** — rough draft → `docs/phase2/block_diagram.md` (needs redraw in draw.io/Visio)
- [x] **Circuit diagram (schematic)** — rough draft → `docs/phase2/circuit_schematic.md` (needs redraw in KiCad/draw.io)
- [ ] **Circuit layout** — physical arrangement (Dawood + Willem)
- [ ] **Mechanical component sketches** (Dawood)

### Trade Studies
- [x] Lingua Franca vs Klipper → `trades/lingua_franca_vs_klipper.md`
- [x] Communication protocol → `trades/comms.md`
- [x] MCU platform → `trades/mcu.md`
- [ ] **Location trade study** (Dawood)
- [ ] **Present trade studies to Prof. Pannier**

### Electrical Documentation
- [x] **Pin assignment table** — rough draft → `docs/phase2/pin_assignments.md`
- [x] **Power budget worksheet** — rough draft → `docs/phase2/power_budget.md`
- [x] **Select buck converters** — Pololu D24V22F5 selected → `docs/phase2/buck_converter.md`

### Bill of Materials
- [x] **Draft BOM** with DigiKey/Newark part numbers → `docs/phase2/bom.md` (~$183 total, 28 items, most P/Ns verified)
- [x] **Write purchasing instructions** — included in `docs/phase2/bom.md`

### 3D-Printed Components (Dawood)
- [ ] Identify which components need 3D printing
- [ ] Design sketches for each part

### Engineering Analysis
- [x] Latency analysis → `docs/latency_analysis.md`
- [x] Problem analysis → `docs/problem_analysis.md`
- [ ] **Motor load calculations** — pending hardware receipt
- [ ] **Torque analysis** — pending hardware receipt
- [x] **Power budget analysis** — rough draft → `docs/phase2/power_budget.md`

### Phase 2 Memo Draft
- [x] **Memo text draft** — all 8 sections (~1,400 words) → `docs/phase2/memo_draft.md`
- [ ] Redraw block diagram in draw.io/Visio (from `docs/phase2/block_diagram.md`)
- [ ] Redraw circuit schematic in KiCad/draw.io (from `docs/phase2/circuit_schematic.md`)
- [x] Verify DigiKey/Newark part numbers and stock — 10 of 14 verified/corrected; 2 unverified (MicroSD, USB cable), 2 need final check (wire spools, screw terminals)
- [ ] Dawood: write Section 5 (mechanical concept) + Figures 3–4

### Phase 2 Submission Checklist (due Mar 1)

**Willem (before Feb 28):**
- [ ] Redraw block diagram in draw.io or Visio → export as Figure 1
- [ ] Redraw circuit schematic in KiCad or draw.io → export as Figure 2
- [ ] Paste memo text from `docs/phase2/memo_draft.md` into Word template
- [ ] Insert all 5 tables from memo draft
- [ ] Insert Figures 1–2, add captions

**Dawood (before Feb 28):**
- [ ] Write Section 5 (mechanical concept, ~150 words)
- [ ] Create Figure 3 (physical layout sketch) and Figure 4 (mechanical concept)
- [ ] Location trade study (even a brief rationale is fine for the memo)

**Together (Feb 28 – Mar 1):**
- [ ] One person edits the entire document for consistency
- [ ] Verify total page count ≤ 5
- [ ] Export to PDF, submit to instructor

**Already done (no action needed):**
- [x] Memo text — 8 sections, ~1,400 words → `docs/phase2/memo_draft.md`
- [x] BOM with verified part numbers (~$183) → `docs/phase2/bom.md`
- [x] All electrical docs (pin table, power budget, buck converter)
- [x] 3 trade studies with scores

---

## Software Development — No Hardware Required

All software in `src/`. Can be developed and tested without physical hardware.

### Bridge Daemon (`src/bridge/`)

#### Core — Written
- [x] `config.py` — register mappings, connection defaults, constants
- [x] `klipper_client.py` — klippy Unix socket client (connect, G-code, status query, stepper commands)
- [x] `rtde_client.py` — ur_rtde wrapper with stub fallback for dev without robot
- [x] `bridge_daemon.py` — main loop: RTDE read → translate → Klipper command → status writeback
- [x] `__main__.py` — entry point for `python -m bridge`
- [x] Register allocation implemented matching `docs/register_allocation.md`
- [x] E-stop, homing, enable/disable, mode switching
- [x] Reconnection logic for dropped RTDE or Klipper connections
- [x] `--dry-run` mode for testing without Klipper

#### Enhancements — Written
- [x] **Klipper status subscription** — TMC2209 driver status polling with stall detection (`klipper_status.py`)
- [x] **Speed-proportional extrusion mode** — bridge-computed rate from TCP speed × multiplier
- [x] **Data logging** — 17-column CSV with file rotation and event annotations (`data_logger.py`)
- [x] **Watchdog timer** — RTDE timestamp-based stale detection, 0.5s timeout (`watchdog.py`)
- [x] **Configurable extrusion profiles** — linear, polynomial, lookup table (`extrusion_profile.py`, `profiles.json`)
- [x] **Dashboard Server client** — UR30 port 29999 lifecycle management (`dashboard_client.py`)
- [x] **StallGuard accumulator** — Pi-side 5-minute history buffer for batch data reporting (`stallguard_accumulator.py`)

#### Testing — 479 tests across 10 files (100% coverage)
- [x] **Unit tests for `klipper_client.py`** — 44 tests, mock Unix socket, JSON protocol, error handling
- [x] **Unit tests for `rtde_client.py`** — 44 tests, stub mode, register read/write, import fallback
- [x] **Unit tests for `bridge_daemon.py`** — 146 tests, command translation, e-stop, mode switching, reconnection, subsystems, CLI
- [x] **Unit tests for StallGuard** — 49 tests, bridge integration with stallguard status, poll loop error handling
- [x] **Unit tests for `watchdog.py`** — 15 tests, timeout detection, feed/reset, stale timestamp logic, disabled mode
- [x] **Unit tests for `data_logger.py`** — 29 tests, CSV columns, file rotation, decimation, annotations, lifecycle, error recovery
- [x] **Unit tests for `extrusion_profile.py`** — 46 tests, linear/polynomial/lookup profiles, JSON loading, fallback, edge cases
- [x] **Unit tests for `dashboard_client.py`** — 38 tests, TCP server mock, status queries, control commands, DashboardPoller, error handling
- [x] **Unit tests for `stallguard_accumulator.py`** — 34 tests, NamedTuple, capacity, overflow, thread safety, stats, CSV dump, poller/bridge wiring
- [x] **Config validation tests** — 24 tests: register name format, no duplicates, sane constants (`test_config.py`)
- [ ] **URSim integration testing** — moved to Phase 3 "Pre-Hardware: URSim Validation" section

### Klipper Configuration (`src/klipper/`)
- [x] `printer.cfg` — SKR Pico config with `[manual_stepper pump]`, TMC2209 UART, E-axis driver
- [x] `moonraker.conf` — Moonraker API config (port 7125, trusted clients, CORS, update manager)
- [x] `mainsail.cfg` — Pump-specific macros (PUMP_STATUS, PUMP_TEST, PUMP_ENABLE/DISABLE, PUMP_ZERO)

### URScript (`src/urscript/`)
- [x] `extrusion_control.script` — helper functions, `pump_on()`/`pump_off()` for slicer integration, `extrude_along_path()` for speed-sync, retraction
- [x] `test_basic.script` — system validation test (10 sub-tests: A–I + G2; Sub-test G tests constant-rate multi-waypoint pattern, G2 tests speed-sync)
- [x] `test_calibration.script` — pump calibration (5 sub-tests: A linearity, B speed-sync gravimetric, B2 constant-rate gravimetric, C retraction, D latency)

### StallGuard Dual-Core Firmware (`src/klipper_mods/`)

#### Core — Written
- [x] `stallguard_shared.h` — Shared SRAM struct + spinlock #16 helpers
- [x] `core1_stallguard.c` — Core1 entry: gpio16 init, debounce loop, FIFO launch protocol
- [x] `stallguard_command.c` — Klipper DECL_COMMAND: `stallguard_query`, `stallguard_clear`
- [x] `klippy_extras/stallguard_monitor.py` — Klippy host module: 20 Hz poll, Moonraker status object
- [x] `Makefile.patch` — Add source files to Klipper rp2040 build
- [x] `main.c.patch` — Call `core1_launch()` before `sched_main()` in `armcm_main()`
- [x] `README.md` — Build & deploy instructions

#### Verification
- [x] Patches verified against real Klipper source tree (`vendor/klipper/`)
- [x] Linker symbol `_ram_vectortable_start` matches Klipper's `rpxxxx_link.lds.S`
- [x] Register addresses verified against RP2040 datasheet
- [x] GPIO16 correct for SKR Pico E-stepper DIAG pin
- [x] Spinlock #16 safe (not used by Klipper)
- [ ] **Build verification on Pi** — needs hardware (`make` with overlay in Klipper tree)
- [ ] **Runtime verification** — needs hardware (stall motor, check Moonraker status)

#### Audit Fixes (Feb 24) — All Applied
- [x] Fixed `_vector_table` → `_ram_vectortable_start` linker symbol in `core1_stallguard.c`
- [x] Fixed `last_stall_us` → `last_stall_ticks` naming mismatch in `stallguard_monitor.py`, README, hitl_plan, tests
- [x] Added `printer.add_object()` call in `stallguard_monitor.py` (Moonraker couldn't discover module)
- [x] Added dedicated command queue allocation in `stallguard_monitor.py` (was competing with stepper queue)
- [x] Added error count suppression in `stallguard_monitor.py` poll loop (was silently swallowing errors)
- [x] Fixed race condition: `clear_request` now read under spinlock in `core1_stallguard.c`
- [x] Added file existence validation in `deploy.sh` before sed patching (Makefile, main.c)
- [x] Added ur_rtde installation check in `dev-sync.sh` (warns if bridge will run in stub mode)

### Deployment — Written
- [x] `requirements.txt` — Python dependencies (ur-rtde, pytest, ruff) with Windows/ARM install notes
- [x] `src/systemd/w26-bridge.service` — systemd service, auto-start after Klipper
- [x] `deploy.sh` — 11-step deployment script (deps, configs, firmware, verification) + StallGuard overlay (Step 6b)
- [x] `scripts/dev-sync.sh` — Fast rsync to Pi for iterative development (<5s)
- [x] `SETUP.md` — step-by-step setup instructions for fresh Pi
- [x] `DEVELOPMENT.md` — developer & test environment setup (no hardware needed)

### HITL Test Plan — Written
- [x] `docs/design/hitl_plan.md` — TP-06 StallGuard test procedures, URSim dev bench topology, deploy workflow
- [ ] **Execute TP-06** — needs hardware

### CI/CD Pipeline

#### Tier 1: Pre-commit Checks (GitHub Actions, runs on every push, <30s)
- [x] **Create `.github/workflows/ci.yml`** — lint + test on every push
  - `ruff check src/bridge/`
  - `python -m pytest src/bridge/tests/ -v`
  - `shellcheck deploy.sh scripts/dev-sync.sh`
- [x] **Add status badge** to README.md

#### Tier 2: Firmware Build Verification (runs on `src/klipper_mods/` changes)
- [x] **Add firmware build job to CI** — triggered on changes to `src/klipper_mods/**`
  - Clone Klipper source
  - Copy overlay files into Klipper tree
  - Run the same sed commands from deploy.sh
  - `make menuconfig` (non-interactive, write .config)
  - `make` — verify firmware compiles with `arm-none-eabi-gcc`
  - Upload `klipper.uf2` as build artifact
- [x] **Install cross-compiler in CI** — `apt install gcc-arm-none-eabi`

#### CI/CD Setup Guide
- [x] **Write GitHub Actions setup guide** → `docs/design/ci_cd_guide.md` — prerequisites, Tier 1 vs 2 vs 3, verifying workflows, reading build results, downloading firmware artifacts, manual trigger, troubleshooting

#### Tier 3: Deploy-to-Pi (manual trigger or tagged release)
- [ ] **Add deploy workflow** — manual dispatch or on `v*` tag
  - SSH to Pi (via self-hosted runner or SSH action with secrets)
  - `git pull` on Pi
  - `bash deploy.sh` (or `--skip-flash` if no firmware changes)
  - Smoke test: `systemctl status klipper w26-bridge`
  - `curl http://localhost:7125/printer/objects/query?stallguard_monitor`
- [ ] **Store Pi SSH credentials** as GitHub Actions secrets (`PI_HOST`, `PI_SSH_KEY`)

#### Tier 4: Quality Gates (nice-to-have, impressive for capstone)
- [x] **Test coverage report** — `pytest --cov` with `coverage.xml` artifact in CI
- [x] **YAML/config linting** — `yamllint` on `.github/workflows/*.yml` (separate CI job); `.yamllint` config at repo root
- [x] **Dependency security scan** — `pip-audit` in CI to flag known CVEs in ur-rtde, pytest, ruff
- [x] **Firmware size check** — `arm-none-eabi-size klipper.elf` in firmware workflow, fails if `.bss + .data` exceeds 200 KB (SRAM budget gate)
- [x] **Documentation link checker** — inline Python script in CI verifies all `[text](path)` links in markdown files resolve
- [x] **Release workflow** — `.github/workflows/release.yml`: on `v*` tag, runs full CI + firmware build, creates GitHub Release with `klipper.uf2` attached, auto-generates changelog
- [x] **mypy type checking** — `mypy src/bridge/ --exclude tests/` in CI; `pyproject.toml` with per-module overrides for optional-connection pattern
- [x] **Python version matrix** — lint-and-test runs on Python 3.9 (Pi) and 3.11 (dev) to catch compatibility issues
- [x] **Patch freshness** — `.github/workflows/patch-freshness.yml`: weekly cron verifies StallGuard sed patches still apply against upstream Klipper
- [x] **deploy.sh dry-run** — `bash -n` syntax check + `shellcheck --severity=warning` in separate deploy-check CI job
- [x] **codespell** — spell checks all docs and source; `-L "ot"` for false positive suppression
- [x] **Dependabot** — `.github/dependabot.yml`: weekly auto-PRs for pip dependencies and GitHub Actions versions

#### Stretch: Batch StallGuard Data Reporting (instead of live)
Investigate changing StallGuard measurement reporting from live 20 Hz polling to batch mode — buffer measurements on-device and send them back periodically.

**Hardware research findings (Feb 24):**
- RP2040 has 264 KB SRAM total, estimated ~130–160 KB free after Klipper (need `arm-none-eabi-size klipper.elf` to confirm)
- SKR Pico flash is **2 MB** (W25Q16), NOT 16 MB — ~1.9 MB free after firmware
- **Flash is NOT viable** for runtime logging: sector erase takes ~85 ms, which blocks all interrupts and kills step timing (up to 11k missed step events at max step rate)
- **66 KB SRAM buffer** (5 min @ 20 Hz × 11 bytes/sample) is too large — insufficient margin above Klipper runtime needs
- **16 KB SRAM ring buffer** is the safe max: gives ~74 seconds at 20 Hz (1,489 samples)
- Klipper MCU protocol max message = 64 bytes, no native bulk transfer — would need custom `stallguard_dump` command to walk the buffer in 50-byte chunks
- **Recommended approach:** Pi-side buffering in bridge daemon (`collections.deque(maxlen=6000)` = 5 min), not MCU-side. Only add MCU buffer if Pi connection can drop mid-run and post-hoc recovery is needed.

**Tasks:**
- [ ] Run `arm-none-eabi-size ~/klipper/out/klipper.elf` on first hardware build to get exact SRAM usage
- [x] Implement Pi-side 5-minute StallGuard accumulator in bridge daemon (deque in Python, zero MCU changes)
- [x] Add periodic CSV dump or Moonraker-accessible endpoint for accumulated data (`dump_to_csv()` method + 4 tests)
- [ ] **(Stretch)** If MCU-side buffering is needed: add 16 KB SRAM ring buffer in `core1_stallguard.c` + `stallguard_dump` command
- [ ] Evaluate whether 20 Hz polling rate can be reduced (e.g., 5 Hz) to extend buffer duration with same memory

#### Developer Setup
- [ ] **Install ur-rtde on macOS** — no pre-built wheel on PyPI; needs `brew install cmake boost` then `pip install ur-rtde` from source. Low priority (stub mode works for tests) but needed if testing RTDE against URSim from Mac.

#### Known Audit Issues (not yet fixed — low priority)
- [x] **deploy.sh uses GNU sed** — added OS detection: `SED_INPLACE` array handles GNU vs BSD sed.
- [x] **systemd service hardcodes `/home/pi/`** — replaced with `%h` systemd specifier (expands to User= home dir).
- [x] **RTDE connection has no configurable timeout** — added `RTDE_CONNECT_TIMEOUT = 5.0` + `socket.setdefaulttimeout()` wrapper in `connect()`.
- [x] **DASHBOARD_TIMEOUT defined but unused** — was already wired up (constructor accepts timeout, applies via `settimeout()`).
- [x] **TIMER_TIMERAWL hardcoded** — replaced bare `0x40054028` with `#define TIMER_BASE` + `#define TIMER_TIMERAWL` (datasheet §4.6.5 reference).
- [x] **gpio16 conflicts with filament runout sensor** — documented in `src/klipper_mods/README.md` "Hardware Notes" section.

### Design Documents — Complete
All software features are being designed before implementation. Design docs in `docs/design/`.

- [x] **Phase 2 deliverables planning** → `docs/design/phase2_deliverables.md`
- [x] **Bridge enhancements design** → `docs/design/bridge_enhancements.md`
- [x] **Testing strategy design** → `docs/design/testing_strategy.md`
- [x] **Klipper/Moonraker config design** → `docs/design/klipper_config.md`
- [x] **URScript programs design** → `docs/design/urscript_programs.md`
- [x] **Deployment design** → `docs/design/deployment.md`
- [x] **Phase 3 integration plan** → `docs/design/integration_plan.md`
- [x] **Phase 4 test procedures** → `docs/design/test_procedures.md`
- [x] **Network architecture** → `docs/design/network_architecture.md`
- [x] **Phase 2 memo outline** → `docs/design/phase2_memo_outline.md`
- [x] **Final report outline** → `docs/design/final_report_outline.md`
- [x] **Update `docs/pi_power.md`** — fixed stale dual-Pi architecture references
- [x] **Stepper driving design** → `docs/design/stepper_driving.md` — consolidated justification for manual_stepper, TMC2209 config, step generation pipeline, calibration

### Release v1.0.0 — Pre-Hardware

Software-complete milestone. All bridge code is written and tested (479 tests, 100% coverage). Tag v1.0.0 before hardware arrives so we have a known-good baseline to deploy.

#### Software Fixes (code changes needed)
- [x] **Add `SYNC=0` to `stepper_move()`** — `klipper_client.py:150` sends `MANUAL_STEPPER STEPPER=pump MOVE=... SPEED=...` without `SYNC=0`. Klipper blocks the gcode response until the move physically completes — at 125 Hz main loop this freezes the bridge for the entire move duration (seconds). Append ` SYNC=0` to the gcode string. Update tests.
- [x] **Add `SYNC=0` to `stepper_set_position()`** — same issue at `klipper_client.py:157`. SET_POSITION doesn't block as long but should be non-blocking for consistency. Update tests.

#### Validation (no code changes — just run/review things)
- [ ] **URSim smoke test** — spin up URSim Docker, connect bridge with `--dry-run`, verify RTDE register round-trip, mode transitions, e-stop. Proves the RTDE path works before touching real hardware.
- [x] **deploy.sh review** — read through deploy.sh, verify step order makes sense, no stale paths. Can't fully dry-run without Pi but review logic.
- [x] **printer.cfg review** — confirm pin assignments, TMC2209 UART addresses, motor defaults are sensible starting points (`rotation_distance` will need calibration on hardware).
- [ ] **Release candidate tag** — push `v1.0.0-rc1`, verify release workflow fires: CI green, firmware .uf2 builds, GitHub Release created with artifacts.

#### Release
- [ ] **Tag v1.0.0** — push tag, release workflow (`.github/workflows/release.yml`) creates GitHub Release with klipper.uf2 + PDFs. This is the "software-complete, ready for hardware" milestone.

---

## Phase 3: Build and Additional Design/Analysis (Weeks 9–11, Mar 2–22)

Full integration plan with troubleshooting: `docs/design/integration_plan.md`

### Pre-Hardware Checklist (before first power-on)

These are known gotchas from the end-to-end audit. Check each before testing.

#### Physical Hardware (Pi + SKR Pico)
- [ ] **Install DIAG jumper** on SKR Pico E-stepper header — connects TMC2209 DIAG output to gpio16. Without it, gpio16 floats and StallGuard always reads "no stall".
- [ ] **Update printer.cfg serial path** — replace `PLACEHOLDER` in `[mcu]` with actual device from `ls /dev/serial/by-id/usb-Klipper_rp2040_*`. deploy.sh does this automatically.
- [ ] **Verify ur_rtde installed on Pi** — `python -c "import rtde_receive; print('OK')"`. If it fails, bridge runs in stub mode (no real RTDE). ARM binary wheel may need `pip install ur-rtde --no-cache-dir`.
- [ ] **Verify Klipper socket path** — default `/tmp/klippy_uds` is correct for MainsailOS. Check with `ls -la /tmp/klippy_uds`.
- [x] ~~**Verify Pi username is `pi`**~~ — systemd service now uses `%h` specifier (expands to home dir), no longer hardcoded.
- [ ] **Calibrate motor rotation_distance** — `printer.cfg` uses generic `rotation_distance: 40` (40mm/rev). Measure actual pump displacement per revolution and update.

#### URSim on Windows
- [ ] **Open Windows firewall for port 30004** — `New-NetFirewallRule -DisplayName "URSim RTDE" -Direction Inbound -LocalPort 30004 -Protocol TCP -Action Allow`
- [ ] **Docker Desktop with WSL2 backend** — URSim requires Linux containers. Verify Docker is running Linux mode, not Windows mode.
- [ ] **Expose correct Docker ports** — `docker run -p 30004:30004 -p 6080:6080 -p 29999:29999 ...`. Port 30004 = RTDE, 6080 = noVNC teach pendant, 29999 = Dashboard (optional).
- [ ] **Find Windows IP** — `ipconfig` → note IPv4 address. Pass to bridge: `python -m bridge --host <WINDOWS_IP>`.
- [ ] **Power on virtual robot** — in noVNC teach pendant (`http://localhost:6080`), click power on. RTDE port won't respond until robot is powered.
- [ ] **RTDE frequency** — config.py defaults to 500 Hz. URSim e-Series should match, but if connection fails, try setting `RTDE_FREQUENCY = 125` in config.py.

#### Bridge Daemon Config for URSim Testing
- [ ] **Override host IP** — `python -m bridge --host <WINDOWS_IP>` (or systemd override: `sudo systemctl edit w26-bridge`)
- [ ] **Use `--no-status-poll` if no SKR Pico** — disables TMC2209 and StallGuard queries that require real hardware
- [ ] **Use `--dry-run` for RTDE-only testing** — skips Klipper connection entirely, just logs what commands would be sent
- [ ] **Dashboard Server is opt-in** — off by default. Only enable with `--dashboard` if URSim exposes port 29999.

### Dev Bench Setup (can start now)

Full guide: `docs/dev_bench_guide.md`

- [ ] **Image SD card** — MainsailOS, hostname `w26-dev`, user `pi`, SSH enabled
- [ ] **First boot + verify** — SSH in, Klipper/Moonraker active, Mainsail web UI loads
- [ ] **Clone repo + deploy** — `git clone` then `bash deploy.sh` (builds firmware, installs service)
- [ ] **URSim on Windows** — Docker Desktop, `docker run` with ports 30004/29999/6080, power on virtual robot
- [ ] **Configure bridge for URSim** — systemd override: `--host <WINDOWS_IP> --log-level DEBUG`
- [ ] **End-to-end motor test** — Mainsail console: `MANUAL_STEPPER STEPPER=pump MOVE=10 SPEED=5`
- [ ] **RTDE round-trip** — load `test_basic.script` in URSim, verify motor responds via bridge

### Pre-Hardware: URSim Validation (can start now)

- [ ] **Set up URSim on Windows** — `docker run --platform=linux/amd64 -e ROBOT_MODEL=UR30 -p 30004:30004 -p 29999:29999 -p 6080:6080 universalrobots/ursim_e-series`
- [ ] **Load slicer output into URSim** — verify `src/provided/Mblack0.6mm.script` executes cleanly (no joint limits, no singularities, path looks correct in 3D view)
- [ ] **Test bridge daemon against URSim** — connect via RTDE on port 30004, verify register read/write, mode transitions
- [ ] **Load wrapped slicer program into URSim** — test `pump_on()`/`pump_off()` wrapping of slicer output with bridge daemon running (Klipper side mocked)

### Stage 1: Klipper on Pi (Week 9, Day 1)

- [ ] Flash MainsailOS onto Pi SD card (enable SSH, set hostname `w26-pi`)
- [ ] Boot Pi, verify SSH access: `ssh pi@w26-pi.local`
- [ ] Verify `klipper` and `moonraker` services loaded: `systemctl status klipper moonraker`
- [ ] Verify Mainsail web UI responds at `http://w26-pi.local` (errors OK — no printer.cfg yet)

### Stage 2: SKR Pico Firmware (Week 9, Day 1–2)

- [ ] Run `deploy.sh` — handles Klipper config, StallGuard overlay, firmware build, and flash
- [ ] Or manually: Build Klipper MCU firmware: `make menuconfig` → RP2040, no bootloader, W25Q080 CLKDIV 2, USB
- [ ] Flash via BOOTSEL: hold button, plug USB, copy `klipper.uf2` to `RPI-RP2` drive
- [ ] Verify USB serial enumeration: `ls /dev/serial/by-id/usb-Klipper_rp2040_*`
- [ ] Deploy `printer.cfg` to `~/printer_data/config/`, update `[mcu]` serial path
- [ ] Restart Klipper, confirm `Printer is ready` in klippy.log and Mainsail shows green
- [ ] Verify StallGuard via Moonraker: `curl http://localhost:7125/printer/objects/query?stallguard_monitor`

### Hardware Configuration & Calibration

Full guide: `docs/config_guide.md` — covers motor current, rotation distance, velocity/accel, StealthChop, bridge safety limits, extrusion multiplier, URScript waypoints, and cross-file sync.

- [ ] **Determine motor specs** — step angle, coil resistance, rated current (no datasheet procedure)
- [ ] **Calibrate run_current** — experimental sweep from 0.3A, thermal + stall testing
- [ ] **Calibrate rotation_distance** — measure actual pump displacement per revolution
- [ ] **Tune velocity/accel** — find mechanical stall limit, set to 80%
- [ ] **Teach URScript waypoints** — `START_POSE`, `MID_POSE`, `END_POSE` in all 3 scripts
- [ ] **Sync cross-file values** — max speed, accel, extrusion multiplier across printer.cfg / config.py / URScript

### Stage 3: First Stepper Motion (Week 9, Day 2–3)

- [ ] Wire stepper motor to SKR Pico E-axis connector (identify coils with multimeter)
- [ ] Apply 24V to SKR Pico VIN (verify polarity first)
- [ ] Send test G-code via Mainsail console:
  - `MANUAL_STEPPER STEPPER=pump ENABLE=1`
  - `MANUAL_STEPPER STEPPER=pump SET_POSITION=0`
  - `MANUAL_STEPPER STEPPER=pump MOVE=10 SPEED=5` → observe motor rotates
- [ ] Verify direction: positive MOVE = extrude, negative = retract (flip `dir_pin` polarity if wrong)
- [ ] Test speeds: 5, 25, 50 mm/s
- [ ] Disable stepper: `MANUAL_STEPPER STEPPER=pump ENABLE=0`

### Stage 4: TMC2209 Tuning (Week 9, Day 3–4)

- [ ] Read motor nameplate current rating
- [ ] Set `run_current` to 70–80% of rating, `hold_current` to 50–70% of `run_current`
- [ ] Run sustained motion test: `MOVE=1000 SPEED=25` (~40s), monitor TMC2209 temperature (< 80°C target)
- [ ] Verify StealthChop operation (should be near-silent at low speeds)
- [ ] If motor stalls under pump load: increase `run_current` by 0.1A increments (do not exceed motor rating or 1.2A)
- [ ] `DUMP_TMC STEPPER="manual_stepper pump"` — verify no error flags
- [ ] Commit updated `printer.cfg` with final current settings

### Stage 5: Bridge Daemon on Pi (Week 9, Day 4–5)

- [ ] Clone repo onto Pi (or SCP `src/bridge/`)
- [ ] Install deps: `pip3 install ur-rtde` (fallback: stub mode if ARM build fails)
- [ ] Test dry-run: `python3 -m src.bridge.bridge_daemon --dry-run --log-level DEBUG`
- [ ] Test Klipper connection directly (bypass RTDE):
  ```python
  from bridge.klipper_client import KlipperClient
  k = KlipperClient("/tmp/klippy_uds")
  k.connect()
  k.stepper_move("pump", 5.0, 10.0)  # motor should move
  k.stepper_disable("pump")
  k.disconnect()
  ```

### Stage 6: RTDE Connection to UR30 (Week 10)

- [ ] Verify network: `ping <UR30_IP>`, `nc -zv <UR30_IP> 30004`
- [ ] Update `config.py` with UR30 IP address
- [ ] Test RTDE independently: read output registers, write input registers (see `docs/design/integration_plan.md` Stage 6 for test scripts)
- [ ] Load `extrusion_control.script` onto UR30 teach pendant (USB drive or SSH)
- [ ] Run bridge daemon with RTDE: `python3 -m src.bridge.bridge_daemon --host <UR30_IP> --log-level DEBUG`
- [ ] Verify bridge logs show RTDE read/write cycles at 125 Hz
- [ ] Verify teach pendant shows input register values (status, ready flag)

### Stage 7: End-to-End Smoke Test (Week 10–11)

- [ ] All services running: Klipper + Moonraker + bridge daemon + URScript program
- [ ] From UR30: enable + mode=EXTRUDE + rate=10.0 → **stepper moves** (the milestone)
- [ ] Test speed changes: ramp 0→50 mm/s, verify smooth acceleration
- [ ] Test mode transitions: extrude → retract → off
- [ ] Test e-stop: `output_bit_register_65 = True` → stepper halts immediately
- [ ] Verify status feedback: UR30 reads status=RUNNING during extrusion, IDLE when stopped
- [ ] Run `test_basic.script` Sub-tests A–F, I (no robot motion tests)
- [ ] Teach waypoints, run Sub-test G (constant-rate multi-waypoint path)
- [ ] Latency measurement (if oscilloscope available): probe step pin (gpio14), measure command-to-pulse delay

### Stage 7b: Slicer Integration (Week 11)

- [ ] Wrap `src/provided/Mblack0.6mm.script` with `pump_on()`/`pump_off()` from `extrusion_control.script`
- [ ] Load wrapped program onto UR30, run with bridge daemon active
- [ ] Verify pump runs continuously during 776-waypoint path and stops cleanly at the end
- [ ] Run calibration `test_calibration.script` Sub-test A (flow rate linearity) — determine optimal constant rate
- [ ] Run calibration Sub-test B2 (constant-rate multi-waypoint gravimetric) — verify consistent dispensing
- [ ] Tune `EXTRUSION_MULTIPLIER` and retraction parameters based on calibration results

### Stage 8: Pi400 HMI (Week 11, parallel)

- [ ] Connect Pi400 to same network (switch or WiFi)
- [ ] Verify Mainsail UI at `http://w26-pi.local` — monitor stepper status, send G-code
- [ ] Verify SSH: `ssh pi@w26-pi.local`
- [ ] Configure Moonraker trusted clients if needed

### Mechanical Assembly (Dawood, parallel with Stages 1–7)

- [ ] 3D print mounting components
- [ ] Assemble electronics onto mounting hardware
- [ ] Route and secure cabling
- [ ] Mount to end effector / robot

### Phase 3 Deliverable

- [x] **Progress memo template** drafted → `docs/phase3/progress_memo_draft.md` (fill in after hardware testing)
- [ ] **Fill in test results and placeholders** — after bench and integration testing
- [ ] **Submit progress memorandum** to instructor

---

## Phase 4: Test and Reporting (Weeks 12–13, Mar 23 – Apr 5)

Full test procedures with pass/fail criteria and data sheets: `docs/design/test_procedures.md`

### TP-01: End-to-End Functional Test (45 min, Week 12)

Verifies the full communication chain responds to all commands.

- [ ] Test all mode transitions: enable → extrude (5, 10, 25, 50 mm/s) → retract → off
- [ ] Test rate clamping: command 75 mm/s, verify clamped to 50 mm/s
- [ ] Test e-stop during motion: stepper halts, status=ERROR reported to UR30
- [ ] Test recovery from e-stop: clear fault, re-enable, verify system accepts new commands
- [ ] Test homing: position zeros, status returns to IDLE
- [ ] Record bridge daemon logs and teach pendant register screenshots at each step

### TP-02: Latency Characterization (90 min, Week 12)

Measures actual end-to-end latency; compare against 8 ms prediction in `docs/latency_analysis.md`.

- [ ] **Method A (software):** RTDE timestamp comparison — measures UR30-to-bridge latency segments
- [ ] **Method B (oscilloscope):** Probe step pin (gpio14), single-shot trigger on first pulse after cold-start command — 10 measurements
- [ ] **Method C (step-change):** Steady 10 mm/s → step to 30 mm/s, capture frequency transition — 50 measurements
- [ ] Compute statistics: mean, std dev, P95, P99, min, max
- [ ] **Pass criteria:** P95 < 20 ms, no outlier > 100 ms
- [ ] Generate latency histogram figure for final report

### TP-03: Speed Accuracy Test (60 min, Week 12)

Quantifies commanded vs actual speed across operating range.

- [ ] Steady-state accuracy: measure step frequency at 5, 10, 20, 30, 50 mm/s (extrude + retract), 5 readings each
- [ ] Compute steady-state error for each setpoint (target: < 2%)
- [ ] Transient response: oscilloscope capture of 10→30, 30→10, 0→50, 50→0 mm/s step changes
- [ ] Measure rise/fall times
- [ ] Rapid alternation: 10↔30 mm/s at 1 Hz for 10 cycles — no stalls

### TP-04: Fault Handling Test (75 min, Week 13)

Injects each failure mode from the problem analysis and verifies safe response.

- [ ] **TP-04a: RTDE disconnect** — pull Ethernet cable during extrusion → stepper stops within 2s, ERR_COMMS_LOST reported, auto-reconnects on cable restore
- [ ] **TP-04b: Stepper stall** — manually block motor shaft → document open-loop behavior (no detection without StallGuard), `DUMP_TMC` status, motor temperature
- [ ] **TP-04c: Klipper crash** — `kill -9 klippy` during extrusion → stepper stops (MCU host timeout), bridge detects and reports error, recovers on Klipper restart
- [ ] **TP-04d: USB disconnect** — pull USB cable → stepper stops immediately, Klipper enters shutdown, bridge reports fault, recovers after reconnect + restart

### TP-05: Endurance Test (90 min, Week 13)

60-minute continuous run at representative speeds.

- [ ] Speed profile: ramp to 20 mm/s → alternate 15/25 every 30s → 50 mm/s burst → ramp down
- [ ] Temperature monitoring every 10 min: TMC2209 (< 100°C), motor (< 80°C), Pi CPU (< 80°C), RP2040
- [ ] Zero communication errors in bridge log over 60 min
- [ ] No speed drift: post-test frequency within 1% of initial measurement
- [ ] 24V current draw within 2A budget (if clamp meter available)

### URScript Test Programs on Hardware

- [ ] Run full `test_basic.script` (Sub-tests A–I + G + G2) with taught waypoints — all sub-tests pass
- [ ] Run full `test_calibration.script` (Sub-tests A, B, B2, C, D) — record all calibration data
- [ ] Finalize `EXTRUSION_MULTIPLIER`, retraction parameters, and Klipper accel/velocity from calibration results

### Stretch Goals (if time permits)

- [x] **StallGuard torque feedback** — WRITTEN, needs hardware validation. TMC2209 DIAG → Core1 → Klipper MCU command → klippy extras → RTDE → URScript. See `src/klipper_mods/` and `docs/design/hitl_plan.md`. Would change TP-04b from open-loop to closed-loop stall detection.
- [ ] **G-code timeshifting** — compensate Klipper lookahead buffer latency
- [ ] **URCap** for teach pendant UI (Java SDK)

### Analysis Assignment (Due Apr 2, Canvas)

From Dr. Pannier check-in (Feb 24):

- [ ] **Motor load calculations** — MATLAB/Simulink model to verify stepper motor is not overloaded by pump, and UR30 power supply can handle the current draw (V=IR)
- [ ] **Motor ramp simulation** — differential equation model of motor during extrusion ramp-up to verify current does not exceed driver/supply limits

### Final Report (Due Apr 23)

- [ ] **Write final report** (PDF, ≤2000 words)
- [ ] **Map to Bolton's 7-step design process**
- [ ] **Relate to course topics** — control systems, circuits, actuators, microcontrollers, system models
- [ ] **Team member work listing**
- [ ] **Figures and tables** — latency histogram (TP-02), speed accuracy chart (TP-03), transient response scope captures, temperature vs time (TP-05), block diagram, circuit schematic, system photo
- [ ] **References and citations**
- [ ] **Use Word Styles** via UMich Office 365
- [ ] **One team member edits entire report**
- [ ] **Attach supplementary materials** — code, drawings

### Oral Presentation (Apr 24, 6:30–9:30 PM)

Layout guidance from Dr. Pannier (Feb 24):
1. Intro
2. What each component is (e.g., "what is Klipper")
3. What we built
4. Why we built it
5. How we built it
6. Results / "winning"

- [ ] Prepare presentation following Dr. Pannier's layout
- [ ] Practice design defense
- [ ] Prepare prototype for demonstration

---

## Research Documents Index

| Document | Location |
|----------|----------|
| Problem analysis (Bolton Step 2) | `docs/problem_analysis.md` |
| RTDE register allocation | `docs/register_allocation.md` |
| Latency analysis | `docs/latency_analysis.md` |
| Trade: Klipper vs Lingua Franca | `trades/lingua_franca_vs_klipper.md` |
| Trade: Communication protocol | `trades/comms.md` |
| Trade: MCU platform | `trades/mcu.md` |
| Information needs tracker | `reqs/information_needs.md` |
| Klipper protocols & API | `docs/klipper_protocols.md` |
| SKR Pico V1.0 specs | `docs/skr_pico_specs.md` |
| SKR Pico + Klipper setup | `docs/skr_pico_klipper_setup.md` |
| UR RTDE research | `docs/ur_rtde.md` |
| Power requirements | `docs/pi_power.md` |
| Design process | `reqs/process.md` |
| Phase 2 requirements | `reqs/phase2.md` |
| Phase 3/4 requirements | `reqs/phase3.md` |
| Project overview | `reqs/about.md` |
| Accelerated schedule | `schedule.md` |

## Source Code Index

| Component | Location | Status |
|-----------|----------|--------|
| Bridge daemon (main loop) | `src/bridge/bridge_daemon.py` | Written |
| Bridge config (registers, constants) | `src/bridge/config.py` | Written |
| Klipper Unix socket client | `src/bridge/klipper_client.py` | Written |
| RTDE client wrapper | `src/bridge/rtde_client.py` | Written |
| Klipper status poller | `src/bridge/klipper_status.py` | Written |
| Watchdog timer | `src/bridge/watchdog.py` | Written |
| Data logger | `src/bridge/data_logger.py` | Written |
| Extrusion profiles | `src/bridge/extrusion_profile.py` | Written |
| Dashboard client | `src/bridge/dashboard_client.py` | Written |
| StallGuard accumulator | `src/bridge/stallguard_accumulator.py` | Written |
| Klipper printer config | `src/klipper/printer.cfg` | Written |
| Moonraker config | `src/klipper/moonraker.conf` | Written |
| Mainsail pump macros | `src/klipper/mainsail.cfg` | Written |
| StallGuard shared header | `src/klipper_mods/stallguard_shared.h` | Written |
| StallGuard core1 firmware | `src/klipper_mods/core1_stallguard.c` | Written |
| StallGuard MCU commands | `src/klipper_mods/stallguard_command.c` | Written |
| StallGuard klippy module | `src/klipper_mods/klippy_extras/stallguard_monitor.py` | Written |
| URScript extrusion program | `src/urscript/extrusion_control.script` | Written |
| URScript validation test | `src/urscript/test_basic.script` | Written |
| URScript calibration test | `src/urscript/test_calibration.script` | Written |
| Deploy script | `deploy.sh` | Written |
| Dev sync script | `scripts/dev-sync.sh` | Written |
