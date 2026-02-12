# W26 Cobot Axis -- Setup Instructions

Step-by-step guide for setting up the complete software stack on a fresh Raspberry Pi. Covers OS installation through verified end-to-end operation.

**Project:** W26 Cobot Axis -- ME472 Mechatronics Capstone
**Target:** Raspberry Pi (headless) running Klipper + RTDE bridge daemon, controlling an SKR Pico V1.0 stepper driver for metal paste dispensing.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Step 1: Install the Operating System](#2-step-1-install-the-operating-system)
3. [Step 2: Network Configuration](#3-step-2-network-configuration)
4. [Step 3: Clone the Repository](#4-step-3-clone-the-repository)
5. [Step 4: Flash Klipper Firmware to SKR Pico](#5-step-4-flash-klipper-firmware-to-skr-pico)
6. [Step 5: Deploy Klipper Configuration](#6-step-5-deploy-klipper-configuration)
7. [Step 6: Install the Bridge Daemon](#7-step-6-install-the-bridge-daemon)
8. [Step 7: Configure Moonraker (Optional)](#8-step-7-configure-moonraker-optional)
9. [Step 8: End-to-End Verification](#9-step-8-end-to-end-verification)
10. [Troubleshooting](#10-troubleshooting)
11. [Maintenance](#11-maintenance)

---

## 1. Prerequisites

### Hardware Required

| Item | Notes |
|------|-------|
| Raspberry Pi (Pi 4B recommended, Pi 3B+ minimum) | With appropriate power supply (5.1V/3A) |
| MicroSD card | 16 GB minimum, 32 GB recommended |
| BigTreeTech SKR Pico V1.0 | With USB-C cable for connecting to the Pi |
| Ethernet cable | Connecting Pi to same network/switch as UR30 |
| Computer with SD card reader | For flashing the OS image |
| (Optional) Pi400 | On the same network for SSH access and Mainsail web UI |

### Software on Your Computer

- **Raspberry Pi Imager** -- download from https://www.raspberrypi.com/software/
- **SSH client** -- built into macOS and Linux terminals; use PuTTY on Windows

### Network Requirements

All devices (Pi, UR30, optional Pi400) must be on the same subnet. A gigabit switch is recommended but a direct Ethernet cable between the Pi and UR30 works for a two-device setup.

---

## 2. Step 1: Install the Operating System

### Option A: MainsailOS (Recommended)

MainsailOS is a pre-configured image that includes Klipper, Moonraker, and the Mainsail web UI out of the box. This is the fastest path to a working system.

1. Download the latest MainsailOS release from:
   https://github.com/mainsail-crew/MainsailOS/releases

2. Open **Raspberry Pi Imager** on your computer.

3. Click **"Choose OS"** then **"Use custom"** and select the downloaded `.img.xz` file.

4. Click the **gear icon** (or Ctrl+Shift+X) to open advanced settings:
   - **Hostname:** `w26-pi`
   - **Enable SSH:** Yes, with password authentication
   - **Set username:** `pi`
   - **Set password:** choose a secure password
   - **Configure WiFi:** skip if using Ethernet (recommended); configure if needed for initial headless setup
   - **Locale:** set your timezone

5. Select your SD card under **"Choose Storage"**.

6. Click **"Write"** and wait for the process to complete.

7. Insert the SD card into the Pi and power it on. Wait 2-3 minutes for the first boot to complete.

### Option B: Raspberry Pi OS Lite + KIAUH

Use this approach if you need a specific OS version, a newer kernel, or more control over the installation.

1. Flash **Raspberry Pi OS Lite (64-bit, Bookworm)** using Raspberry Pi Imager with the same advanced settings as above (hostname `w26-pi`, user `pi`, SSH enabled).

2. Boot the Pi and SSH in:
   ```bash
   ssh pi@w26-pi.local
   ```

3. Install KIAUH (Klipper Installation And Update Helper):
   ```bash
   sudo apt-get update && sudo apt-get install -y git
   cd ~ && git clone https://github.com/dw-0/kiauh.git
   ./kiauh/kiauh.sh
   ```

4. In the KIAUH menu, install in this order:
   - **Klipper**
   - **Moonraker**
   - **Mainsail**

   Follow the prompts for each installation. Accept defaults unless you have a specific reason to change them.

### Verification Checkpoint

```bash
ssh pi@w26-pi.local
systemctl is-active klipper      # should print: active
systemctl is-active moonraker    # should print: active
```

Open `http://w26-pi.local/` in a browser. You should see the Mainsail web UI (it will show a Klipper error about missing config -- that is expected and will be fixed in Step 5).

---

## 3. Step 2: Network Configuration

The Pi must be reachable by the UR30 controller over Ethernet. Both devices must be on the same subnet.

### Option A: DHCP (Simpler, Good for Development)

If your network has a DHCP server (router), the Pi will get an IP automatically. Find it with:

```bash
hostname -I
```

You can use `w26-pi.local` (mDNS) to reach the Pi from other devices on the network. This works on macOS and Linux out of the box; Windows may need Bonjour installed.

### Option B: Static IP (Recommended for Production)

A static IP ensures the Pi is always reachable at the same address, which simplifies URScript configuration and SSH access.

**For dhcpcd-based systems (MainsailOS, older Raspberry Pi OS):**

```bash
sudo tee -a /etc/dhcpcd.conf << 'EOF'

# W26 Static IP
interface eth0
static ip_address=192.168.1.50/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
EOF

sudo systemctl restart dhcpcd
```

**For NetworkManager-based systems (Raspberry Pi OS Bookworm):**

```bash
sudo nmcli con mod "Wired connection 1" \
    ipv4.method manual \
    ipv4.addresses 192.168.1.50/24 \
    ipv4.gateway 192.168.1.1 \
    ipv4.dns 192.168.1.1
sudo nmcli con up "Wired connection 1"
```

### IP Address Plan

| Device | IP Address | Notes |
|--------|-----------|-------|
| UR30 Controller | 192.168.1.100 | Set via teach pendant: Installation > Network |
| Pi (Klipper host) | 192.168.1.50 | Static or DHCP reservation |
| Pi400 (HMI) | 192.168.1.51 (or DHCP) | Optional |
| Subnet mask | 255.255.255.0 | /24 network |

### Verification Checkpoint

```bash
# From the Pi -- verify UR30 is reachable:
ping -c3 192.168.1.100

# From the Pi400 or your computer -- verify Pi is reachable:
ping -c3 192.168.1.50
```

---

## 4. Step 3: Clone the Repository

SSH into the Pi and clone the project repository:

```bash
ssh pi@w26-pi.local
cd ~
git clone <repository-url> W26-Cobot-Axis
```

Replace `<repository-url>` with the actual URL. If the repository is private, use SSH keys or HTTPS with a personal access token.

### Verification Checkpoint

```bash
ls ~/W26-Cobot-Axis/src/bridge/bridge_daemon.py
# Should exist and print the path without errors
```

---

## 5. Step 4: Flash Klipper Firmware to SKR Pico

Connect the SKR Pico V1.0 to the Pi via its USB-C port.

### First-Time Flash (Board Has Never Run Klipper)

The SKR Pico ships with no firmware or with a default bootloader. The first flash must use the UF2 method via the RP2040's built-in USB mass storage bootloader.

**1. Build the firmware:**

```bash
cd ~/klipper
make menuconfig
```

In the menuconfig interface, set:

| Setting | Value |
|---------|-------|
| Micro-controller Architecture | **Raspberry Pi RP2040** |
| Bootloader offset | **No bootloader** |
| Flash chip | **W25Q080 with CLKDIV 2** |
| Communication interface | **USB** |

Save (press Q, then Y) and exit.

```bash
make clean
make -j$(nproc)
```

This produces `~/klipper/out/klipper.uf2`.

**2. Enter BOOTSEL mode on the SKR Pico:**

- Hold the **BOOTSEL** button on the board.
- While holding BOOTSEL, press and release the **RESET** button (or unplug and replug the USB cable).
- Release BOOTSEL.
- The board appears as a USB mass storage device (like a USB flash drive).

**3. Flash the firmware:**

```bash
sudo mount /dev/sda1 /mnt
sudo cp ~/klipper/out/klipper.uf2 /mnt/
sudo sync
sudo umount /mnt
```

The board reboots automatically into Klipper firmware after the file is copied.

### Subsequent Flashes (Board Already Running Klipper)

Once Klipper is running on the SKR Pico, you can flash over USB without BOOTSEL:

```bash
cd ~/klipper
make clean && make -j$(nproc)
SERIAL=$(ls /dev/serial/by-id/usb-Klipper_rp2040_* | head -1)
make flash FLASH_DEVICE="$SERIAL"
```

### Verification Checkpoint

```bash
ls /dev/serial/by-id/usb-Klipper_rp2040_*
# Should show something like:
# /dev/serial/by-id/usb-Klipper_rp2040_E66058388341A829-if00
```

**Record this serial path.** You will need it for `printer.cfg` in the next step.

---

## 6. Step 5: Deploy Klipper Configuration

**1. Update the MCU serial path in `printer.cfg`:**

```bash
SERIAL=$(ls /dev/serial/by-id/usb-Klipper_rp2040_*)
sed -i "s|serial: /dev/serial/by-id/usb-Klipper_rp2040_PLACEHOLDER-if00|serial: $SERIAL|" \
    ~/W26-Cobot-Axis/src/klipper/printer.cfg
```

Verify the change:

```bash
grep "serial:" ~/W26-Cobot-Axis/src/klipper/printer.cfg
# Should show the actual device path, not PLACEHOLDER
```

**2. Create the gcode_files directory** (required by the `[virtual_sdcard]` section in `printer.cfg`):

```bash
mkdir -p ~/gcode_files
```

**3. Symlink the config to the Klipper config directory:**

```bash
# Determine config directory (MainsailOS uses printer_data/config)
KLIPPER_CONFIG_DIR="$HOME/printer_data/config"
[ ! -d "$KLIPPER_CONFIG_DIR" ] && KLIPPER_CONFIG_DIR="$HOME/klipper_config"

# Backup any existing config
if [ -f "$KLIPPER_CONFIG_DIR/printer.cfg" ] && [ ! -L "$KLIPPER_CONFIG_DIR/printer.cfg" ]; then
    cp "$KLIPPER_CONFIG_DIR/printer.cfg" "$KLIPPER_CONFIG_DIR/printer.cfg.bak"
fi

# Create symlink
ln -sf ~/W26-Cobot-Axis/src/klipper/printer.cfg "$KLIPPER_CONFIG_DIR/printer.cfg"
```

**4. Restart Klipper:**

```bash
sudo systemctl restart klipper
```

### Verification Checkpoint

```bash
# Wait 5-10 seconds, then check:
systemctl status klipper
# Should show "active (running)"

# Check the Klipper log for errors:
tail -20 /tmp/klippy.log
# Should end with "Printer is ready" or similar
```

**Common issues at this step:**

| Error in klippy.log | Cause | Fix |
|---------------------|-------|-----|
| `Unable to open serial port` | Wrong serial path in printer.cfg | Run `ls /dev/serial/by-id/` and update printer.cfg |
| `MCU protocol error` | Firmware version does not match host | Reflash SKR Pico (see Step 4) after `cd ~/klipper && git pull` |
| `Unable to read tmc uart` | TMC2209 UART config mismatch | Verify `uart_pin`, `tx_pin`, `uart_address` in printer.cfg |

---

## 7. Step 6: Install the Bridge Daemon

### Option A: Automated Deployment (Recommended)

The deployment script handles all remaining setup in one command:

```bash
cd ~/W26-Cobot-Axis
chmod +x deploy.sh
bash deploy.sh --skip-flash
```

Use `--skip-flash` since you already flashed the SKR Pico in Step 4. The script will:

- Install system build dependencies (build-essential, cmake, Boost)
- Verify Klipper and Moonraker installations
- Install Python dependencies (ur-rtde) into the Klipper virtualenv
- Deploy the printer.cfg symlink (idempotent -- safe if already done)
- Install and enable the `w26-bridge.service` systemd unit
- Update the MCU serial path if needed
- Restart all services and verify

### Option B: Manual Installation

If you prefer to install step by step:

**1. Install system build prerequisites:**

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake \
    libboost-system-dev libboost-thread-dev libboost-filesystem-dev \
    python3-dev python3-pip
```

**2. Install Python dependencies into the Klipper virtualenv:**

```bash
~/klippy-env/bin/pip install --upgrade pip
~/klippy-env/bin/pip install -r ~/W26-Cobot-Axis/src/bridge/requirements.txt
```

This takes 5-15 minutes on ARM as `ur-rtde` compiles from C++ source. If the build fails, the bridge will still run in stub mode (no robot connection) which is useful for development and testing.

**3. Test the bridge daemon manually:**

```bash
cd ~/W26-Cobot-Axis/src
~/klippy-env/bin/python -m bridge --dry-run --log-level DEBUG
```

Expected output: the bridge starts, connects to Klipper (if running), and shows `DRY RUN` messages. It will fail to connect to the UR30 if the robot is not on the network (expected) and retry every 2 seconds. Press Ctrl+C to stop.

**4. Install and enable the systemd service:**

```bash
sudo cp ~/W26-Cobot-Axis/src/systemd/w26-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable w26-bridge.service
```

**5. Start the bridge:**

```bash
sudo systemctl start w26-bridge
```

### Verification Checkpoint

```bash
systemctl status w26-bridge
# Should show "active (running)"

journalctl -u w26-bridge -f --no-pager
# Should show the bridge starting up and connecting to Klipper.
# If the UR30 is not on the network, you will see:
#   "RTDE connection failed ... retrying in 2s"
# This is normal -- the bridge retries until the robot is available.
```

---

## 8. Step 7: Configure Moonraker (Optional)

If Moonraker is installed (MainsailOS includes it by default), the Mainsail web UI provides a browser-based dashboard for monitoring Klipper status, viewing the printer.cfg, and checking logs.

The default Moonraker configuration from MainsailOS is usually sufficient. If you need to allow access from additional devices (e.g., the Pi400), check the authorization settings:

```bash
# Check the Moonraker config file:
cat ~/printer_data/config/moonraker.conf
# or on older setups:
cat ~/moonraker.conf
```

Ensure the `[authorization]` section includes your local subnet:

```ini
[authorization]
trusted_clients:
    127.0.0.1
    192.168.1.0/24
cors_domains:
    *
```

### Verification Checkpoint

Open `http://w26-pi.local/` in a browser from the Pi400 or any computer on the same network. The Mainsail dashboard should show Klipper's state. If the SKR Pico is connected and the config is correct, Klipper should show "Ready".

---

## 9. Step 8: End-to-End Verification

This step requires the UR30 to be powered on and reachable at the configured IP address (default: `192.168.1.100`, set in `src/bridge/config.py`).

**1. Load a URScript program on the UR30** that writes to the RTDE output registers. The project includes a test program at `src/urscript/extrusion_control.script`. Load it via the teach pendant or the UR30's Polyscope interface.

**2. Start (or restart) the bridge daemon:**

```bash
sudo systemctl restart w26-bridge
journalctl -u w26-bridge -f
```

**3. Expected log output when everything is connected:**

```
HH:MM:SS [bridge] INFO: Connecting to UR30 at 192.168.1.100:30004 ...
HH:MM:SS [bridge] INFO: RTDE connected to 192.168.1.100
HH:MM:SS [bridge] INFO: Connected to klippy at /tmp/klippy_uds
HH:MM:SS [bridge] INFO: Klipper state: Printer is ready
HH:MM:SS [bridge] INFO: Bridge running at 125 Hz (dry_run=False)
```

**4. Trigger extrusion from the UR30.** In the URScript program, set:

- `output_bit_register_64 = True` (enable)
- `output_int_register_0 = 1` (extrude mode)
- `output_double_register_0 = 10.0` (10 mm/s rate)

The stepper motor should begin moving. The bridge log will show commands being translated.

**5. Verify status feedback.** The bridge writes status back to the UR30 via RTDE input registers:

- `input_int_register_0` = 1 (running)
- `input_double_register_0` = actual rate (mm/s)
- `input_bit_register_64` = True (ready)

These can be read in URScript or viewed in the teach pendant's RTDE monitor.

---

## 10. Troubleshooting

### Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Mainsail shows "Klipper not connected" | Klipper service not running | `sudo systemctl restart klipper` then check `/tmp/klippy.log` |
| `MCU protocol error` in klippy.log | Firmware version mismatch between host and MCU | Reflash SKR Pico: `cd ~/klipper && git pull && make clean && make && make flash FLASH_DEVICE=...` |
| `Unable to read tmc uart` in klippy.log | TMC2209 UART wiring or address wrong | Verify `uart_pin`, `tx_pin`, `uart_address` in printer.cfg match SKR Pico hardware |
| Bridge shows "RTDE connection failed" | UR30 not reachable or no program running | `ping 192.168.1.100` -- ensure UR30 is powered on with a program loaded |
| Bridge shows "Klipper connection failed" | klippy socket missing | `systemctl status klipper` -- fix Klipper issues first, check `/tmp/klippy_uds` exists |
| Bridge shows "ur_rtde not installed -- using stub" | ur-rtde package not installed | `~/klippy-env/bin/pip install ur-rtde` -- check Boost is installed first |
| Stepper does not move but bridge logs look correct | Current too low or wiring issue | Check `run_current` in printer.cfg; verify step/dir/enable pin wiring to motor |
| Lightning bolt icon on Pi HDMI output | Under-voltage from power supply | Use a proper 5.1V/3A supply; check buck converter output |
| Bridge hits systemd start limit | Bridge crashing repeatedly | `sudo systemctl reset-failed w26-bridge` then fix root cause and restart |

### Viewing Logs

```bash
# Bridge daemon logs (live follow):
journalctl -u w26-bridge -f

# Bridge daemon logs (today only):
journalctl -u w26-bridge --since today

# Bridge daemon errors only:
journalctl -u w26-bridge -p err

# Klipper log:
tail -50 /tmp/klippy.log

# Moonraker logs:
journalctl -u moonraker -f

# All services together:
journalctl -u klipper -u moonraker -u w26-bridge -f
```

### Running the Bridge Manually (Bypassing systemd)

For debugging, stop the systemd service and run the bridge directly:

```bash
sudo systemctl stop w26-bridge
cd ~/W26-Cobot-Axis/src
~/klippy-env/bin/python -m bridge --log-level DEBUG
```

This gives you direct terminal output and lets you use Ctrl+C to stop. Add `--dry-run` to test without sending commands to Klipper.

---

## 11. Maintenance

### Updating Bridge Code

```bash
ssh pi@w26-pi.local
cd ~/W26-Cobot-Axis
git pull
sudo systemctl restart w26-bridge
```

No reinstallation needed -- the systemd service runs directly from the repository clone.

### Updating Klipper

When updating Klipper on the host, you **must** also reflash the MCU firmware. Mismatched versions cause `MCU protocol error`.

```bash
cd ~/klipper
git pull
make clean && make -j$(nproc)
SERIAL=$(ls /dev/serial/by-id/usb-Klipper_rp2040_* | head -1)
make flash FLASH_DEVICE="$SERIAL"
sudo systemctl restart klipper
sudo systemctl restart w26-bridge
```

### Changing the UR30 IP Address

Edit `src/bridge/config.py` and change the `UR30_HOST` value:

```python
UR30_HOST = "192.168.1.XXX"    # your new IP
```

Then restart:

```bash
sudo systemctl restart w26-bridge
```

### Re-Running the Deployment Script

The deployment script is idempotent and safe to re-run at any time:

```bash
cd ~/W26-Cobot-Axis
bash deploy.sh --skip-flash    # skip firmware flash, just update configs/services
bash deploy.sh                 # full deployment including firmware rebuild
```

### Backup

The entire system can be rebuilt from a fresh MainsailOS image plus the git repository. The only state that matters is:

- The git repository (backed up by `git push`)
- The MCU serial path in `printer.cfg` (board-specific, must be re-detected on new hardware)

Everything else (Klipper, Moonraker, virtualenv, systemd service) is reproducible via the deployment script.
