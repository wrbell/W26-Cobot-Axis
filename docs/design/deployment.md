# Deployment Design Document

> **Project:** W26 Cobot Axis -- ME472 Mechatronics Capstone
> **Author:** Willem (Software/EE)
> **Date:** 2026-02-12
> **Status:** Design -- not yet implemented

This document specifies the deployment infrastructure for the W26 Cobot Axis system. It covers four deliverables: Python dependency management (`requirements.txt`), a systemd service file for the bridge daemon, a deployment script for automated setup, and step-by-step setup instructions for a fresh Raspberry Pi.

**Target hardware:** Raspberry Pi (headless, Klipper host + RTDE bridge) connected to a BigTreeTech SKR Pico V1.0 via USB serial and to a UR30 robot controller via Ethernet.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Deliverable 1: requirements.txt](#2-deliverable-1-requirementstxt)
3. [Deliverable 2: systemd Service File](#3-deliverable-2-systemd-service-file)
4. [Deliverable 3: Deployment Script](#4-deliverable-3-deployment-script)
5. [Deliverable 4: Setup Instructions](#5-deliverable-4-setup-instructions)
6. [Network Configuration](#6-network-configuration)
7. [File Placement Summary](#7-file-placement-summary)
8. [Maintenance Procedures](#8-maintenance-procedures)
9. [Open Questions](#9-open-questions)

---

## 1. System Overview

### 1.1 Software Stack on Pi

The headless Pi runs four main processes:

| Process | Role | Managed By |
|---------|------|------------|
| klippy (Klipper host) | Motion planning, G-code parsing, MCU communication | systemd (`klipper.service`) |
| Moonraker | HTTP/WebSocket API layer for Klipper | systemd (`moonraker.service`) |
| Bridge daemon | RTDE-to-Klipper translator | systemd (`w26-bridge.service`) -- new |
| SSH daemon | Remote access | systemd (pre-installed) |

### 1.2 Dependencies Between Services

```
                    network-online.target
                           |
                    klipper.service
                      (creates /tmp/klippy_uds)
                      /              \
          moonraker.service    w26-bridge.service
          (port 7125)          (reads RTDE, writes to klippy_uds)
```

The bridge daemon requires the klippy Unix domain socket (`/tmp/klippy_uds`) to exist. This socket is created by Klipper after it finishes startup, which takes several seconds after `klipper.service` reports "active". This timing dependency is the most important deployment challenge.

### 1.3 Source Code Inventory

All bridge daemon source is in `src/bridge/`:

| File | Imports (stdlib) | Imports (third-party) |
|------|------------------|-----------------------|
| `bridge_daemon.py` | `argparse`, `logging`, `signal`, `sys`, `time` | None directly; uses `config`, `rtde_client`, `klipper_client` |
| `config.py` | None | None |
| `klipper_client.py` | `json`, `logging`, `socket`, `threading`, `time` | None |
| `rtde_client.py` | `logging`, `time` | `rtde_receive`, `rtde_control` (from ur_rtde) |
| `__main__.py` | None | None (imports `bridge_daemon.main`) |

The **only third-party dependency** is `ur_rtde` (the SDU C++/Python library). All Klipper communication uses the standard library `socket` module via `klipper_client.py`, which connects directly to the klippy Unix domain socket. No Moonraker client library is needed.

---

## 2. Deliverable 1: requirements.txt

### 2.1 Purpose

Declares Python package dependencies for the bridge daemon so they can be installed reproducibly with `pip install -r requirements.txt`.

### 2.2 Specified Contents

```
# W26 Cobot Axis -- Bridge Daemon Dependencies
# Install: pip install -r requirements.txt
#
# NOTE: ur-rtde requires C++ build tools and Boost.
# On Raspberry Pi (ARM), install system packages first:
#   sudo apt-get install -y build-essential cmake libboost-all-dev
#
# If ur-rtde fails to build from source on ARM, the bridge daemon
# will fall back to stub mode (no robot connection) -- see
# src/bridge/rtde_client.py for the fallback logic.

ur-rtde>=1.5.7,<2.0
```

### 2.3 Design Rationale

**Version pinning strategy: range with upper bound.**

- `ur-rtde>=1.5.7,<2.0` -- The lower bound ensures the register API methods used in `rtde_client.py` (e.g., `getOutputIntRegister`, `setInputIntRegister`) are available. These methods have been stable since ~1.4. The upper bound `<2.0` guards against a hypothetical major version with breaking changes.
- No exact pin (e.g., `==1.5.9`) because on ARM/Raspberry Pi, pre-built wheels may only be available for certain versions and exact pins would cause unnecessary build failures.

**Why only one dependency?**

The bridge daemon was intentionally written using only the Python standard library for Klipper communication (raw Unix socket with JSON, in `klipper_client.py`). This avoids pulling in `requests`, `websockets`, or any Moonraker client library, which reduces the attack surface and installation complexity on the Pi.

**Anticipated future dependencies:**

| Package | Purpose | When to Add |
|---------|---------|-------------|
| None currently | -- | -- |
| `csv` (stdlib) | Data logging to CSV | Already available, no pip install needed |
| `systemd-python` | sd_notify for watchdog integration | If ExecStartPost health check proves insufficient |

### 2.4 System-Level Build Prerequisites

`ur-rtde` is a C++ library with Python bindings (via pybind11). On ARM (Raspberry Pi), it compiles from source since pre-built wheels are typically only available for x86_64. The following system packages must be installed before `pip install`:

```
sudo apt-get install -y \
    build-essential \
    cmake \
    libboost-system-dev \
    libboost-thread-dev \
    libboost-filesystem-dev \
    python3-dev \
    python3-pip
```

Alternatively, `libboost-all-dev` can replace the individual Boost packages but is a larger install (~200 MB).

**Build time on Pi:** Expect 5-15 minutes for `ur-rtde` compilation on a Pi 4-class board.

### 2.5 File Location

```
src/bridge/requirements.txt
```

### 2.6 Error Handling

| Failure | Cause | Mitigation |
|---------|-------|------------|
| `ur-rtde` build fails | Missing Boost or cmake | Install system prerequisites first; deployment script handles this |
| `ur-rtde` build fails (ARM) | Incompatible Boost version | Try `pip install --no-build-isolation ur-rtde`; if still fails, the bridge has a built-in stub fallback in `rtde_client.py` that allows development/testing without the library |
| Pip too old | pip < 19.3 cannot handle pybind11 builds | `pip install --upgrade pip` before installing requirements |

### 2.7 Maintenance

- When upgrading `ur-rtde`, test on the Pi first. ARM builds are more fragile than x86.
- If a new dependency is added to the bridge daemon, add it to `requirements.txt` and re-run `pip install -r requirements.txt` on the Pi.
- If `ur-rtde` 2.x is released, evaluate the changelog for breaking changes to the `RTDEReceiveInterface` / `RTDEControlInterface` API before updating the version range.

---

## 3. Deliverable 2: systemd Service File

### 3.1 Purpose

Automatically start the bridge daemon on Pi boot, after Klipper is ready, with crash restart and journal logging.

### 3.2 Specified Contents

```ini
# /etc/systemd/system/w26-bridge.service
#
# W26 Cobot Axis -- RTDE-to-Klipper Bridge Daemon
# Translates UR30 RTDE commands to Klipper stepper commands.
#
# Install:
#   sudo cp w26-bridge.service /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable w26-bridge.service
#
# Logs:
#   journalctl -u w26-bridge -f

[Unit]
Description=W26 RTDE-to-Klipper Bridge Daemon
Documentation=https://github.com/<org>/W26-Cobot-Axis
After=klipper.service network-online.target
Wants=network-online.target
# The bridge needs the klippy UDS to exist. klipper.service
# creates it a few seconds after starting. The bridge daemon
# has its own retry loop in _connect_all() that will wait
# for the socket, so a hard Requires= is not needed.

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/W26-Cobot-Axis/src
ExecStartPre=/bin/bash -c 'for i in $(seq 1 30); do [ -S /tmp/klippy_uds ] && exit 0; sleep 1; done; echo "Warning: klippy_uds not found after 30s, starting anyway (bridge will retry)" >&2'
ExecStart=/home/pi/klippy-env/bin/python -m bridge
Restart=on-failure
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=60

# Logging -- stdout/stderr go to the journal
StandardOutput=journal
StandardError=journal
SyslogIdentifier=w26-bridge

# Environment
Environment=PYTHONUNBUFFERED=1

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/tmp

[Install]
WantedBy=multi-user.target
```

### 3.3 Design Rationale

#### Service ordering: `After=klipper.service`

The `After=` directive ensures systemd does not start the bridge until `klipper.service` has been started. However, systemd considers a `Type=simple` service "started" as soon as the process is forked -- it does not wait for the klippy socket to appear. Klipper typically takes 3-10 seconds after fork to create `/tmp/klippy_uds`.

**How the socket timing is handled (defense in depth):**

1. **ExecStartPre wait loop:** A pre-start script polls for `/tmp/klippy_uds` up to 30 seconds. This covers the normal case where Klipper is starting up and the socket appears within a few seconds.

2. **Bridge daemon retry logic:** Even if `ExecStartPre` times out (e.g., Klipper is in an error state), the bridge starts anyway. The `Bridge._connect_all()` method in `bridge_daemon.py` already has a retry loop with `config.RECONNECT_DELAY` (2 seconds) that will keep trying to connect to the klippy socket indefinitely. This is the primary resilience mechanism.

3. **No `Requires=klipper.service`:** Using `Requires=` would cause the bridge to fail if Klipper stops or restarts. The bridge should independently attempt reconnection, not crash when Klipper cycles. `After=` without `Requires=` is the correct pattern for loosely-coupled services.

#### User: `pi`

The bridge runs as the `pi` user (the default user on Raspberry Pi OS / MainsailOS). This is the same user that runs Klipper and Moonraker. Using a dedicated service user (e.g., `w26bridge`) would add complexity with no security benefit since the bridge needs access to the klippy socket, which is owned by `pi`.

**If MainsailOS is used:** The default user is `pi`. The paths in the service file assume this.

#### Python interpreter: `/home/pi/klippy-env/bin/python`

Klipper's install script creates a virtualenv at `~/klippy-env/`. Reusing this virtualenv avoids maintaining a separate Python environment. The bridge's only third-party dependency (`ur-rtde`) will be installed into this same virtualenv.

**Alternative:** Create a separate virtualenv for the bridge (e.g., `~/w26-env/`). This isolates the bridge from Klipper's Python environment but requires managing two virtualenvs. The shared approach is simpler for a capstone project.

#### Restart policy

- `Restart=on-failure` -- Restarts the bridge if it exits with a non-zero code or is killed by a signal. Does not restart on clean exit (exit code 0).
- `RestartSec=5` -- Wait 5 seconds between restarts to avoid hammering the klippy socket or UR30.
- `StartLimitBurst=5` and `StartLimitIntervalSec=60` -- If the bridge crashes 5 times within 60 seconds, systemd stops trying. This prevents infinite restart loops if there is a fundamental configuration error.

#### Logging

`StandardOutput=journal` and `StandardError=journal` route all bridge output to the systemd journal. Combined with `SyslogIdentifier=w26-bridge`, logs can be viewed with:

```bash
journalctl -u w26-bridge -f          # follow live
journalctl -u w26-bridge --since today  # today's logs
journalctl -u w26-bridge -p err       # errors only
```

`PYTHONUNBUFFERED=1` ensures Python does not buffer stdout, so log messages appear immediately in the journal.

#### Security hardening

- `NoNewPrivileges=true` -- Prevents privilege escalation.
- `ProtectSystem=strict` -- Makes the filesystem read-only except for explicitly allowed paths.
- `ProtectHome=read-only` -- The bridge reads its source code from `/home/pi/` but does not need to write there.
- `ReadWritePaths=/tmp` -- The bridge connects to `/tmp/klippy_uds` which requires read-write access to `/tmp`.

### 3.4 File Location

```
src/systemd/w26-bridge.service
```

Deployed to `/etc/systemd/system/w26-bridge.service` on the Pi.

### 3.5 Dependencies

- `klipper.service` must exist (installed by Klipper or MainsailOS).
- The bridge source must be at `/home/pi/W26-Cobot-Axis/src/`.
- The Python virtualenv with `ur-rtde` installed must be at `/home/pi/klippy-env/`.

### 3.6 Error Handling

| Failure | Symptom | Resolution |
|---------|---------|------------|
| klippy socket never appears | ExecStartPre warning in journal, bridge starts but logs "Klipper connection failed" every 2s | Check `systemctl status klipper`; fix Klipper issues first |
| Bridge crashes on import | `ModuleNotFoundError: No module named 'rtde_receive'` | `ur-rtde` not installed in the virtualenv; run deployment script |
| Bridge hits start limit | `systemctl status w26-bridge` shows "start-limit-hit" | Fix the underlying error, then `sudo systemctl reset-failed w26-bridge && sudo systemctl start w26-bridge` |
| UR30 not reachable | Bridge logs "RTDE connection failed" every 2s | Verify network: `ping 192.168.1.100`; check UR30 is powered on and running a program |
| Wrong Python path | `ExecStart` fails immediately | Verify virtualenv location: `ls /home/pi/klippy-env/bin/python` |

### 3.7 Maintenance

- **Changing the UR30 IP:** Edit `src/bridge/config.py` (`UR30_HOST`) and restart: `sudo systemctl restart w26-bridge`.
- **Updating bridge code:** Pull new code to `/home/pi/W26-Cobot-Axis/`, then `sudo systemctl restart w26-bridge`.
- **Viewing logs during development:** `journalctl -u w26-bridge -f --no-pager`.
- **Running the bridge manually (bypassing systemd):** `sudo systemctl stop w26-bridge && cd /home/pi/W26-Cobot-Axis/src && /home/pi/klippy-env/bin/python -m bridge --log-level DEBUG`.

---

## 4. Deliverable 3: Deployment Script

### 4.1 Purpose

A single idempotent script that installs all software components, copies configuration files, and enables services. Safe to run multiple times -- it checks for existing installations before acting.

### 4.2 Specified Contents

The deployment script (`deploy.sh`) will perform the following steps in order:

```
#!/bin/bash
# deploy.sh -- W26 Cobot Axis Deployment Script
# Run on the headless Pi as the 'pi' user.
# Usage: bash deploy.sh [--skip-flash]
```

#### Step 1: Validate environment

- Check running as user `pi` (not root).
- Check running on ARM architecture (`uname -m` should be `aarch64` or `armv7l`).
- Check internet connectivity (`ping -c1 google.com`).
- Check that the repository is present at the expected location.

#### Step 2: Install system dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    libboost-system-dev \
    libboost-thread-dev \
    libboost-filesystem-dev \
    python3-dev \
    python3-pip \
    git
```

Idempotency: `apt-get install` is naturally idempotent; already-installed packages are skipped.

#### Step 3: Verify Klipper installation

- Check that `~/klipper/` exists (Klipper source).
- Check that `~/klippy-env/` exists (Python virtualenv).
- Check that `klipper.service` is enabled: `systemctl is-enabled klipper`.
- If Klipper is not installed, print an error and exit. The deployment script does not install Klipper itself -- that is handled by MainsailOS or KIAUH (see Setup Instructions).

#### Step 4: Verify Moonraker installation

- Check that `~/moonraker/` exists.
- Check that `moonraker.service` is enabled.
- If not installed, print a warning (Moonraker is optional but recommended for web UI monitoring).

#### Step 5: Install bridge Python dependencies

```bash
~/klippy-env/bin/pip install --upgrade pip
~/klippy-env/bin/pip install -r ~/W26-Cobot-Axis/src/bridge/requirements.txt
```

Idempotency: pip will skip already-installed packages if the version constraint is satisfied.

#### Step 6: Deploy Klipper configuration

```bash
# Symlink printer.cfg to the Klipper config directory.
# Klipper looks for config in ~/printer_data/config/ (MainsailOS)
# or ~/klipper_config/ (older setups).
KLIPPER_CONFIG_DIR="$HOME/printer_data/config"
if [ ! -d "$KLIPPER_CONFIG_DIR" ]; then
    KLIPPER_CONFIG_DIR="$HOME/klipper_config"
fi

# Backup existing printer.cfg if it exists and is not already our symlink
if [ -f "$KLIPPER_CONFIG_DIR/printer.cfg" ] && [ ! -L "$KLIPPER_CONFIG_DIR/printer.cfg" ]; then
    cp "$KLIPPER_CONFIG_DIR/printer.cfg" "$KLIPPER_CONFIG_DIR/printer.cfg.bak.$(date +%Y%m%d%H%M%S)"
fi

ln -sf ~/W26-Cobot-Axis/src/klipper/printer.cfg "$KLIPPER_CONFIG_DIR/printer.cfg"
```

Idempotency: `ln -sf` replaces any existing symlink. The backup only occurs if the existing file is not already a symlink.

**Important:** After deploying, the MCU serial path in `printer.cfg` (`serial: /dev/serial/by-id/usb-Klipper_rp2040_PLACEHOLDER-if00`) must be updated to match the actual device. The deployment script will print a reminder.

#### Step 7: Flash Klipper firmware to SKR Pico (optional, `--skip-flash` to bypass)

```bash
cd ~/klipper

# Configure firmware build for RP2040
# This writes .config non-interactively
cat > .config << 'KCONFIG'
CONFIG_LOW_LEVEL_OPTIONS=y
CONFIG_MACH_RP2040=y
CONFIG_RP2040_FLASH_W25Q080=y
CONFIG_RP2040_STAGE2_CLKDIV2=y
CONFIG_USB=y
CONFIG_USB_VENDOR_ID=0x1d50
CONFIG_USB_DEVICE_ID=0x614e
CONFIG_USB_SERIAL_NUMBER="12345"
CONFIG_INITIAL_PINS=""
CONFIG_HAVE_GPIO=y
CONFIG_HAVE_GPIO_ADC=y
CONFIG_HAVE_GPIO_SPI=y
CONFIG_HAVE_GPIO_I2C=y
CONFIG_HAVE_GPIO_HARD_PWM=y
CONFIG_CLOCK_FREQ=12000000
CONFIG_FLASH_SIZE=0x200000
CONFIG_RAM_START=0x20000000
CONFIG_RAM_SIZE=0x42000
CONFIG_STACK_SIZE=512
CONFIG_FLASH_APPLICATION_ADDRESS=0x10000000
CONFIG_FLASH_BOOT_ADDRESS=0x10000100
KCONFIG

make clean
make -j$(nproc)

# Check if SKR Pico is already running Klipper (can flash over USB)
SERIAL_DEVICE=$(ls /dev/serial/by-id/usb-Klipper_rp2040_* 2>/dev/null | head -1)
if [ -n "$SERIAL_DEVICE" ]; then
    echo "Found Klipper device at $SERIAL_DEVICE -- flashing via make flash"
    make flash FLASH_DEVICE="$SERIAL_DEVICE"
else
    echo "No Klipper device found. Manual UF2 flash required:"
    echo "  1. Hold BOOTSEL on SKR Pico and plug in USB"
    echo "  2. sudo mount /dev/sda1 /mnt"
    echo "  3. sudo cp ~/klipper/out/klipper.uf2 /mnt/"
    echo "  4. sudo umount /mnt"
fi
```

**Note on `make menuconfig`:** The deployment script uses a pre-written `.config` file instead of interactive `make menuconfig`. The `.config` values correspond to the settings documented in `docs/skr_pico_klipper_setup.md` Section 2.2:

- Micro-controller Architecture: Raspberry Pi RP2040
- Bootloader offset: No bootloader
- Flash chip: W25Q080 with CLKDIV 2
- Communication interface: USB

Idempotency: `make clean && make` always produces a fresh build. Flashing is safe to repeat.

**Caution:** The `.config` values shown above are representative. The exact Kconfig symbols may differ between Klipper versions. Before implementing, verify against the current Klipper source by running `make menuconfig` manually once, selecting the correct options, and copying the resulting `.config` file.

#### Step 8: Install and enable the systemd service

```bash
sudo cp ~/W26-Cobot-Axis/src/systemd/w26-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable w26-bridge.service
```

Idempotency: Copying the file and reloading is safe to repeat. `enable` is idempotent.

#### Step 9: Update MCU serial path

```bash
# Detect the Klipper MCU serial device
SERIAL_DEVICE=$(ls /dev/serial/by-id/usb-Klipper_rp2040_* 2>/dev/null | head -1)
if [ -n "$SERIAL_DEVICE" ]; then
    echo "Detected MCU at: $SERIAL_DEVICE"
    # Update printer.cfg with actual serial path
    sed -i "s|serial: /dev/serial/by-id/usb-Klipper_rp2040_PLACEHOLDER-if00|serial: $SERIAL_DEVICE|" \
        ~/W26-Cobot-Axis/src/klipper/printer.cfg
    echo "Updated printer.cfg serial path."
else
    echo "WARNING: No Klipper MCU detected. Update printer.cfg manually after flashing."
fi
```

#### Step 10: Restart services

```bash
sudo systemctl restart klipper
# Wait for klippy socket
for i in $(seq 1 30); do
    [ -S /tmp/klippy_uds ] && break
    sleep 1
done
sudo systemctl restart moonraker 2>/dev/null || true  # optional
sudo systemctl start w26-bridge
```

#### Step 11: Verification

```bash
echo ""
echo "=== Deployment Verification ==="
echo ""
echo "Klipper:  $(systemctl is-active klipper)"
echo "Moonraker: $(systemctl is-active moonraker 2>/dev/null || echo 'not installed')"
echo "Bridge:   $(systemctl is-active w26-bridge)"
echo ""
echo "klippy socket: $([ -S /tmp/klippy_uds ] && echo 'exists' || echo 'MISSING')"
echo "MCU serial:    $(ls /dev/serial/by-id/usb-Klipper_rp2040_* 2>/dev/null || echo 'NOT FOUND')"
echo ""
echo "Bridge logs (last 5 lines):"
journalctl -u w26-bridge --no-pager -n 5
```

### 4.3 File Location

```
deploy.sh    (repository root)
```

### 4.4 Dependencies

- Raspberry Pi running Raspberry Pi OS (Bookworm/Bullseye) or MainsailOS.
- Internet connectivity for package downloads.
- Klipper and Moonraker already installed (via MainsailOS or KIAUH).
- Repository cloned to `~/W26-Cobot-Axis/`.

### 4.5 Error Handling

| Failure | Cause | Script Behavior |
|---------|-------|-----------------|
| Not running as `pi` user | Ran as root or wrong user | Exits with error message |
| No internet | `apt-get` / `pip` fail | Exits with error message |
| Klipper not installed | MainsailOS not set up yet | Exits with instruction to install Klipper first |
| `ur-rtde` build fails | Missing Boost, ARM issue | Prints error; bridge will run in stub mode |
| SKR Pico not connected | USB cable missing | Prints manual flash instructions; continues |
| Old printer.cfg present | Prior Klipper config | Backs up before symlinking |

### 4.6 Maintenance

- **Re-running after code changes:** `bash deploy.sh --skip-flash` to skip firmware build and just update configs/services.
- **Adding new Python dependencies:** Update `requirements.txt`, then re-run the script.
- **Updating Klipper firmware:** `bash deploy.sh` (without `--skip-flash`). This rebuilds and reflashes. **Important:** Klipper host and MCU firmware must match the same Klipper commit. If Klipper is updated on the host, the MCU must be reflashed.

---

## 5. Deliverable 4: Setup Instructions

### 5.1 Purpose

Step-by-step instructions for setting up the complete software stack on a fresh Raspberry Pi, from OS installation through verified operation.

### 5.2 Prerequisites

**Hardware required:**

- Raspberry Pi (Pi 4B recommended, Pi 3B+ minimum) with power supply
- MicroSD card (16 GB minimum, 32 GB recommended)
- BigTreeTech SKR Pico V1.0 with USB-C cable
- Ethernet cable (connecting Pi to same network as UR30)
- A computer with SD card reader for flashing the OS
- (Optional) Pi400 on the same network for SSH/monitoring

**Accounts/software on your computer:**

- Raspberry Pi Imager (https://www.raspberrypi.com/software/)
- SSH client (built into macOS/Linux; PuTTY on Windows)

### 5.3 Step 1: Install the Operating System

**Recommended: MainsailOS** (includes Klipper + Moonraker + Mainsail pre-configured).

1. Download the latest MainsailOS image from https://github.com/mainsail-crew/MainsailOS/releases
2. Open Raspberry Pi Imager.
3. Select "Use custom" and choose the downloaded MainsailOS `.img.xz` file.
4. Click the gear icon to configure:
   - **Hostname:** `w26-pi` (or your preference)
   - **Enable SSH:** Yes, with password authentication
   - **Set username:** `pi`
   - **Set password:** (choose a password)
   - **Configure WiFi:** Not needed if using Ethernet; configure if needed for initial setup
   - **Locale:** Set your timezone
5. Write to the SD card.
6. Insert the SD card into the Pi and power on.

**Alternative: Raspberry Pi OS Lite + KIAUH**

If MainsailOS is not suitable (e.g., need a newer kernel, specific packages), use Raspberry Pi OS Lite (64-bit) and install Klipper via KIAUH:

1. Flash Raspberry Pi OS Lite (64-bit, Bookworm) with Raspberry Pi Imager.
2. Configure SSH, hostname, and user as above.
3. Boot, SSH in, then install KIAUH:
   ```bash
   sudo apt-get update && sudo apt-get install -y git
   cd ~ && git clone https://github.com/dw-0/kiauh.git
   ./kiauh/kiauh.sh
   ```
4. In the KIAUH menu, install: Klipper, Moonraker, Mainsail.

**Verification checkpoint:**

```bash
ssh pi@w26-pi.local    # or use the Pi's IP address
systemctl is-active klipper     # should print "active"
systemctl is-active moonraker   # should print "active"
```

If you can access `http://w26-pi.local/` in a browser and see the Mainsail web UI, the base install is working.

### 5.4 Step 2: Network Configuration

The Pi must be reachable by the UR30 controller and (optionally) the Pi400 HMI.

**Option A: DHCP (simpler, recommended for development)**

Leave the Pi on DHCP. Find its IP with:
```bash
hostname -I
```
Configure the UR30's URScript to use this IP, or use the hostname `w26-pi.local` (mDNS).

**Option B: Static IP (recommended for production)**

Edit `/etc/dhcpcd.conf` (or use `nmcli` on Bookworm):

```bash
# For dhcpcd-based systems (MainsailOS, older Raspberry Pi OS):
sudo tee -a /etc/dhcpcd.conf << 'EOF'

# W26 Static IP
interface eth0
static ip_address=192.168.1.50/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
EOF

sudo systemctl restart dhcpcd
```

```bash
# For NetworkManager-based systems (Raspberry Pi OS Bookworm):
sudo nmcli con mod "Wired connection 1" \
    ipv4.method manual \
    ipv4.addresses 192.168.1.50/24 \
    ipv4.gateway 192.168.1.1 \
    ipv4.dns 192.168.1.1
sudo nmcli con up "Wired connection 1"
```

**IP address plan:**

| Device | IP Address | Notes |
|--------|-----------|-------|
| UR30 Controller | 192.168.1.100 | Set via teach pendant (Installation > Network) |
| Pi (Klipper host) | 192.168.1.50 | Static or DHCP reservation |
| Pi400 (HMI) | 192.168.1.51 (or DHCP) | Optional |
| Subnet mask | 255.255.255.0 | /24 |

All devices must be on the same subnet. If a gigabit switch is used, no special switch configuration is needed.

**Verification checkpoint:**

```bash
# From the Pi:
ping -c3 192.168.1.100    # UR30 should respond
```

### 5.5 Step 3: Clone the Repository

```bash
ssh pi@w26-pi.local
cd ~
git clone <repository-url> W26-Cobot-Axis
```

If the repository is private, set up an SSH key or use HTTPS with a personal access token.

**Verification checkpoint:**

```bash
ls ~/W26-Cobot-Axis/src/bridge/bridge_daemon.py    # should exist
```

### 5.6 Step 4: Flash Klipper Firmware to SKR Pico

Connect the SKR Pico to the Pi via USB-C.

**First-time flash (board has never run Klipper):**

1. Build the firmware:
   ```bash
   cd ~/klipper
   make menuconfig
   ```
   Select:
   - Micro-controller Architecture: **Raspberry Pi RP2040**
   - Bootloader offset: **No bootloader**
   - Flash chip: **W25Q080 with CLKDIV 2**
   - Communication interface: **USB**

   Save and exit.

   ```bash
   make clean
   make -j$(nproc)
   ```

2. Enter BOOTSEL mode on the SKR Pico:
   - Hold the BOOTSEL button on the board.
   - While holding, press and release the RESET button (or unplug/replug USB).
   - Release BOOTSEL. The board should appear as a USB mass storage device.

3. Flash:
   ```bash
   sudo mount /dev/sda1 /mnt
   sudo cp ~/klipper/out/klipper.uf2 /mnt/
   sudo sync
   sudo umount /mnt
   ```

4. The board reboots automatically into Klipper firmware.

**Subsequent flashes (board already running Klipper):**

```bash
cd ~/klipper
make clean && make -j$(nproc)
SERIAL=$(ls /dev/serial/by-id/usb-Klipper_rp2040_* | head -1)
make flash FLASH_DEVICE="$SERIAL"
```

**Verification checkpoint:**

```bash
ls /dev/serial/by-id/usb-Klipper_rp2040_*
# Should show something like: usb-Klipper_rp2040_E66058388341A829-if00
```

Record this serial path -- it is needed for `printer.cfg`.

### 5.7 Step 5: Deploy Klipper Configuration

1. Update the MCU serial path in `printer.cfg`:
   ```bash
   SERIAL=$(ls /dev/serial/by-id/usb-Klipper_rp2040_*)
   sed -i "s|serial: /dev/serial/by-id/usb-Klipper_rp2040_PLACEHOLDER-if00|serial: $SERIAL|" \
       ~/W26-Cobot-Axis/src/klipper/printer.cfg
   ```

2. Create the required `gcode_files` directory:
   ```bash
   mkdir -p ~/gcode_files
   ```

3. Symlink the config:
   ```bash
   KLIPPER_CONFIG_DIR="$HOME/printer_data/config"
   [ ! -d "$KLIPPER_CONFIG_DIR" ] && KLIPPER_CONFIG_DIR="$HOME/klipper_config"

   # Backup existing config
   [ -f "$KLIPPER_CONFIG_DIR/printer.cfg" ] && \
       cp "$KLIPPER_CONFIG_DIR/printer.cfg" "$KLIPPER_CONFIG_DIR/printer.cfg.bak"

   ln -sf ~/W26-Cobot-Axis/src/klipper/printer.cfg "$KLIPPER_CONFIG_DIR/printer.cfg"
   ```

4. Restart Klipper:
   ```bash
   sudo systemctl restart klipper
   ```

**Verification checkpoint:**

```bash
# Wait a few seconds, then:
systemctl status klipper
# Should show "active (running)"

# Check klippy log for errors:
cat /tmp/klippy.log | tail -20
# Should end with "Printer is ready" or similar
```

If Klipper reports an MCU error, the serial path in `printer.cfg` is likely wrong. Verify with `ls /dev/serial/by-id/`.

If Klipper reports `MCU protocol error`, the MCU firmware version does not match the host. Reflash the SKR Pico (Step 4).

### 5.8 Step 6: Install Bridge Daemon

1. Install system build prerequisites:
   ```bash
   sudo apt-get update
   sudo apt-get install -y build-essential cmake libboost-all-dev python3-dev
   ```

2. Install Python dependencies:
   ```bash
   ~/klippy-env/bin/pip install --upgrade pip
   ~/klippy-env/bin/pip install -r ~/W26-Cobot-Axis/src/bridge/requirements.txt
   ```
   This will take 5-15 minutes on ARM as `ur-rtde` compiles from source.

3. Test the bridge daemon manually:
   ```bash
   cd ~/W26-Cobot-Axis/src
   ~/klippy-env/bin/python -m bridge --dry-run --log-level DEBUG
   ```
   Expected output: The bridge should start, connect to Klipper (if running), and show `DRY RUN` messages. It will fail to connect to the UR30 (which is expected without the robot) and retry every 2 seconds. Press Ctrl+C to stop.

4. Install and enable the systemd service:
   ```bash
   sudo cp ~/W26-Cobot-Axis/src/systemd/w26-bridge.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable w26-bridge.service
   ```

**Verification checkpoint:**

```bash
sudo systemctl start w26-bridge
journalctl -u w26-bridge -f --no-pager
# Should show bridge starting, connecting to Klipper, retrying RTDE
```

### 5.9 Step 7: Configure Moonraker (Optional)

If Moonraker is installed (MainsailOS includes it), ensure the Mainsail web UI can access Klipper. The default Moonraker configuration from MainsailOS is usually sufficient.

If you need to allow access from the Pi400 or other devices, check `~/printer_data/config/moonraker.conf` (or `~/moonraker.conf`) for the `[authorization]` section:

```ini
[authorization]
trusted_clients:
    127.0.0.1
    192.168.1.0/24
cors_domains:
    *
```

**Verification checkpoint:**

Open `http://w26-pi.local/` in a browser from the Pi400. The Mainsail dashboard should show Klipper's state. If the SKR Pico is connected and the config is correct, Klipper should show "Ready".

### 5.10 Step 8: End-to-End Verification

This step requires the UR30 to be powered on and reachable at `192.168.1.100` (or the IP configured in `src/bridge/config.py`).

1. Ensure a URScript program is loaded on the UR30 that writes to the RTDE output registers (e.g., `src/urscript/extrusion_control.script` or a test program).

2. Start the bridge in non-dry-run mode:
   ```bash
   sudo systemctl restart w26-bridge
   journalctl -u w26-bridge -f
   ```

3. Expected log output:
   ```
   HH:MM:SS [bridge] INFO: Connecting to UR30 at 192.168.1.100:30004 ...
   HH:MM:SS [bridge] INFO: RTDE connected to 192.168.1.100
   HH:MM:SS [bridge] INFO: Connected to klippy at /tmp/klippy_uds
   HH:MM:SS [bridge] INFO: Klipper state: Printer is ready
   HH:MM:SS [bridge] INFO: Bridge running at 125 Hz (dry_run=False)
   ```

4. On the UR30, enable extrusion via URScript (set `output_bit_register_64 = True`, `output_int_register_0 = 1`, `output_double_register_0 = 10.0`). The stepper should begin moving.

### 5.11 Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Mainsail shows "Klipper not connected" | Klipper service not running or crashed | `sudo systemctl restart klipper`; check `cat /tmp/klippy.log` |
| `MCU protocol error` in klippy.log | Firmware version mismatch | Reflash SKR Pico (Step 4) after `cd ~/klipper && git pull && make` |
| `Unable to read tmc uart` warnings | TMC2209 UART wiring or address issue | Verify `uart_pin`, `tx_pin`, `uart_address` in `printer.cfg` match hardware |
| Bridge shows "RTDE connection failed" | UR30 not reachable or not running a program | `ping 192.168.1.100`; ensure UR30 program is running |
| Bridge shows "Klipper connection failed" | klippy socket missing | `systemctl status klipper`; check if `/tmp/klippy_uds` exists |
| Bridge shows "ur_rtde not installed -- using stub" | `ur-rtde` package not installed or build failed | Re-run `pip install ur-rtde`; check Boost is installed |
| Stepper motor does not move but bridge logs look correct | Stepper current too low or wiring issue | Check TMC2209 `run_current` in `printer.cfg`; check step/dir/enable wiring |
| Pi under-voltage warning (lightning bolt on screen) | Insufficient power supply | Use a proper 5.1V/3A supply; check buck converter output voltage |

---

## 6. Network Configuration

### 6.1 Network Topology

```
                    Gigabit Switch (or direct cable)
                   /           |             \
            UR30             Pi              Pi400
         192.168.1.100    192.168.1.50    192.168.1.51
          (robot)      (Klipper host)      (HMI)
                          port 30004 <-- RTDE
                          port 7125 --> Moonraker
                          port 22 --> SSH
```

### 6.2 Firewall

Raspberry Pi OS does not enable a firewall by default. If `ufw` or `iptables` rules are added, the following ports must be open:

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 22 | TCP | Inbound | SSH access |
| 7125 | TCP | Inbound | Moonraker API (Mainsail web UI) |
| 80 | TCP | Inbound | Mainsail web interface (nginx) |
| 30004 | TCP | Outbound | RTDE to UR30 |

### 6.3 Static IP vs DHCP

**Recommendation: Static IP for the Pi in production.**

The UR30's URScript program references the Pi's IP indirectly (the bridge connects to the UR30, not the other way around), but having a stable IP simplifies SSH access, Mainsail bookmarks, and log review. If DHCP is used, configure a DHCP reservation on the router/switch for the Pi's MAC address.

---

## 7. File Placement Summary

### 7.1 Repository Files (source of truth)

| File | Repository Path |
|------|----------------|
| Bridge daemon source | `src/bridge/*.py` |
| Bridge requirements | `src/bridge/requirements.txt` |
| Klipper printer config | `src/klipper/printer.cfg` |
| systemd service file | `src/systemd/w26-bridge.service` |
| Deployment script | `deploy.sh` |
| This document | `docs/design/deployment.md` |

### 7.2 Deployed Locations on Pi

| Purpose | Path on Pi | Source |
|---------|-----------|--------|
| Repository clone | `/home/pi/W26-Cobot-Axis/` | git clone |
| Klipper printer config | `~/printer_data/config/printer.cfg` | Symlink to repo |
| systemd service | `/etc/systemd/system/w26-bridge.service` | Copied from repo |
| Python virtualenv | `/home/pi/klippy-env/` | Created by Klipper installer |
| Klipper source | `/home/pi/klipper/` | Created by Klipper installer |
| Moonraker source | `/home/pi/moonraker/` | Created by Moonraker installer |
| klippy UDS socket | `/tmp/klippy_uds` | Created by Klipper at runtime |
| klippy log | `/tmp/klippy.log` | Created by Klipper at runtime |
| G-code files directory | `/home/pi/gcode_files/` | Created by setup |

---

## 8. Maintenance Procedures

### 8.1 Updating Bridge Code

```bash
ssh pi@w26-pi.local
cd ~/W26-Cobot-Axis
git pull
sudo systemctl restart w26-bridge
```

No re-installation needed -- the service runs directly from the repository clone.

### 8.2 Updating Klipper

```bash
cd ~/klipper
git pull

# IMPORTANT: Reflash MCU firmware after updating Klipper host
make clean && make -j$(nproc)
SERIAL=$(ls /dev/serial/by-id/usb-Klipper_rp2040_* | head -1)
make flash FLASH_DEVICE="$SERIAL"

sudo systemctl restart klipper
sudo systemctl restart w26-bridge
```

Klipper host and MCU firmware must always be from the same git commit. Mismatched versions cause `MCU protocol error`.

### 8.3 Changing the UR30 IP Address

1. Edit `src/bridge/config.py`:
   ```python
   UR30_HOST = "192.168.1.XXX"    # new IP
   ```
2. Restart the bridge:
   ```bash
   sudo systemctl restart w26-bridge
   ```

Alternatively, override at runtime without editing the config file:

Edit the systemd service file to pass `--host`:
```ini
ExecStart=/home/pi/klippy-env/bin/python -m bridge --host 192.168.1.XXX
```

### 8.4 Viewing Logs

```bash
# Bridge daemon logs
journalctl -u w26-bridge -f

# Klipper logs
cat /tmp/klippy.log | tail -50

# Moonraker logs
journalctl -u moonraker -f

# All services together
journalctl -u klipper -u moonraker -u w26-bridge -f
```

### 8.5 Backup and Restore

**What to back up:**

- `~/W26-Cobot-Axis/` (the repository -- but this is in git, so `git push` is the backup)
- `~/printer_data/config/` (Klipper config -- but our `printer.cfg` is in the repo via symlink)

**What does not need backup:**

- Klipper source (`~/klipper/`) -- can be re-cloned
- Moonraker source (`~/moonraker/`) -- can be re-cloned
- Python virtualenv (`~/klippy-env/`) -- can be recreated

The entire system can be rebuilt from a fresh MainsailOS image + the repository.

---

## 9. Open Questions

These items require decisions before implementation. They should be resolved during Phase 3 (Build).

| Question | Options | Impact |
|----------|---------|--------|
| Which Pi model for the headless node? | Pi 4B (2GB+), Pi 3B+ | Affects power budget and deployment paths. Pi 4B recommended. |
| Shared virtualenv or separate? | Reuse `klippy-env` vs create `w26-env` | Shared is simpler; separate is cleaner. Start shared, split if conflicts arise. |
| Static IP or DHCP? | Static (edit dhcpcd/nmcli) vs DHCP reservation | Static is more reliable for production. Use DHCP during development. |
| MainsailOS or manual Klipper install? | MainsailOS (faster) vs Pi OS + KIAUH (more control) | MainsailOS recommended for speed; KIAUH if specific OS version is needed. |
| USB serial or UART for Pi-to-SKR Pico? | USB-C cable vs GPIO UART wires | USB is simpler and recommended for initial development. UART for production if USB proves unreliable in the UR30's electrical environment. |
| Should the bridge run in its own virtualenv? | Yes (isolated) vs No (shared with Klipper) | Shared approach documented; revisit if package conflicts arise. |
| How to handle `printer.cfg` edits via Mainsail? | Symlink (edits go back to repo) vs copy (edits are local) | Symlink keeps repo as source of truth but Mainsail edits change the repo copy. |

---

*This document is a design specification. Implementation files (`requirements.txt`, `w26-bridge.service`, `deploy.sh`) should be created based on the specifications above during Phase 3.*
