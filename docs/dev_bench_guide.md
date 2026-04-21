# Dev Bench Bring-Up Guide

Step-by-step guide for setting up a development bench with real hardware (Pi + SKR Pico + stepper motor) and URSim on Windows. This bench validates the full signal chain — RTDE → bridge → Klipper → motor — before deploying to the production UR30 lab setup.

---

## 1. Overview

### What the dev bench tests

The dev bench exercises the complete communication chain with real hardware:

```
URSim (Docker on Windows)  ──RTDE/TCP──▶  Pi (Klipper + bridge)  ──USB──▶  SKR Pico  ──▶  Stepper Motor
```

This catches integration issues that mock tests cannot: USB serial timing, Klipper firmware compatibility, TMC2209 driver behavior, and real stepper motion.

### What it can't test

- Real UR30 timing characteristics (URSim is not cycle-accurate)
- Teach pendant interaction (noVNC is a close approximation)
- Robot safety systems (e-stop relay, protective stop behavior)
- Production network topology and latency

### Dev vs prod strategy

**Single branch, single `deploy.sh`, per-Pi systemd override.** No git branching for environments.

| Aspect | Dev Bench | Prod (Dawood's Lab) |
|--------|-----------|---------------------|
| UR controller | URSim (Docker on Windows) | Real UR30 |
| Pi hostname | `w26-dev` | `w26-pi` |
| Network | Home LAN, DHCP + mDNS | Lab switch, static IP `192.168.0.50` |
| Bridge `--host` | Windows PC LAN IP | `192.168.0.3` (UR30) |
| Config method | systemd override | Default `config.py` values |
| 24V power | Bench PSU | UR controller power block |

The bridge daemon's `--host` CLI flag (set via systemd override) is the **only** difference. Everything else — code, deploy script, `printer.cfg` — is identical.

---

## 2. Dev Bench Hardware

No shopping list — these items are available:

| Item | Notes |
|------|-------|
| Raspberry Pi 4B | Headless control node |
| 5.1V/3A USB-C PSU | Pi power supply |
| 32 GB microSD card | For MainsailOS |
| SKR Pico V1.0 | Klipper MCU, USB-C data cable to Pi |
| NEMA17 stepper motor | Any bipolar stepper for testing |
| 24V bench power supply | Powers SKR Pico VIN (2A minimum) |
| Ethernet cable | Pi to router/switch |
| Windows PC | Running Docker Desktop (WSL2) for URSim |

---

## 3. SD Card Imaging

Use MainsailOS — it includes Klipper, Moonraker, and Mainsail pre-installed.

1. Download the latest MainsailOS release from the [MainsailOS releases page](https://github.com/mainsail-crew/MainsailOS/releases).

2. Open **Raspberry Pi Imager**, click **"Choose OS" → "Use custom"**, select the `.img.xz` file.

3. Click the gear icon (Ctrl+Shift+X) for advanced settings:
   - **Hostname:** `w26-dev` (not `w26-pi` — that's prod)
   - **Enable SSH:** Yes, with password authentication
   - **Username:** `pi`
   - **Password:** choose a secure password
   - **WiFi:** skip (using Ethernet)

4. Select SD card, click **"Write"**, wait for completion.

5. Insert SD card into Pi, power on, wait 2–3 minutes for first boot.

See [SETUP.md](../SETUP.md) Step 1 for more detail — the only difference is the hostname (`w26-dev` instead of `w26-pi`).

---

## 4. Pi First Boot

```bash
ssh pi@w26-dev.local
```

Verify services are running:

```bash
systemctl is-active klipper      # should print: active
systemctl is-active moonraker    # should print: active
```

Verify Mainsail web UI loads at `http://w26-dev.local/` (Klipper error about missing config is expected — fixed after deploy).

DHCP is fine for the dev bench — mDNS (`w26-dev.local`) handles discovery without static IP configuration.

---

## 5. Clone Repo and Deploy

```bash
cd ~
git clone <repository-url> W26-Cobot-Axis
cd W26-Cobot-Axis
bash deploy.sh
```

`deploy.sh` handles everything: system deps, Python deps (ur-rtde), printer.cfg symlink, firmware build + flash, systemd service install, serial path auto-discovery.

If the SKR Pico was already flashed separately:

```bash
bash deploy.sh --skip-flash
```

### Verification

```bash
systemctl is-active klipper        # active
systemctl is-active w26-bridge     # active
ls /dev/serial/by-id/usb-Klipper_rp2040_*   # MCU enumerated
tail -5 /tmp/klippy.log            # "Printer is ready"
```

---

## 6. SKR Pico Firmware Flash

`deploy.sh` handles firmware build and flash automatically (Steps 7–8). If you need to flash manually:

1. **Enter BOOTSEL mode:** Hold the BOOTSEL button on the SKR Pico, then plug in the USB cable (or press RESET while holding BOOTSEL). Release BOOTSEL. The board appears as a USB mass storage device.

2. **Build and copy firmware:**
   ```bash
   cd ~/klipper
   make menuconfig   # RP2040, no bootloader, W25Q080 CLKDIV 2, USB
   make clean && make -j$(nproc)
   sudo mount /dev/sda1 /mnt
   sudo cp out/klipper.uf2 /mnt/
   sudo sync && sudo umount /mnt
   ```

3. **Verify MCU enumeration:**
   ```bash
   ls /dev/serial/by-id/usb-Klipper_rp2040_*
   ```

For subsequent flashes (board already running Klipper), use `make flash FLASH_DEVICE=<serial-path>` instead of BOOTSEL.

---

## 7. URSim Setup (Docker on Windows)

URSim runs in Docker Desktop with the WSL2 backend. This section is a condensed version of [docs/ursim_quickstart.md](ursim_quickstart.md) — refer there for detailed troubleshooting.

### Start URSim

Open PowerShell:

```powershell
docker run --rm -d --name ursim --platform=linux/amd64 `
  -e ROBOT_MODEL=UR30 `
  -p 30004:30004 `
  -p 29999:29999 `
  -p 6080:6080 `
  universalrobots/ursim_e-series
```

Wait ~30 seconds for the container to boot.

### Power on the virtual robot

1. Open `http://localhost:6080` in a browser (noVNC teach pendant).
2. Click the **power button** (bottom-left) → **ON** → **START**.
3. Wait for robot status to show **Normal** (green).

> RTDE port 30004 does not respond until the virtual robot is powered on.

### Find the Windows LAN IP

```powershell
ipconfig
```

Look for the **IPv4 Address** on the adapter that shares a subnet with the Pi (e.g., `192.168.1.42`). This is `<WINDOWS_IP>` in the steps below.

### Windows Firewall

Open inbound TCP ports 30004 and 29999 so the Pi can reach URSim:

```powershell
New-NetFirewallRule -DisplayName "URSim RTDE" -Direction Inbound -LocalPort 30004 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "URSim Dashboard" -Direction Inbound -LocalPort 29999 -Protocol TCP -Action Allow
```

Or temporarily disable the firewall on the private network profile (Settings → Network & Internet → Windows Firewall).

### Verify connectivity from Pi

```bash
nc -zv <WINDOWS_IP> 30004
# Should print: Connection to <WINDOWS_IP> 30004 port [tcp/*] succeeded!
```

---

## 8. Configure Bridge for URSim

The bridge daemon defaults to `--host 192.168.0.3` (the prod UR30 IP). Override this for dev.

### Option A: Systemd override (persistent across reboots)

```bash
sudo systemctl edit w26-bridge
```

Add the following (the first blank `ExecStart=` clears the default):

```ini
[Service]
ExecStart=
ExecStart=%h/klippy-env/bin/python -m bridge --host <WINDOWS_IP> --log-level DEBUG
```

Save, then:

```bash
sudo systemctl restart w26-bridge
```

### Option B: Manual foreground run (for debugging)

```bash
sudo systemctl stop w26-bridge
cd ~/W26-Cobot-Axis/src
~/klippy-env/bin/python -m bridge --host <WINDOWS_IP> --log-level DEBUG
```

This gives direct terminal output. Press Ctrl+C to stop. Add `--no-status-poll` if the SKR Pico is not connected (skips TMC2209/StallGuard queries). Add `--dry-run` to skip the Klipper connection entirely.

---

## 9. End-to-End Verification Checklist

Run through these in order. Each step depends on the previous one.

- [ ] **URSim running** — container up, robot powered on in noVNC (`http://localhost:6080`)
- [ ] **Pi reaches URSim** — `nc -zv <WINDOWS_IP> 30004` succeeds from the Pi
- [ ] **Bridge connects** — `journalctl -u w26-bridge -f` shows `RTDE connected to <WINDOWS_IP>`
- [ ] **Klipper ready** — Mainsail at `http://w26-dev.local/` shows green "Ready" status
- [ ] **Motor test via Mainsail console:**
  ```
  MANUAL_STEPPER STEPPER=pump ENABLE=1
  MANUAL_STEPPER STEPPER=pump SET_POSITION=0
  MANUAL_STEPPER STEPPER=pump MOVE=10 SPEED=5
  ```
  Motor should rotate visibly.
- [ ] **RTDE round-trip** — load [`src/urscript/test_basic.script`](../src/urscript/test_basic.script) in URSim, run Sub-tests A–F — motor responds to RTDE commands through the bridge. In a separate terminal, follow the bridge log:
  ```bash
  ssh pi@w26-dev.local journalctl -u w26-bridge -f
  ```
  Expected: for each sub-test the teach-pendant log shows `[PASS] Sub-test X`, and the bridge log shows the corresponding mode/rate/enable register changes (e.g., `mode=1 rate=10.0 enable=True`). Sub-tests G and H are waypoint-dependent and stay commented out until `config_guide.md` Section 5a is done.

> **Next step:** Once the bench is verified, configure hardware-dependent parameters (motor current, rotation distance, waypoints, etc.) using `docs/config_guide.md`.

---

## 10. Dev Workflow

Once the bench is running, the daily workflow is:

1. **Edit code** on your dev machine (laptop/desktop).

2. **Push to Pi** with the fast sync script (~5 seconds):
   ```bash
   ./scripts/dev-sync.sh pi@w26-dev.local
   ```
   This rsyncs changed source files and restarts the bridge daemon.

3. **Watch logs** in a separate terminal:
   ```bash
   ssh pi@w26-dev.local journalctl -u w26-bridge -f
   ```

4. **Run tests locally** (no hardware needed):
   ```bash
   python -m pytest src/bridge/tests/ -v
   ```

5. **Monitor Klipper** via Mainsail at `http://w26-dev.local/`.

---

## 11. Promoting to Prod

When dev bench testing passes and changes are ready for the real UR30:

1. **Push to `main`** — same branch, no environment branching.

2. **On the prod Pi (`w26-pi`):**
   ```bash
   git pull && bash deploy.sh --skip-flash
   ```
   Or for a quick update:
   ```bash
   ./scripts/dev-sync.sh pi@w26-pi.local
   ```

3. **No code changes needed.** The only difference is the systemd override — prod uses the default `--host 192.168.0.3`, dev uses `--host <WINDOWS_IP>`.

---

## 12. Troubleshooting

### Windows Firewall blocking RTDE (most common issue)

**Symptom:** `nc -zv <WINDOWS_IP> 30004` times out from the Pi.

**Fix:** Open port 30004 in Windows Firewall (see [Section 7](#windows-firewall)), or temporarily disable the firewall on the private network profile.

### Bridge can't reach URSim

| Symptom | Fix |
|---------|-----|
| `Connection refused` | Robot not powered on in noVNC — click power → ON → START |
| `Connection timed out` | Wrong IP, firewall, or Pi not on same subnet |
| Bridge logs show stub mode | `ur-rtde` not installed — `~/klippy-env/bin/pip install ur-rtde` |

### Klipper MCU errors

**Symptom:** Mainsail shows "MCU protocol error" or "Unable to connect to MCU".

**Fix:** Firmware version mismatch. Reflash the SKR Pico:
```bash
cd ~/klipper && git pull && make clean && make -j$(nproc)
SERIAL=$(ls /dev/serial/by-id/usb-Klipper_rp2040_* | head -1)
make flash FLASH_DEVICE="$SERIAL"
sudo systemctl restart klipper
```

### ur-rtde ARM build takes a long time

Building ur-rtde from C++ source on the Pi takes 10–15 minutes. This is expected. `deploy.sh` handles it automatically. If the build fails (missing Boost headers), run:

```bash
sudo apt-get install -y build-essential cmake libboost-system-dev libboost-thread-dev libboost-filesystem-dev
~/klippy-env/bin/pip install ur-rtde --no-cache-dir
```

### RTDE frequency mismatch

If the bridge connects but immediately drops, URSim may not support 500 Hz. Edit `src/bridge/config.py`:

```python
RTDE_FREQUENCY = 125    # try 125 Hz for URSim
```

### Motor doesn't move

| Symptom | Fix |
|---------|-----|
| Klipper ready but no motion | Check stepper wiring — identify coil pairs with multimeter |
| `Unable to read tmc uart` | Verify `uart_pin`/`tx_pin`/`uart_address` in `printer.cfg` |
| Motor vibrates but doesn't rotate | Swapped coil wires — swap one coil pair |
| Motor moves wrong direction | Add/remove `!` prefix on `dir_pin` in `printer.cfg` |
