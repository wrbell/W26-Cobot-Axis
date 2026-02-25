# W26 Cobot Axis -- Developer & Test Environment Setup

How to set up a local development and testing environment on your own machine. No Raspberry Pi, SKR Pico, or UR30 robot needed -- everything runs in stub mode.

---

## Quick Start

```bash
git clone https://github.com/<your-org>/W26-Cobot-Axis.git
cd W26-Cobot-Axis
make install                               # pip install + pre-commit hooks
make check                                 # lint + test + typecheck + yamllint + spellcheck
```

That's it. All tests pass without any hardware connected.

---

## Prerequisites

| Tool | Version | Required? |
|------|---------|-----------|
| Python | 3.10+ | Yes |
| pip | latest | Yes |
| git | any | Yes |
| make | any | Recommended -- provides `make check`, `make test`, etc. |
| shellcheck | any | Optional -- only for linting `deploy.sh` and `dev-sync.sh` |
| Docker | any | Optional -- only for running URSim or `act` (local CI) |

---

## Clone and Install

```bash
git clone https://github.com/<your-org>/W26-Cobot-Axis.git
cd W26-Cobot-Axis
```

**Using a virtual environment (recommended):**

```bash
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

**What gets installed:**

| Package | Purpose |
|---------|---------|
| `ur-rtde` | RTDE communication with UR30 (fails gracefully if C++ deps missing -- see [Stub Mode](#stub-mode-no-hardware)) |
| `pytest` | Test framework |
| `ruff` | Linter and formatter |

> **Note:** If `ur-rtde` fails to install (missing C++ toolchain), everything else still works. The bridge daemon and all tests fall back to stub mode automatically.

---

## Running Tests

**Full suite:**

```bash
python -m pytest src/bridge/tests/ -v
```

Expected output: **469 passed** in under 2 seconds.

**Single test file:**

```bash
python -m pytest src/bridge/tests/test_bridge_daemon.py -v
```

**Single test:**

```bash
python -m pytest src/bridge/tests/test_bridge_daemon.py::test_idle_mode -v
```

**Quiet mode (just pass/fail):**

```bash
python -m pytest src/bridge/tests/ -q
```

**Show print output:**

```bash
python -m pytest src/bridge/tests/ -v -s
```

### Test File Summary

| File | Tests | What it covers |
|------|-------|----------------|
| `test_bridge_daemon.py` | 71 | Main loop, mode switching, e-stop, reconnection |
| `test_rtde_client.py` | 43 | RTDE read/write, stub fallback, timeouts |
| `test_klipper_client.py` | 42 | Unix socket client, G-code send/receive |
| `test_extrusion_profile.py` | 39 | Linear/polynomial/lookup speed profiles |
| `test_stallguard_accumulator.py` | 34 | StallGuard history buffer, CSV dump |
| `test_stallguard.py` | 25 | StallGuard status integration |
| `test_dashboard_client.py` | 25 | UR Dashboard Server client |
| `test_config.py` | 24 | Register naming, uniqueness, constant sanity |
| `test_data_logger.py` | 17 | CSV logging with rotation |
| `test_watchdog.py` | 15 | RTDE timestamp-based stale detection |

---

## Linting

**Check for issues:**

```bash
ruff check src/bridge/
```

**Auto-fix what it can:**

```bash
ruff check src/bridge/ --fix
```

Ruff checks for: unused imports, undefined names, style issues, common bugs, and more. CI runs the same check on every push.

---

## Makefile

A `Makefile` provides single-command entry points for all development tasks:

| Command | What it does |
|---------|-------------|
| `make lint` | Ruff lint check |
| `make fmt` | Ruff auto-fix |
| `make test` | pytest with coverage |
| `make typecheck` | mypy type check |
| `make spellcheck` | codespell spell check |
| `make yamllint` | Lint workflow YAML |
| `make check` | All of the above (lint + test + typecheck + yamllint + spellcheck) |
| `make install` | `pip install -r requirements.txt` + `pre-commit install` |
| `make clean` | Remove `__pycache__`, `.mypy_cache`, `.coverage`, etc. |
| `make ci-local` | Run CI locally via `act` (requires Docker) |

Run `make check` before pushing to catch most CI failures locally.

---

## Pre-commit Hooks

Pre-commit hooks run automatically on `git commit` to catch issues before they reach CI. They're configured in `.pre-commit-config.yaml`.

**Setup (one-time):**

```bash
make install          # or: pip install pre-commit && pre-commit install
```

**What runs on each commit:**

| Hook | What it checks |
|------|---------------|
| ruff | Lint (`src/bridge/`) |
| mypy | Type check (`src/bridge/`, excluding tests) |
| yamllint | Workflow YAML syntax (`.github/workflows/`) |
| codespell | Spelling errors across the repo |

**Run all hooks manually (without committing):**

```bash
pre-commit run --all-files
```

**Skip hooks for a quick commit (not recommended):**

```bash
git commit --no-verify -m "WIP"
```

---

## Running CI Locally with `act`

[`act`](https://github.com/nektos/act) runs GitHub Actions workflows locally using Docker. This is optional -- `make check` covers the most important checks without Docker.

**Install:**

```bash
brew install act      # macOS
# or see https://github.com/nektos/act#installation
```

**Run the lint-and-test job:**

```bash
make ci-local         # or: act -j lint-and-test --matrix python-version:3.11
```

**Notes:**
- Requires Docker running locally
- The firmware build job (`firmware.yml`) won't run well locally -- ARM cross-compilation in Docker is slow and unnecessary. Use `make check` instead.
- `.actrc` configures the default Docker image and secrets

---

## Stub Mode (No Hardware)

The bridge daemon is designed to work without a UR30 robot or SKR Pico connected. When `ur-rtde` is not installed (or fails to import), the RTDE client falls back to a stub:

```python
# src/bridge/rtde_client.py
try:
    import rtde_receive
    import rtde_control
    HAS_UR_RTDE = True
except ImportError:
    HAS_UR_RTDE = False
    log.warning("ur_rtde not installed — using stub client for development")
```

**What this means:**
- All 469 tests pass without any hardware or `ur-rtde` installed
- The bridge daemon starts but won't connect to a real robot
- Mock objects in `conftest.py` simulate both RTDE and Klipper socket responses
- You can develop, test, and lint entirely on your laptop

---

## Installing ur-rtde (Optional)

You only need `ur-rtde` installed if you're testing against a real UR30 or URSim. For unit tests and local development, stub mode is sufficient.

### Windows

Pre-built wheels are available -- just pip install:

```bash
pip install ur-rtde
```

### macOS

Requires building from source. Install C++ dependencies first:

```bash
brew install cmake boost
pip install ur-rtde
```

### Linux (x86)

```bash
sudo apt install build-essential cmake libboost-all-dev
pip install ur-rtde
```

### Linux ARM (Raspberry Pi)

```bash
sudo apt install build-essential cmake libboost-all-dev
pip install ur-rtde
```

> The Pi build takes several minutes due to compiling C++ from source.

---

## Vendor Dependencies

The `vendor/` directory holds local copies of external source trees used for patch verification. It is git-ignored.

```bash
git clone --depth 1 https://github.com/Klipper3d/klipper.git vendor/klipper
```

**What it's for:** The StallGuard firmware overlay (`src/klipper_mods/`) includes two patches (`Makefile.patch`, `main.c.patch`) that must apply cleanly against the real Klipper source. Having a local clone lets you verify this:

```bash
cd vendor/klipper
git apply ../../src/klipper_mods/Makefile.patch --check
git apply ../../src/klipper_mods/main.c.patch --check
```

**When you need it:** Only if you're modifying the StallGuard firmware overlay. For normal bridge development, skip this step.

---

## Development Workflow

The typical edit-test-lint-push cycle:

1. **Edit** source files in `src/bridge/`
2. **Check** -- `make check` (runs lint + test + typecheck + yamllint + spellcheck)
3. **Commit** -- pre-commit hooks catch remaining issues automatically
4. **Push** -- CI runs the full matrix on GitHub

CI (GitHub Actions) runs the same checks on every push and pull request:
- Tier 1: `ruff check` + `pytest` + `shellcheck` on deploy scripts
- Tier 2: ARM firmware cross-compile (only on `src/klipper_mods/` changes)

See [`docs/design/ci_cd_guide.md`](docs/design/ci_cd_guide.md) for full CI/CD details.

---

## Testing Against URSim

URSim is Universal Robots' simulator -- it runs a virtual UR30 that speaks real RTDE. Use it to test the bridge daemon end-to-end without physical hardware.

See [`docs/ursim_quickstart.md`](docs/ursim_quickstart.md) for setup instructions (Docker on Windows, network config, running test scripts).

---

## Deploying to Pi

When you're ready to deploy to a real Raspberry Pi:

1. **First-time setup:** Follow [`SETUP.md`](SETUP.md) -- covers OS install, network config, Klipper, Moonraker, and the bridge daemon
2. **Automated deployment:** Run `deploy.sh` -- 11-step idempotent script that handles everything

```bash
# From your dev machine (SSH to Pi):
ssh pi@w26-pi.local
cd ~/W26-Cobot-Axis
./deploy.sh
```

---

## Iterative Development on Pi

For rapid edit-test cycles during hardware integration, use `dev-sync.sh` instead of full redeployment:

```bash
# From your dev machine:
./scripts/dev-sync.sh pi@w26-pi.local
```

This rsyncs only changed source files to the Pi and restarts the bridge daemon. Much faster than a full `deploy.sh` run.

See the script header in [`scripts/dev-sync.sh`](scripts/dev-sync.sh) for options.

---

## Common Commands Reference

| Command | What it does |
|---------|-------------|
| `make check` | Run all checks (lint + test + typecheck + yamllint + spellcheck) |
| `make test` | Run all 469 tests with coverage |
| `make lint` | Ruff lint check |
| `make fmt` | Ruff auto-fix |
| `make typecheck` | mypy type check |
| `make install` | Install deps + pre-commit hooks |
| `make clean` | Remove caches and build artifacts |
| `make ci-local` | Run CI locally via `act` (requires Docker) |
| `pre-commit run --all-files` | Run all pre-commit hooks manually |
| `python -m pytest src/bridge/tests/ -v` | Run all 469 tests (verbose) |
| `python -m pytest src/bridge/tests/test_bridge_daemon.py -v` | Run one test file |
| `python -m pytest src/bridge/tests/test_bridge_daemon.py::test_idle_mode -v` | Run one test |
| `python -m bridge` | Start bridge daemon (needs RTDE + Klipper) |
| `./deploy.sh` | Full deployment to Pi (11 steps) |
| `./scripts/dev-sync.sh pi@w26-pi.local` | Fast rsync to Pi |
| `shellcheck deploy.sh scripts/dev-sync.sh` | Lint shell scripts |
| `git clone --depth 1 https://github.com/Klipper3d/klipper.git vendor/klipper` | Clone Klipper for patch verification |
