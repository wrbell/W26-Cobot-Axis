# CI/CD Setup Guide

This document explains the continuous integration (CI) setup for the W26 Cobot
Axis project, how to use it, and how to troubleshoot common issues.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [How It Works -- Tier 1 and Tier 2](#2-how-it-works----tier-1-and-tier-2)
3. [Verifying CI Is Working](#3-verifying-ci-is-working)
4. [Reading Build Results](#4-reading-build-results)
5. [The CI Badge](#5-the-ci-badge)
6. [Downloading Firmware Artifacts (Tier 2)](#6-downloading-firmware-artifacts-tier-2)
7. [Manual Firmware Build Trigger](#7-manual-firmware-build-trigger)
8. [Tier 3 -- Deploy to Pi (Future)](#8-tier-3----deploy-to-pi-future)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites

### GitHub Actions

GitHub Actions is built into GitHub. There is nothing to install or configure
on the repository settings page beyond having the workflow files present. As
long as the repository has the `.github/workflows/` directory with valid YAML
files, Actions will run automatically.

**Free tier limits:**

| Repository type | Minutes per month |
|-----------------|-------------------|
| Public          | Unlimited         |
| Private         | 2,000             |

Our Tier 1 workflow takes about 30 seconds per run. Tier 2 (firmware build)
takes 2--3 minutes because it cross-compiles Klipper. Even with frequent
pushes, you will not come close to the 2,000-minute limit on a private repo.

### What you need

- A GitHub account with push access to the repository.
- The two workflow files committed and pushed:
  - `.github/workflows/ci.yml` (Tier 1)
  - `.github/workflows/firmware.yml` (Tier 2)
- That is it. No secrets, tokens, or external services are needed for Tier 1
  and Tier 2.

---

## 2. How It Works -- Tier 1 and Tier 2

The project uses a **tiered CI strategy**. Tier 1 runs on every change and is
fast. Tier 2 runs only when firmware source changes and is slower.

### Tier 1: Lint, Test, ShellCheck

**Workflow file:** `.github/workflows/ci.yml`

**Triggers:** Every `push` and every `pull_request`, on any branch.

**What it does (single job: `lint-and-test`):**

| Step | Command | Purpose |
|------|---------|---------|
| Checkout | `actions/checkout@v4` | Clone the repo at the triggering commit |
| Setup Python | `actions/setup-python@v5` (3.11) | Install Python 3.11 |
| Install deps | `pip install ruff pytest ur_rtde` | Install linter, test runner, and RTDE library |
| Lint | `ruff check src/bridge/` | Static analysis of all Python bridge code |
| Test | `python -m pytest src/bridge/tests/ -v` | Run 277+ unit tests (all mocked, no hardware needed) |
| ShellCheck | `shellcheck deploy.sh scripts/dev-sync.sh` | Lint the two Bash scripts for common shell bugs |

The steps run sequentially in a single job on `ubuntu-latest`. If any step
fails, the remaining steps do not run and the whole workflow is marked as
failed.

**Typical runtime:** 20--40 seconds.

### Tier 2: Firmware Build

**Workflow file:** `.github/workflows/firmware.yml`

**Triggers:**
- `push` -- but only when files under `src/klipper_mods/**` change.
- `workflow_dispatch` -- manual trigger from the Actions tab (see
  [Section 7](#7-manual-firmware-build-trigger)).

**What it does (single job: `build`):**

| Step | Command / Action | Purpose |
|------|-----------------|---------|
| Checkout | `actions/checkout@v4` | Clone the repo |
| Install cross-compiler | `apt-get install gcc-arm-none-eabi newlib-arm-none-eabi` | ARM toolchain for RP2040 |
| Clone Klipper | `git clone --depth 1 ...klipper.git` | Get Klipper source tree |
| Apply StallGuard overlay | Copy C/H files + `sed` patches | Inject our firmware into the Klipper build |
| Write `.config` | `cat > klipper/.config` | Configure Klipper for RP2040/SKR Pico |
| Build | `make olddefconfig && make -j$(nproc)` | Cross-compile to produce `klipper.uf2` |
| Upload artifact | `actions/upload-artifact@v4` | Save `klipper.uf2` as a downloadable build artifact |

**The overlay process in detail:**

The Apply StallGuard overlay step mirrors what `deploy.sh` does on the Pi.
It performs three operations:

1. **Copy source files** into the Klipper tree:
   ```
   src/klipper_mods/stallguard_shared.h   -->  klipper/src/rp2040/
   src/klipper_mods/core1_stallguard.c    -->  klipper/src/rp2040/
   src/klipper_mods/stallguard_command.c  -->  klipper/src/rp2040/
   ```

2. **Patch `klipper/src/rp2040/Makefile`** -- insert two `src-y +=` lines
   after the `rp2040/i2c.c` entry so the build system compiles our files:
   ```makefile
   src-y += rp2040/core1_stallguard.c
   src-y += rp2040/stallguard_command.c
   ```

3. **Patch `klipper/src/rp2040/main.c`** -- add a forward declaration for
   `core1_launch()` after the `#include "sched.h"` line, and insert the
   `core1_launch()` call just before `sched_main()` so Core 1 starts before
   the main scheduler loop.

If any of these `sed` commands fail (e.g., because Klipper upstream changed
the anchor lines), the build will fail and CI will report it. This is
intentional -- it tells us when upstream Klipper has broken our overlay.

**The `.config` values:**

The Klipper `.config` written by the workflow targets:
- `CONFIG_MACH_RP2040=y` -- RP2040 processor
- `CONFIG_USB=y` -- USB serial communication (how the Pi talks to the SKR Pico)
- `CONFIG_RP2040_FLASH_W25Q080=y` -- W25Q080 flash chip on the SKR Pico
- `CONFIG_CLOCK_FREQ=12000000` -- 12 MHz crystal on the SKR Pico

**Typical runtime:** 2--3 minutes.

**Output:** A downloadable `klipper-firmware` artifact containing `klipper.uf2`.

---

## 3. Verifying CI Is Working

After pushing your first commit with the workflow files, follow these steps to
confirm everything is running.

### Step 1: Push a commit

```bash
git add .github/workflows/ci.yml .github/workflows/firmware.yml
git commit -m "Add CI workflows"
git push origin main
```

### Step 2: Check the Actions tab

Go to the repository on GitHub and click the **Actions** tab at the top of the
page. You should see your workflow runs listed:

```
Actions
  All workflows
    CI                      main  <commit message>  <timestamp>  [green/yellow/red]
    Firmware Build          main  <commit message>  <timestamp>  [green/yellow/red]
```

- **Yellow circle** = currently running.
- **Green checkmark** = passed.
- **Red X** = failed.

If you only changed files outside `src/klipper_mods/`, only the CI workflow
will appear (Tier 2 does not trigger).

### Step 3: Click into a workflow run

Click on the workflow name (e.g., "CI") to see the list of runs. Click on the
specific run to see its jobs. Click on the job name ("lint-and-test" or
"build") to see the step-by-step log output.

### Step 4: Check commit status

Go back to the repository's main page or any pull request. Next to the commit
hash, you will see a small icon:

- Green checkmark = all workflows passed.
- Yellow dot = running.
- Red X = at least one workflow failed. Click it for details.

---

## 4. Reading Build Results

When a workflow fails, you need to find which step failed and read its output.

### Finding the failed step

1. Go to **Actions** tab.
2. Click the failed run (red X).
3. Click the job name (e.g., "lint-and-test").
4. The step that failed will have a red X next to it. All subsequent steps
   will be grayed out (they did not run).
5. Click the failed step to expand its log output.

### Reading ruff output

If the **Lint** step fails, ruff found style or correctness issues. The output
looks like this:

```
src/bridge/config.py:42:1: E302 Expected 2 blank lines before function definition
src/bridge/rtde_client.py:18:5: F841 Local variable 'x' is assigned but never used
Found 2 errors.
```

The format is `file:line:column: code message`. Fix the listed issues, commit,
and push again.

You can reproduce this locally:

```bash
ruff check src/bridge/
```

### Reading pytest output

If the **Test** step fails, at least one test did not pass. Scroll to the
bottom of the pytest output to see the summary:

```
FAILED src/bridge/tests/test_bridge.py::test_emergency_stop - AssertionError: ...
FAILED src/bridge/tests/test_klipper_client.py::test_reconnect - TimeoutError: ...

====================== 2 failed, 275 passed in 0.8s =======================
```

The `FAILED` lines tell you which test file and test function failed. Scroll
up to find the full traceback for each failure.

You can reproduce this locally:

```bash
python -m pytest src/bridge/tests/ -v
```

To run a single failing test:

```bash
python -m pytest src/bridge/tests/test_bridge.py::test_emergency_stop -v
```

### Reading shellcheck output

If the **ShellCheck** step fails, the output shows shell script issues:

```
In deploy.sh line 47:
  cd $REPO_DIR
     ^-------^ SC2164: Use 'cd ... || exit' in case cd fails.

In scripts/dev-sync.sh line 12:
  local files=$(ls *.py)
        ^---^ SC2155: Declare and assign separately to avoid masking return values.
```

Each finding has a code like `SC2164`. You can look it up at
`https://www.shellcheck.net/wiki/SCxxxx` for a detailed explanation.

You can reproduce this locally (if shellcheck is installed):

```bash
shellcheck deploy.sh scripts/dev-sync.sh
```

On macOS, install with `brew install shellcheck`. On Ubuntu/Debian, install
with `sudo apt-get install shellcheck`.

### Reading firmware build output

If the **Build firmware** step fails in Tier 2, it is usually one of:

- **`sed` patch failed silently** -- the anchor line changed in upstream
  Klipper. The build will fail with undefined symbol errors like
  `undefined reference to 'core1_launch'` or missing file errors.
- **Compilation error** -- a syntax or type error in the StallGuard C code.
  The `gcc` output will show the file, line, and error message.
- **Linker error** -- a missing symbol. Check that all three source files
  were copied correctly and both `src-y +=` lines were patched into the
  Makefile.

---

## 5. The CI Badge

The README.md already includes a CI status badge on line 1:

```markdown
![CI](../../actions/workflows/ci.yml/badge.svg)
```

This uses a relative GitHub URL that resolves to:

```
https://github.com/<owner>/<repo>/actions/workflows/ci.yml/badge.svg
```

The badge dynamically shows the status of the most recent `ci.yml` run on the
default branch (`main`):

| Badge text | Meaning |
|------------|---------|
| CI: passing | All steps in the most recent Tier 1 run succeeded |
| CI: failing | At least one step in the most recent Tier 1 run failed |
| CI: no status | No runs yet, or the workflow file was just added |

The badge updates automatically. No configuration is needed. It is useful for
quickly checking project health without opening the Actions tab.

### Adding a firmware badge (optional)

If you want a badge for Tier 2 as well, add this line to README.md:

```markdown
![Firmware Build](../../actions/workflows/firmware.yml/badge.svg)
```

---

## 6. Downloading Firmware Artifacts (Tier 2)

When the Tier 2 firmware build succeeds, it uploads `klipper.uf2` as a build
artifact. This is the compiled firmware binary ready to flash onto the SKR
Pico.

### From the GitHub web UI

1. Go to the **Actions** tab.
2. Click **Firmware Build** in the left sidebar to filter runs.
3. Click on a successful run (green checkmark).
4. Scroll down to the **Artifacts** section at the bottom of the run page.
5. Click **klipper-firmware** to download a ZIP file.
6. Extract the ZIP. Inside is `klipper.uf2`.

### From the command line (using `gh` CLI)

If you have the GitHub CLI installed:

```bash
# List recent firmware build runs
gh run list --workflow=firmware.yml

# Download the artifact from the most recent successful run
gh run download --name klipper-firmware
```

This creates a `klipper-firmware/` directory containing `klipper.uf2`.

### Flashing the SKR Pico

Once you have `klipper.uf2`:

1. Hold the BOOTSEL button on the SKR Pico and plug it into USB.
2. It mounts as a USB mass storage device (like a flash drive).
3. Copy `klipper.uf2` onto the mounted drive.
4. The SKR Pico reboots automatically and runs the new firmware.

This is the same process whether the `.uf2` came from CI or from a local
build.

### Artifact retention

GitHub retains artifacts for **90 days** by default. After that, they are
deleted. If you need a permanent archive of a specific firmware build, download
it and store it elsewhere.

---

## 7. Manual Firmware Build Trigger

The firmware workflow supports `workflow_dispatch`, which means you can trigger
a build manually without pushing a commit. This is useful when:

- You want to rebuild against the latest upstream Klipper to check for
  breakage, without changing any of our code.
- You want to generate a fresh `klipper.uf2` artifact from the current `main`
  branch.

### From the GitHub web UI

1. Go to the **Actions** tab.
2. Click **Firmware Build** in the left sidebar.
3. Click the **Run workflow** button (top right of the runs list).
4. Select the branch (usually `main`).
5. Click the green **Run workflow** button.

The build starts immediately. Refresh the page to see it appear in the runs
list.

### From the command line (using `gh` CLI)

```bash
# Trigger a firmware build on the main branch
gh workflow run firmware.yml --ref main

# Watch it run
gh run watch
```

---

## 8. Tier 3 -- Deploy to Pi (Future)

A third workflow tier is planned but not yet implemented. It would automate
deployment to the headless Raspberry Pi that runs in the production system.

### Concept

```
Tier 3: Deploy to Pi
  Trigger: manual dispatch (workflow_dispatch) or tag push (v*)
  Steps:
    1. SSH into the Pi
    2. git pull the latest code
    3. Run deploy.sh (which handles Klipper config, bridge daemon, services)
    4. Verify services are running
```

### Why it is not implemented yet

Deployment over SSH requires two GitHub Actions secrets:

| Secret name | Value |
|-------------|-------|
| `PI_HOST` | IP address or hostname of the Pi on the lab network |
| `PI_SSH_KEY` | Private SSH key authorized to log into the Pi as the `pi` user |

These cannot be set until:

1. The Pi hardware is on the lab network with a known static IP.
2. An SSH key pair is generated and the public key is added to the Pi's
   `~/.ssh/authorized_keys`.
3. The private key is added to the repository's Settings > Secrets and
   variables > Actions page.

### What we do instead (for now)

Manual deployment using `scripts/dev-sync.sh` for fast file sync during
development, and `deploy.sh` for full deployment (run directly on the Pi via
SSH). This is documented in the main README.

When hardware is available and the Pi is on the network, adding Tier 3 is
straightforward -- it is just an SSH action that runs the existing `deploy.sh`
script.

---

## 9. Troubleshooting

### Actions not triggering at all

**Symptom:** You push a commit but no workflow run appears in the Actions tab.

**Check these:**

1. **Are the workflow files in the right place?** They must be at exactly
   `.github/workflows/ci.yml` and `.github/workflows/firmware.yml` (note the
   `.github` directory with a leading dot).

2. **Is the YAML valid?** A syntax error in the workflow file will silently
   prevent it from running. Validate with:
   ```bash
   # Install actionlint (optional)
   brew install actionlint   # macOS
   actionlint .github/workflows/ci.yml
   actionlint .github/workflows/firmware.yml
   ```

3. **Are Actions enabled?** Go to Settings > Actions > General and make sure
   "Allow all actions and reusable workflows" is selected.

4. **Branch protection rules?** If the repository has branch protection
   configured to require specific status checks, make sure the workflow names
   match what is configured.

5. **Workflow file on the correct branch?** The workflow files must exist on
   the branch that is being pushed. If you added them on `main` but are
   pushing to `feature-x`, the workflows need to be on `feature-x` too (or
   merged from `main`).

### Tier 2 does not trigger on push

**Symptom:** You pushed changes to files in `src/klipper_mods/` but the
Firmware Build workflow did not run.

**Check:** The path filter in `firmware.yml` is `src/klipper_mods/**`. Make
sure your changed files are actually under that directory. Files outside it
(like `docs/` or `src/bridge/`) will not trigger Tier 2.

Also verify that the push event is reaching GitHub. Check `git log --oneline`
locally vs. the commit history on GitHub to confirm the push went through.

### `ur_rtde` install failure

**Symptom:** The `pip install ruff pytest ur_rtde` step fails with a build
error for `ur_rtde`.

**Cause:** The `ur_rtde` package has C++ bindings that require a compiler and
Boost libraries. On most `ubuntu-latest` runners, this works out of the box.
If it fails:

1. Check the error log -- it usually says which system library is missing.
2. Add a step before the pip install to install build dependencies:
   ```yaml
   - name: Install build deps for ur_rtde
     run: sudo apt-get install -y libboost-all-dev
   ```
3. Alternatively, if the bridge tests do not actually import `ur_rtde` at
   module level (they use mocks), you could remove `ur_rtde` from the pip
   install line. But keeping it ensures the import does not break.

### ShellCheck warnings vs. errors

**Symptom:** ShellCheck reports findings and CI fails, but the scripts work
fine locally.

**Explanation:** ShellCheck returns a non-zero exit code when it finds any
issues (warnings, errors, or info-level findings). All of them cause the CI
step to fail.

**Fix options:**

1. **Fix the findings.** This is usually the right approach. ShellCheck
   catches real bugs (unquoted variables, missing error handling).

2. **Suppress specific findings** with inline directives:
   ```bash
   # shellcheck disable=SC2086
   rsync $FLAGS "$SRC" "$DEST"
   ```
   Use this sparingly and only when you understand why the finding is a false
   positive for your use case.

3. **Exclude codes globally** by passing `--exclude` to shellcheck in the
   workflow file (not recommended unless you have a good reason).

### Firmware build fails with undefined symbols

**Symptom:** The `make` step in Tier 2 fails with errors like:

```
undefined reference to 'core1_launch'
undefined reference to 'stallguard_command_init'
```

**Cause:** The `sed` patches that modify the Klipper Makefile or `main.c` did
not apply correctly. This usually means upstream Klipper changed the anchor
lines that our `sed` commands rely on.

**How to investigate:**

1. Click into the failed workflow run.
2. Expand the "Apply StallGuard overlay" step to see the `sed` output.
3. Check the "Build firmware" step for the exact error.
4. Locally, clone a fresh copy of Klipper and check whether the anchor lines
   still exist:
   ```bash
   git clone --depth 1 https://github.com/Klipper3d/klipper.git /tmp/klipper-check
   grep -n 'rp2040/i2c\.c' /tmp/klipper-check/src/rp2040/Makefile
   grep -n '#include "sched.h"' /tmp/klipper-check/src/rp2040/main.c
   grep -n 'sched_main()' /tmp/klipper-check/src/rp2040/main.c
   ```
5. If the anchor lines changed, update the `sed` commands in both
   `.github/workflows/firmware.yml` and `deploy.sh` to match.

The anchor lines we depend on (as of the time of writing):

| File | Anchor line | What we patch |
|------|------------|---------------|
| `src/rp2040/Makefile` | `rp2040/i2c.c` (last `src-y` entry) | Append our two `src-y +=` lines after it |
| `src/rp2040/main.c` | `#include "sched.h"` | Insert `extern void core1_launch(void);` after it |
| `src/rp2040/main.c` | `sched_main();` | Insert `core1_launch();` before it |

### Firmware build fails with `.config` errors

**Symptom:** The `make olddefconfig` step fails or produces unexpected output.

**Cause:** Klipper's Kconfig options may have changed upstream. The `.config`
written by the workflow might reference options that no longer exist or are
missing new required options.

**Fix:** Run `make menuconfig` locally against a fresh Klipper clone, select
the correct options for RP2040 + USB, save, and copy the resulting `.config`
content into the workflow file.

### Tests pass locally but fail in CI

**Symptom:** `pytest` passes on your machine but fails on GitHub Actions.

**Common causes:**

1. **Python version mismatch.** CI uses Python 3.11 (set in `ci.yml`). Check
   your local version with `python --version`.
2. **Missing dependency.** You installed something locally that is not in the
   `pip install` line in the workflow. Add it.
3. **OS difference.** Your machine is macOS; CI runs Ubuntu. Path separators,
   temp directories, and available system commands can differ. The bridge tests
   should not depend on any of these (they are all mocked), but check if a new
   test accidentally does.
4. **File ordering.** Some operating systems return directory listings in
   different orders. If a test depends on file order, it may be flaky.

### Workflow takes too long

**Symptom:** The firmware build is slow or times out.

**Mitigation:**

- The `git clone --depth 1` for Klipper already minimizes clone time.
- `make -j$(nproc)` already parallelizes the build.
- GitHub-hosted runners have 2--4 cores. There is not much you can do to speed
  up a cross-compilation beyond what is already configured.
- If Tier 1 is slow, check whether the test suite has grown significantly. The
  tests should stay under 2 seconds total since they are all mocked.

---

## Appendix: Workflow File Locations

| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | Tier 1: lint + test + shellcheck |
| `.github/workflows/firmware.yml` | Tier 2: firmware cross-compilation |
| `deploy.sh` | On-Pi deployment (Tier 3 would automate running this) |
| `scripts/dev-sync.sh` | Fast rsync for development iteration |

---

## Appendix: Useful Commands

```bash
# Run the same checks locally that CI runs (Tier 1)
ruff check src/bridge/
python -m pytest src/bridge/tests/ -v
shellcheck deploy.sh scripts/dev-sync.sh

# Build firmware locally (same as Tier 2, assuming vendor/klipper exists)
cp src/klipper_mods/stallguard_shared.h vendor/klipper/src/rp2040/
cp src/klipper_mods/core1_stallguard.c vendor/klipper/src/rp2040/
cp src/klipper_mods/stallguard_command.c vendor/klipper/src/rp2040/
cd vendor/klipper && make olddefconfig && make -j$(nproc)

# Trigger firmware build remotely via gh CLI
gh workflow run firmware.yml --ref main

# Download latest firmware artifact via gh CLI
gh run download --name klipper-firmware

# Check workflow run status via gh CLI
gh run list --workflow=ci.yml --limit 5
gh run list --workflow=firmware.yml --limit 5
```
