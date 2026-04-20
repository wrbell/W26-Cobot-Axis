# URSim Quick-Start Runbook

Step-by-step guide for running the W26 bridge daemon against URSim on Windows.
This is the fastest path to verifying RTDE communication before hardware arrives.

**Time estimate:** ~30 minutes for first-time setup, ~2 minutes for subsequent runs.

---

## Prerequisites

- **Windows 10/11** with Docker Desktop installed (WSL2 backend)
- **Python 3.10+** with `pip` (for running the bridge daemon)
- This repo cloned on the Windows machine

### Install Python Dependencies

```powershell
cd W26-Cobot-Axis
pip install -r requirements.txt
```

> **Note:** `ur-rtde` has pre-built Windows x64 wheels on PyPI, so `pip install` should
> work without a C++ compiler. If it fails, install
> [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
> and retry.

---

## Step 1: Start URSim in Docker

Open PowerShell and run:

```powershell
docker run --rm -d `
  --name ursim `
  --platform=linux/amd64 `
  -e ROBOT_MODEL=UR30 `
  -p 30004:30004 `
  -p 29999:29999 `
  -p 6080:6080 `
  universalrobots/ursim_e-series
```

| Port  | Service |
|-------|---------|
| 30004 | RTDE (Real-Time Data Exchange) |
| 29999 | Dashboard Server (robot lifecycle) |
| 6080  | noVNC teach pendant (web browser) |

Wait ~30 seconds for the container to boot.

### Verify Container is Running

```powershell
docker ps
# Should show "ursim" container with STATUS "Up"
```

---

## Step 2: Power On the Virtual Robot

1. Open a browser to **http://localhost:6080**
2. You'll see the UR teach pendant UI
3. Click the **power button** (bottom-left) → **ON** → **START**
4. Wait for the robot status to show **Normal** (green)

> **Important:** RTDE port 30004 does not respond until the virtual robot is powered on.
> If the bridge can't connect, check this first.

---

## Step 3: Open Windows Firewall (first time only)

If running the bridge from a different machine (e.g., Pi on the network), open port 30004:

```powershell
New-NetFirewallRule -DisplayName "URSim RTDE" -Direction Inbound -LocalPort 30004 -Protocol TCP -Action Allow
```

If running the bridge on the **same Windows machine**, skip this step — `localhost` bypasses the firewall.

---

## Step 4: Find Your IP Address

If bridge and URSim are on the same machine, use `127.0.0.1`.

If on different machines:
```powershell
ipconfig
# Look for "IPv4 Address" under your active adapter (e.g., 192.168.1.50)
```

---

## Step 5: Run the Bridge Daemon

### Option A: Dry Run (RTDE only, no Klipper)

Best for verifying RTDE communication works. Skips Klipper connection entirely.

```powershell
python -m src.bridge.bridge_daemon --host 127.0.0.1 --dry-run --log-level DEBUG --no-status-poll
```

Expected output:
```
HH:MM:SS [bridge] INFO: Connecting to UR30 at 127.0.0.1:30004 ...
HH:MM:SS [bridge] INFO: RTDE connected to 127.0.0.1
HH:MM:SS [bridge] INFO: Klipper connection skipped (dry-run mode)
HH:MM:SS [bridge] INFO: Bridge started — dry-run mode, 125 Hz loop
HH:MM:SS [bridge] DEBUG: DRY RUN: mode=0 enable=False rate=0.0
```

### Option B: Dry Run with Dashboard Server

Also connects to port 29999 for robot lifecycle queries:

```powershell
python -m src.bridge.bridge_daemon --host 127.0.0.1 --dry-run --log-level DEBUG --no-status-poll --dashboard
```

### Option C: Dry Run with CSV Logging

Captures telemetry to CSV for later analysis:

```powershell
python -m src.bridge.bridge_daemon --host 127.0.0.1 --dry-run --log-level DEBUG --no-status-poll --log
```

CSV files go to `./logs/` (or specify `--log-dir path`).

### CLI Flags Reference

| Flag | Effect |
|------|--------|
| `--host IP` | UR30/URSim IP address (default: 192.168.1.100) |
| `--dry-run` | Skip Klipper connection, log commands instead of executing |
| `--no-status-poll` | Disable TMC2209/StallGuard queries (no SKR Pico connected) |
| `--no-watchdog` | Disable RTDE timestamp watchdog |
| `--no-sg-accumulator` | Disable StallGuard history buffer |
| `--dashboard` | Enable Dashboard Server on port 29999 |
| `--log` | Enable CSV telemetry logging |
| `--log-level DEBUG` | Verbose output (DEBUG, INFO, WARNING, ERROR) |

---

## Step 6: Test RTDE Register Communication

While the bridge is running in dry-run mode, go to the noVNC teach pendant (http://localhost:6080) and load a URScript program that writes to the output registers the bridge reads.

### Quick Register Test from Python

In a separate terminal, run this test script to verify register read/write independently. Save it as `test_ursim_rtde.py` on the Windows host (URSim binds its RTDE server to `127.0.0.1` inside the container; with the `-p 30004:30004` port mapping, `127.0.0.1` on the host also works). Install `ur_rtde` first if you do not have it:

```bash
pip install ur_rtde     # or see DEVELOPMENT.md for the macOS/Linux build notes
python test_ursim_rtde.py
```

```python
# test_ursim_rtde.py — standalone RTDE connectivity test
import rtde_receive
import rtde_control
import time  # reserved for future timing loops

HOST = "127.0.0.1"

print(f"Connecting to {HOST}:30004 ...")
rtde_r = rtde_receive.RTDEReceiveInterface(HOST)
rtde_c = rtde_control.RTDEControlInterface(HOST)
print("Connected!")

# Read robot state
mode = rtde_r.getRobotMode()
print(f"Robot mode: {mode} (7 = RUNNING)")

tcp_speed = rtde_r.getActualTCPSpeed()
print(f"TCP speed: {tcp_speed}")

# Read output registers (these are what URScript writes)
try:
    int_reg = rtde_r.getOutputIntRegister(0)
    print(f"output_int_register_0 (mode): {int_reg}")
except Exception as e:
    print(f"Register read failed (expected if no URScript running): {e}")

# Write input registers (these are what the bridge writes back to UR)
try:
    rtde_c.setInputIntRegister(0, 0)       # status = IDLE
    rtde_c.setInputIntRegister(1, 0)       # error = NONE
    rtde_c.setInputDoubleRegister(0, 0.0)  # actual_rate
    rtde_c.setInputBitRegister(64, True)   # ready = True
    rtde_c.setInputBitRegister(65, False)  # fault = False
    print("Input registers written successfully")
except Exception as e:
    print(f"Register write failed: {e}")

rtde_r.disconnect()
rtde_c.disconnect()
print("Done.")
```

Run it:
```powershell
python test_ursim_rtde.py
```

---

## Step 7: Load and Test URScript Programs

### Load the Slicer Output

1. Copy `src/provided/Mblack0.6mm.script` to the URSim programs directory:
   ```powershell
   docker cp src/provided/Mblack0.6mm.script ursim:/ursim/programs/
   ```

2. In the noVNC teach pendant, go to **Program** tab → **Load Program** → select `Mblack0.6mm`

3. Press **Play** and watch the 3D view — verify the 776-waypoint path looks correct (no joint limit errors, no singularities)

### Load the Extrusion Control Library

```powershell
docker cp src/urscript/extrusion_control.script ursim:/ursim/programs/
docker cp src/urscript/test_basic.script ursim:/ursim/programs/
```

Load `test_basic` in the teach pendant and run Sub-tests A through F and I (these don't require taught waypoints or real hardware).

---

## Troubleshooting

### Bridge can't connect to URSim

| Symptom | Fix |
|---------|-----|
| `Connection refused` | Robot not powered on in noVNC UI — click power → ON → START |
| `Connection timed out` | Wrong IP address, or firewall blocking port 30004 |
| `ur_rtde not installed` | `pip install ur-rtde` (Windows x64 wheel available) |
| Bridge runs but shows stub mode | `ur_rtde` import failed — check `pip list \| findstr ur` |

### RTDE frequency mismatch

If the connection drops immediately after connecting, URSim may not support 500 Hz.
Edit `src/bridge/config.py` line 13:

```python
RTDE_FREQUENCY = 125    # try 125 Hz for URSim
```

Or pass a custom frequency (if we add the CLI flag later).

### Docker issues

| Symptom | Fix |
|---------|-----|
| `no matching manifest for linux/amd64` | Enable WSL2 backend in Docker Desktop settings |
| Container exits immediately | Check logs: `docker logs ursim` |
| noVNC shows blank screen | Wait longer (~60s), or try `docker restart ursim` |
| Port already in use | `docker stop ursim` first, or change port mapping |

### Register read returns unexpected values

- Output registers (UR → Pi) are **only written by URScript**. If no URScript program
  is running, registers contain default/stale values.
- Input registers (Pi → UR) are written by the bridge. Check bridge logs for
  `Failed to write RTDE status` errors.

---

## Stopping URSim

```powershell
docker stop ursim
```

The `--rm` flag means the container is automatically removed on stop. Your loaded
programs will be lost — re-copy them next time, or remove `--rm` and use
`docker start ursim` to resume.

To persist programs across restarts, mount a volume:

```powershell
docker run --rm -d `
  --name ursim `
  --platform=linux/amd64 `
  -e ROBOT_MODEL=UR30 `
  -p 30004:30004 `
  -p 29999:29999 `
  -p 6080:6080 `
  -v ${PWD}/ursim_programs:/ursim/programs `
  universalrobots/ursim_e-series
```

---

## What to Verify Tomorrow

Minimum success criteria for the URSim session:

1. URSim container starts, robot powers on in noVNC
2. Bridge connects to RTDE on port 30004 (`RTDE connected to ...` in logs)
3. Bridge reads output registers (mode, rate, enable — all zeros is fine)
4. Bridge writes input registers (status=IDLE, ready=True)
5. `Mblack0.6mm.script` plays in URSim without errors (776 waypoints)

Stretch goals:
- Dashboard Server queries work (`--dashboard` flag)
- CSV log captures register values during slicer playback
- `test_basic.script` Sub-tests A–F pass with bridge running
