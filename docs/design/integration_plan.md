# Phase 3 Integration Plan

**W26 Cobot Axis -- ME472 Mechatronics Capstone**
**Phase 3: Build and Additional Design/Analysis (Weeks 9--11, Mar 2--22, 2026)**
**Author:** Willem (Software/EE)
**Date:** 2026-02-12

---

## Overview

This document defines the step-by-step hardware bring-up sequence for Phase 3. The goal is to establish a working end-to-end signal chain from the UR30 controller through the Raspberry Pi and SKR Pico to the stepper motor by March 22.

Week 9 (Mar 2--8) is Spring Break -- dedicated build time with no classes. Weeks 10--11 overlap with labs, so integration work must fit around scheduled lab sessions.

**Critical path:** Stage 1 through Stage 3 must succeed before any other stage can begin. Stages 4--8 have some parallelism but generally follow the order listed.

```
Stage 1: Klipper on Pi               (Week 9, Day 1)
  |
Stage 2: SKR Pico firmware            (Week 9, Day 1--2)
  |
Stage 3: Stepper motion               (Week 9, Day 2--3)
  |
  +-----> Stage 4: TMC2209 tuning     (Week 9, Day 3--4)
  |
  +-----> Stage 5: Bridge daemon      (Week 9, Day 4--5)
              |
              +-----> Stage 6: RTDE connection   (Week 10)
                          |
                          +-----> Stage 7: End-to-end   (Week 10--11)
                                      |
                                      +-----> Stage 8: Pi400 HMI   (Week 11, parallel)
```

**Assumed hardware on hand at start of Phase 3:**
- Raspberry Pi (model TBD, headless) with SD card and 5.1V power supply
- BigTreeTech SKR Pico V1.0 (RP2040, 4x TMC2209 onboard)
- Stepper motor + pump (provided by course, specs TBD)
- 24V power supply (from UR controller power block or bench supply for lab testing)
- USB-C cable (Pi to SKR Pico)
- Ethernet cable + gigabit switch (Pi to UR30)
- Raspberry Pi 400 (HMI/dev terminal)
- Multimeter, oscilloscope (lab equipment)

---

## Stage 1: Klipper on Pi

**Goal:** A headless Raspberry Pi running Klipper (klippy) and Moonraker, accessible via SSH.

**Estimated time:** 2--3 hours

**Prerequisites:**
- Raspberry Pi with a MicroSD card (32 GB minimum)
- 5.1V / 3A power supply for Pi
- Ethernet cable and network with DHCP (or keyboard + monitor for initial WiFi config)
- A workstation with an SD card writer (Pi400 works for this)

### Action

1. **Flash MainsailOS** onto the SD card using Raspberry Pi Imager.
   - MainsailOS bundles Raspberry Pi OS Lite + Klipper + Moonraker + Mainsail in a single image.
   - In Imager advanced settings: enable SSH with password authentication, set hostname to `w26-pi`, configure WiFi if no ethernet available, set locale to `en_US.UTF-8`.
   - Alternative: flash Raspberry Pi OS Lite and install Klipper manually using KIAUH (`https://github.com/dw-0/kiauh`). This gives more control but takes longer.

2. **Boot the Pi** with the flashed SD card. Connect ethernet. Wait 60--90 seconds for first-boot setup.

3. **SSH into the Pi** from the Pi400 (or any machine on the same network):
   ```
   ssh pi@w26-pi.local
   ```
   If mDNS does not resolve, check the router's DHCP lease table for the Pi's IP address and SSH by IP.

4. **Verify Klipper is installed:**
   ```
   systemctl status klipper
   systemctl status moonraker
   ```
   Both services should be `loaded` but may show errors because there is no `printer.cfg` yet. That is expected.

5. **Update the system** (only if internet is available):
   ```
   sudo apt update && sudo apt upgrade -y
   ```

6. **Verify the klippy Unix socket path exists** (it will appear once Klipper starts with a valid config):
   ```
   ls -la /tmp/klippy_uds
   ```
   This file will not exist yet -- that is expected until Stage 2 provides a valid MCU connection.

### Verification

- SSH access works: `ssh pi@w26-pi.local` connects.
- `klipper` service is loaded: `systemctl is-enabled klipper` returns `enabled`.
- `moonraker` service is loaded: `systemctl is-enabled moonraker` returns `enabled`.
- Mainsail web UI responds (even if showing errors): `http://w26-pi.local` loads in a browser from the Pi400.

### Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Cannot SSH | Pi did not boot, wrong hostname, no network | Connect monitor + keyboard. Check `/boot/ssh` file exists. Check ethernet cable. Try `ssh pi@<IP>`. |
| mDNS not resolving | Avahi not running or network issue | Use IP address directly. Install `avahi-daemon` if missing. |
| Klipper service not found | MainsailOS image was not used | Install Klipper manually via KIAUH: `cd ~ && git clone https://github.com/dw-0/kiauh.git && ./kiauh/kiauh.sh` |
| Moonraker 502 error in browser | Klipper not started (no printer.cfg) | Expected at this stage. Will resolve after Stage 2. |

### Rollback

If the SD card image is bad or the Pi will not boot, re-flash the SD card. There is nothing to lose at this stage.

### Tools/Equipment

- SD card reader/writer
- Ethernet cable
- Monitor + keyboard (fallback if SSH fails)
- Pi400 or laptop on the same network for SSH

---

## Stage 2: SKR Pico Firmware

**Goal:** Klipper MCU firmware compiled, flashed onto the SKR Pico via UF2, and the board enumerated as a USB serial device on the Pi.

**Estimated time:** 1--2 hours

**Prerequisites:**
- Stage 1 complete (Pi accessible via SSH, Klipper installed)
- SKR Pico V1.0 board
- USB-C cable
- 24V power supply connected to SKR Pico VIN (or USB power alone for flashing -- USB power is sufficient for the RP2040 but the TMC2209 drivers will not initialize without VIN)

### Action

1. **SSH into the Pi** and build the Klipper MCU firmware:
   ```
   cd ~/klipper
   make menuconfig
   ```

   Select the following settings:
   ```
   Micro-controller Architecture: Raspberry Pi RP2040
   Bootloader offset:             No bootloader
   Flash chip:                    W25Q080 with CLKDIV 2
   Communication interface:       USB
   ```

   The flash chip setting `W25Q080 with CLKDIV 2` is compatible with the W25Q16 chip on the SKR Pico despite the name mismatch. Selecting the wrong flash chip will produce non-booting firmware.

   Save and exit, then build:
   ```
   make clean
   make
   ```

   This produces `~/klipper/out/klipper.uf2`.

2. **Enter BOOTSEL mode on the SKR Pico:**
   - Disconnect USB from the Pi.
   - Press and hold the `BOOTSEL` button on the SKR Pico.
   - While holding, plug the USB-C cable into the Pi.
   - Release `BOOTSEL` after 1--2 seconds.
   - The RP2040 should enumerate as a USB mass storage device named `RPI-RP2`.

3. **Copy the firmware:**
   ```
   sudo mount /dev/sda1 /mnt
   sudo cp ~/klipper/out/klipper.uf2 /mnt/
   sudo sync
   sudo umount /mnt
   ```

   The board will automatically reboot into Klipper firmware after the UF2 is written. The USB mass storage device will disappear.

4. **Verify USB serial enumeration:**
   ```
   ls /dev/serial/by-id/
   ```

   Expected output (the hex string will vary):
   ```
   usb-Klipper_rp2040_E66094A027831922-if00
   ```

   **Record this full path.** It will be needed for `printer.cfg`.

5. **Deploy `printer.cfg`** from the repository to the Pi:
   ```
   cp ~/W26-Cobot-Axis/src/klipper/printer.cfg ~/printer_data/config/printer.cfg
   ```

   Edit the `[mcu]` serial line to match the actual device path from step 4:
   ```
   nano ~/printer_data/config/printer.cfg
   ```
   Replace `usb-Klipper_rp2040_PLACEHOLDER-if00` with the actual serial ID.

6. **Restart Klipper:**
   ```
   sudo systemctl restart klipper
   ```

7. **Check Klipper logs for successful MCU connection:**
   ```
   cat /tmp/klippy.log | tail -50
   ```

   Look for lines like:
   ```
   Loaded MCU 'mcu' ... rp2040
   MCU 'mcu' config: ...
   Printer is ready
   ```

### Verification

- `ls /dev/serial/by-id/` shows a `usb-Klipper_rp2040_*` entry.
- `systemctl status klipper` shows `active (running)` with no errors.
- `/tmp/klippy.log` contains `Printer is ready`.
- `/tmp/klippy_uds` exists: `ls -la /tmp/klippy_uds`.
- Mainsail web UI at `http://w26-pi.local` shows "Ready" status (green).

### Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| No `RPI-RP2` drive appears | BOOTSEL not held during plug-in | Unplug USB. Try again, holding BOOTSEL firmly before and during plug-in. |
| `/dev/sda1` does not appear | Pi kernel did not detect USB mass storage | Try `lsblk` to find the correct device node. May be `/dev/sdb1`. |
| No `/dev/serial/by-id/` entry after flash | Firmware did not flash correctly, or wrong menuconfig settings | Re-enter BOOTSEL mode and re-flash. Double-check menuconfig: RP2040, no bootloader, W25Q080, USB. |
| `MCU protocol error` in klippy.log | Klipper host and MCU firmware version mismatch | Rebuild firmware from the same Klipper commit as the host: `cd ~/klipper && git pull && make clean && make`, then re-flash. |
| `Unable to connect to MCU` | Wrong serial path in printer.cfg | Run `ls /dev/serial/by-id/` and copy the exact path into printer.cfg. |
| `Unable to read tmc uart` errors | 24V not connected to SKR Pico VIN | TMC2209 UART requires VIN power. Connect 24V to the SKR Pico power input. |

### Rollback

If firmware flash fails, the RP2040 can always re-enter BOOTSEL mode. There is no way to brick an RP2040 through firmware -- the UF2 bootloader is in ROM.

### Tools/Equipment

- USB-C cable
- SSH terminal (from Pi400)
- 24V power supply (for TMC2209 UART -- can defer to Stage 3 if only testing USB enumeration)

---

## Stage 3: Stepper Motion

**Goal:** Send a G-code command from the Pi; the stepper motor physically turns.

**Estimated time:** 1--2 hours

**Prerequisites:**
- Stage 2 complete (Klipper "Printer is ready", MCU connected)
- Stepper motor wired to the SKR Pico E-axis driver socket (4-pin JST connector: coil A+, A-, B+, B-)
- 24V power supply connected to SKR Pico VIN and GND

### Action

1. **Wire the stepper motor** to the SKR Pico E-axis motor connector.
   - Identify the motor coil pairs using a multimeter (resistance mode). Coil A and coil B each show a few ohms between their pair; no continuity between coils.
   - Connect coil A to pins 1--2 and coil B to pins 3--4 of the E-motor connector. If the motor runs backwards, swap one coil pair.
   - Do NOT connect 24V yet.

2. **Apply 24V power** to the SKR Pico VIN/GND screw terminals.
   - Verify polarity with a multimeter before connecting.
   - Verify the power LED on the SKR Pico lights up.

3. **Verify Klipper is still ready** (24V may have caused a reset):
   ```
   systemctl status klipper
   ```

4. **Send test G-code commands** via the Klipper console (Mainsail web UI or SSH):

   Via Mainsail: navigate to `http://w26-pi.local`, open the Console tab, and type:
   ```
   MANUAL_STEPPER STEPPER=pump ENABLE=1
   MANUAL_STEPPER STEPPER=pump SET_POSITION=0
   MANUAL_STEPPER STEPPER=pump MOVE=10 SPEED=5
   ```

   Via SSH (using the klippy virtual console):
   ```
   ~/moonraker/scripts/moonraker.py  # ensure moonraker is running
   curl -s -X POST "http://localhost:7125/printer/gcode/script?script=MANUAL_STEPPER%20STEPPER%3Dpump%20ENABLE%3D1"
   curl -s -X POST "http://localhost:7125/printer/gcode/script?script=MANUAL_STEPPER%20STEPPER%3Dpump%20SET_POSITION%3D0"
   curl -s -X POST "http://localhost:7125/printer/gcode/script?script=MANUAL_STEPPER%20STEPPER%3Dpump%20MOVE%3D10%20SPEED%3D5"
   ```

5. **Observe the motor.** It should rotate smoothly for 10mm of travel at 5 mm/s. With `rotation_distance: 40`, that is 0.25 revolutions (90 degrees).

6. **Test reverse direction:**
   ```
   MANUAL_STEPPER STEPPER=pump MOVE=-10 SPEED=5
   ```

7. **Test different speeds:**
   ```
   MANUAL_STEPPER STEPPER=pump MOVE=40 SPEED=25
   MANUAL_STEPPER STEPPER=pump MOVE=80 SPEED=50
   ```

8. **Disable the stepper when done:**
   ```
   MANUAL_STEPPER STEPPER=pump ENABLE=0
   ```

### Verification

- Motor physically rotates when MOVE command is sent.
- Motor direction matches the sign of the MOVE distance (positive = extrude direction, negative = retract). If reversed, add or remove `!` from `dir_pin: gpio13` in printer.cfg and restart Klipper.
- Motor stops cleanly when ENABLE=0 is sent (shaft becomes free-spinning).
- No `Unable to read tmc uart` errors in klippy.log.
- Motor runs quietly (StealthChop should be near-silent at low speeds).

### Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Motor does not move | Wrong wiring, no 24V, wrong pin mapping | Check wiring with multimeter. Verify 24V at VIN. Confirm `step_pin`, `dir_pin`, `enable_pin` match E-axis on SKR Pico. |
| Motor vibrates but does not rotate | Coil pairs swapped | Swap one coil pair (A+ with A-, or swap A and B). |
| Motor direction reversed | Dir pin polarity | Add `!` prefix to `dir_pin` in printer.cfg: `dir_pin: !gpio13`. Restart Klipper. |
| Motor is very loud/rough | StealthChop not active, or motor current too low | Check `stealthchop_threshold: 999999` is set. Increase `run_current` in small increments (0.1A steps). |
| `Move exceeds maximum` error | Move distance exceeds Klipper safety limits | This should not happen with `[manual_stepper]` unless firmware has kinematic limits. Check `velocity` and `accel` settings in printer.cfg. |
| Klipper goes into shutdown after move | Thermal fault or MCU communication timeout | Check klippy.log for the specific error. If MCU timeout, check USB cable quality. |

### Rollback

If the motor does not work, power off 24V, disconnect the motor, and return to Stage 2 verification. The stepper motor cannot be damaged by incorrect wiring to the TMC2209 (the driver has overcurrent protection), but the driver can overheat if run at excessive current without cooling.

### Tools/Equipment

- Multimeter (for coil identification and voltage verification)
- 24V power supply (bench supply or UR controller power block)
- Stepper motor + cable
- Small screwdriver (for SKR Pico screw terminals)

---

## Stage 4: TMC2209 Tuning

**Goal:** Set motor current to match the actual motor's rating, verify thermal behavior, and confirm StealthChop/SpreadCycle operation.

**Estimated time:** 1--2 hours (plus thermal soak time)

**Prerequisites:**
- Stage 3 complete (motor moves on command)
- Motor nameplate data (rated current, step angle) -- read from the motor label or datasheet
- Infrared thermometer or thermocouple (optional but recommended)

### Action

1. **Read the motor's rated current** from the nameplate or datasheet. Record it.
   - Typical NEMA 17 steppers: 0.5A to 2.0A per phase.
   - The TMC2209 on the SKR Pico can deliver up to ~1.2A RMS continuously (thermally limited by the PCB).

2. **Set `run_current`** in `printer.cfg` to 70--80% of the motor's rated current as a starting point:
   ```
   [tmc2209 manual_stepper pump]
   run_current: <value>
   ```

   For example, if the motor is rated at 1.0A/phase, start with `run_current: 0.700`.

3. **Set `hold_current`** to 50--70% of `run_current`:
   ```
   hold_current: <value>
   ```

4. **Restart Klipper** after editing printer.cfg:
   ```
   sudo systemctl restart klipper
   ```

5. **Run a sustained motion test** to check thermals:
   ```
   MANUAL_STEPPER STEPPER=pump ENABLE=1
   MANUAL_STEPPER STEPPER=pump MOVE=1000 SPEED=25
   ```
   This will run the motor for ~40 seconds at moderate speed.

6. **Monitor TMC2209 driver temperature** during the test:
   - Touch the TMC2209 chip on the SKR Pico (carefully -- it may be hot). It should not be too hot to touch (< 70 C on the package).
   - If available, use an infrared thermometer. Target: driver package temperature below 80 C.
   - Query the MCU temperature: `curl "http://localhost:7125/printer/objects/query?temperature_sensor%20mcu_temp"`

7. **Test StealthChop vs SpreadCycle:**
   - Current config has `stealthchop_threshold: 999999` (StealthChop always on -- quiet mode).
   - Run the motor at various speeds (5, 25, 50 mm/s) and listen. StealthChop should be near-silent at low speeds.
   - If the pump requires higher torque at speed, test SpreadCycle by setting `stealthchop_threshold: 0`:
     ```
     [tmc2209 manual_stepper pump]
     stealthchop_threshold: 0
     ```
   - SpreadCycle is louder but provides more torque at higher speeds.

8. **If the motor stalls** (misses steps, vibrates, or stops mid-move):
   - Increase `run_current` by 0.1A increments.
   - Re-test after each increase.
   - Do not exceed the motor's rated current or 1.2A (whichever is lower).

9. **Finalize current settings** and commit the updated printer.cfg back to the repository.

### Verification

- Motor runs at target speed without stalling under expected pump load.
- TMC2209 driver temperature stays below 80 C during sustained operation.
- No `Unable to read tmc uart` errors (UART errors can occur when the driver overheats).
- `DUMP_TMC STEPPER="manual_stepper pump"` shows driver status without error flags (run via Mainsail console).

### Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Motor stalls at low current | Current too low for pump load | Increase `run_current` by 0.1A. If already at motor rating, the motor may be undersized. |
| TMC2209 overheating (> 100 C) | Current too high, no cooling | Reduce `run_current`. Enable the onboard fan by uncommenting `[fan]` section in printer.cfg with `pin: gpio17`. |
| Motor resonance at certain speeds | Stepper resonance near natural frequency | Change microstep setting (try 32 or 64). Adjust acceleration. SpreadCycle handles resonance better than StealthChop. |
| UART read errors during operation | Thermal shutdown or bus noise | Reduce current. Check wiring. Ensure 24V supply is clean (measure with oscilloscope for ripple). |

### Rollback

If tuning causes problems, revert `run_current` to the conservative default (0.580A) and `stealthchop_threshold` to 999999. The printer.cfg from the repo is the known-good baseline.

### Tools/Equipment

- Infrared thermometer or thermocouple (recommended)
- Multimeter
- Oscilloscope (if diagnosing power supply ripple or step timing)
- Motor datasheet or nameplate

---

## Stage 5: Bridge Daemon

**Goal:** The Python bridge daemon runs on the Pi, connects to Klipper via the Unix socket, and can command the stepper.

**Estimated time:** 1--2 hours

**Prerequisites:**
- Stage 3 complete (stepper moves via manual G-code)
- Bridge daemon source code from `src/bridge/` in the repository
- Python 3.11+ on the Pi (included with Raspberry Pi OS)

### Action

1. **Clone the repository onto the Pi** (or copy `src/bridge/` via SCP):
   ```
   cd ~
   git clone <repo-url> W26-Cobot-Axis
   ```

   Or from the Pi400:
   ```
   scp -r ~/W26-Cobot-Axis/src pi@w26-pi.local:~/W26-Cobot-Axis/src
   ```

2. **Install Python dependencies:**
   ```
   cd ~/W26-Cobot-Axis
   pip3 install ur-rtde
   ```

   Note: `ur-rtde` has C++ dependencies. If installation fails:
   ```
   sudo apt install -y python3-pip build-essential libboost-all-dev
   pip3 install ur-rtde
   ```

   If `ur-rtde` cannot be installed (missing dependencies, cross-compilation issues on ARM), the bridge daemon's `rtde_client.py` includes a stub fallback mode that works without the library. This is sufficient for Stages 5 testing.

3. **Test the bridge daemon in dry-run mode** (no RTDE connection, no Klipper commands -- just verifies the code runs):
   ```
   cd ~/W26-Cobot-Axis
   python3 -m src.bridge.bridge_daemon --dry-run --log-level DEBUG
   ```

   Expected output: the bridge starts its main loop, logs `DRY RUN: ...` messages, and runs until Ctrl+C.

   If import errors occur, check that the package structure is correct (`src/bridge/__init__.py` exists, `src/bridge/__main__.py` exists).

4. **Test bridge daemon connected to Klipper** (no RTDE yet):
   - Edit the bridge to skip RTDE connection temporarily, or use the `--dry-run` flag which only skips Klipper commands (check the actual `--dry-run` behavior in bridge_daemon.py -- it skips Klipper writes but still attempts RTDE connection).
   - For isolated Klipper testing, write a quick test script:
     ```python
     # ~/test_klipper.py
     import sys
     sys.path.insert(0, '/root/W26-Cobot-Axis/src')
     from bridge.klipper_client import KlipperClient

     k = KlipperClient("/tmp/klippy_uds")
     k.connect()
     print("Info:", k.get_info())
     print("Move:", k.stepper_move("pump", 5.0, 10.0))
     k.stepper_disable("pump")
     k.disconnect()
     ```

   Run it:
   ```
   python3 ~/test_klipper.py
   ```

   The motor should move 5mm at 10 mm/s, then disable.

5. **Verify the bridge daemon's command translation** by reviewing the log output at DEBUG level. Confirm that RTDE register reads translate to the correct `MANUAL_STEPPER` G-code commands.

### Verification

- `python3 -m src.bridge.bridge_daemon --dry-run` runs without import errors or crashes.
- `test_klipper.py` connects to klippy, moves the stepper, and disconnects cleanly.
- Klippy log shows the G-code commands arriving from the bridge.

### Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: bridge` | Wrong working directory or package structure | Run from the repo root: `cd ~/W26-Cobot-Axis && python3 -m src.bridge.bridge_daemon`. Ensure `__init__.py` exists in `src/bridge/`. |
| `ConnectionError: Cannot connect to klippy` | Klipper not running or socket path wrong | Check `systemctl status klipper`. Verify `/tmp/klippy_uds` exists. |
| `ur-rtde` installation fails | Missing build dependencies on ARM | Install `libboost-all-dev`, `cmake`, `build-essential`. Alternatively, test with stub mode. |
| Bridge connects but motor does not move | Stepper name mismatch | Verify `STEPPER_NAME = "pump"` in config.py matches `[manual_stepper pump]` in printer.cfg. |
| `TimeoutError: Timed out waiting for klippy response` | Klipper busy or in error state | Check klippy.log. Restart Klipper. Ensure printer.cfg is valid. |

### Rollback

The bridge daemon is pure software. If it causes issues, stop it with Ctrl+C or `kill`. It cannot damage hardware. If the daemon left the stepper in an unknown state, send:
```
MANUAL_STEPPER STEPPER=pump ENABLE=0
```
via Mainsail console.

### Tools/Equipment

- SSH terminal
- Text editor (nano, vim)
- No physical tools needed

---

## Stage 6: RTDE Connection

**Goal:** The bridge daemon connects to the UR30 controller via RTDE, reads output registers, and writes input registers.

**Estimated time:** 2--3 hours

**Prerequisites:**
- Stage 5 complete (bridge daemon runs and connects to Klipper)
- UR30 controller powered on and in Remote Mode
- Ethernet connectivity between Pi and UR30 (via gigabit switch)
- IP addresses configured: UR30 at a known static IP, Pi on the same subnet
- URScript program `extrusion_control.script` loaded on the UR30 teach pendant (from `src/urscript/`)

### Action

1. **Verify network connectivity** between the Pi and the UR30:
   ```
   ping <UR30_IP>
   ```
   If this fails, check ethernet cables, switch, and IP configuration. The UR30's IP is configured on the teach pendant under Settings > Network.

2. **Verify RTDE port is reachable:**
   ```
   nc -zv <UR30_IP> 30004
   ```
   Expected: `Connection to <UR30_IP> 30004 port [tcp/*] succeeded!`

   If this fails, the UR30 may not be in the correct mode. RTDE is available on port 30004 in all modes (Local, Remote), but the robot program must be running for output registers to have values.

3. **Update `config.py`** with the UR30's actual IP address:
   ```python
   UR30_HOST = "<actual_UR30_IP>"
   ```

4. **Test RTDE connection independently** before running the full bridge:
   ```python
   # ~/test_rtde.py
   import rtde_receive
   import rtde_control

   rtde_r = rtde_receive.RTDEReceiveInterface("<UR30_IP>")
   print("Robot mode:", rtde_r.getRobotMode())
   print("Safety mode:", rtde_r.getSafetyMode())

   # Read output registers (written by URScript)
   print("output_int_register_0:", rtde_r.getOutputIntRegister(0))
   print("output_double_register_0:", rtde_r.getOutputDoubleRegister(0))
   print("output_bit_register_64:", rtde_r.getOutputBitRegister(64))

   rtde_r.disconnect()
   ```

   Run this while a URScript program is running on the UR30 (even a minimal one that writes to the output registers).

5. **Test writing input registers** (Pi to UR30):
   ```python
   import rtde_control

   rtde_c = rtde_control.RTDEControlInterface("<UR30_IP>")
   rtde_c.setInputIntRegister(0, 0)    # status = idle
   rtde_c.setInputDoubleRegister(0, 0.0)  # actual_rate = 0
   rtde_c.setInputBitRegister(64, True)   # ready = true
   rtde_c.disconnect()
   ```

   On the UR30 teach pendant, check the variable values in the URScript program to confirm the registers arrived.

6. **Load the URScript extrusion program** onto the UR30:
   - Copy `src/urscript/extrusion_control.script` to a USB drive.
   - Load it via the teach pendant (Program > Load).
   - Alternatively, use the UR30 SSH interface or Dashboard Server (port 29999) to load the program.

7. **Run the bridge daemon with RTDE** (no dry-run):
   ```
   cd ~/W26-Cobot-Axis
   python3 -m src.bridge.bridge_daemon --host <UR30_IP> --log-level DEBUG
   ```

   Start the URScript program on the UR30 teach pendant. The bridge should log register reads and Klipper command sends.

### Verification

- `ping <UR30_IP>` succeeds with < 1ms latency on a local network.
- `test_rtde.py` reads valid register values from the UR30.
- Bridge daemon logs show RTDE read/write cycles at the configured loop rate (125 Hz).
- UR30 teach pendant shows input register values written by the bridge (status, ready flag).

### Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| `ping` fails | Wrong IP, cable unplugged, switch issue | Check cables. Verify IPs are on the same subnet. Try different switch port. |
| RTDE connection refused | UR30 not running or firewall | Ensure UR30 is powered on. RTDE (port 30004) should always be available. Check UR30 firmware version -- RTDE requires e-Series or CB3 with firmware >= 3.3. |
| Register values are all zero | URScript program not running | Start the URScript program on the teach pendant. Registers only have values when a program writes to them. |
| `ur-rtde` crashes with segfault | Library version mismatch or ARM compatibility | Try `pip3 install ur-rtde==1.5.6` (specific version). If persistent, use the UR Python RTDE client as fallback. |
| Bridge disconnects repeatedly | RTDE frequency too high or network jitter | Reduce `RTDE_FREQUENCY` in config.py to 125 Hz. Check network for packet loss: `ping -c 100 <UR30_IP>`. |
| UR30 shows `RTDE synchronization error` | Clock drift or register config mismatch | Restart the URScript program. Verify register names in config.py match the RTDE recipe setup in rtde_client.py. |

### Rollback

If RTDE issues destabilize the UR30 (unlikely but possible), stop the bridge daemon, and press the physical E-stop on the UR30 if needed. RTDE is read-only for safety-critical state -- the bridge cannot command robot arm motion.

### Tools/Equipment

- Ethernet cable and gigabit switch
- UR30 teach pendant (for URScript loading and monitoring)
- USB drive (for URScript file transfer, if needed)
- Network diagnostic tools: `ping`, `nc`, `tcpdump`

---

## Stage 7: End-to-End

**Goal:** UR30 sends an extrude command via RTDE; the stepper motor moves at the requested speed. Verify the full communication chain: UR30 --> RTDE --> Pi (bridge daemon) --> Klipper --> SKR Pico --> stepper.

**Estimated time:** 2--4 hours (includes latency characterization)

**Prerequisites:**
- Stage 6 complete (RTDE connected, bridge daemon running)
- Stage 3/4 complete (stepper motor verified and tuned)
- URScript extrusion program loaded and ready
- All hardware powered and connected

### Action

1. **Start all services** on the Pi:
   ```
   sudo systemctl start klipper
   sudo systemctl start moonraker
   ```

   Start the bridge daemon:
   ```
   cd ~/W26-Cobot-Axis
   python3 -m src.bridge.bridge_daemon --host <UR30_IP> --log-level INFO
   ```

2. **Run a simple URScript test** on the UR30 that writes extrusion commands:
   - Set mode = 1 (extrude): `write_output_integer_register(0, 1)`
   - Set rate = 10.0 mm/s: `write_output_float_register(0, 10.0)`
   - Set enable = True: `write_output_boolean_register(64, True)`

   The stepper should begin moving at 10 mm/s.

3. **Verify stepper responds** by observing physical motion. Count rotations or use a marker on the shaft to estimate speed.

4. **Test speed changes:** Have the URScript program ramp the extrusion rate from 0 to 50 mm/s over several seconds. Observe that the stepper smoothly accelerates.

5. **Test stop command:**
   - Set mode = 0 (off): `write_output_integer_register(0, 0)`
   - The stepper should decelerate and stop.

6. **Test retract:**
   - Set mode = 2 (retract) with a rate of 10.0 mm/s.
   - The stepper should run in the reverse direction.

7. **Test emergency stop:**
   - Set estop = True: `write_output_boolean_register(65, True)`
   - The stepper should immediately halt (Klipper emergency stop).
   - After E-stop, Klipper will be in a shutdown state. The bridge daemon should detect this and log an error. A firmware restart is required to recover:
     ```
     curl -X POST "http://localhost:7125/printer/firmware_restart"
     ```

8. **Verify status feedback** on the UR30 side:
   - Read `input_int_register_0` (status) -- should show 1 (running) during extrusion, 0 (idle) when stopped.
   - Read `input_double_register_0` (actual_rate) -- should approximate the commanded rate.
   - Read `input_bit_register_64` (ready) -- should be True when the bridge is connected and Klipper is ready.

9. **Measure end-to-end latency** (if oscilloscope is available):
   - Connect oscilloscope Channel 1 to a UR30 digital output that toggles when the extrude command is sent.
   - Connect Channel 2 to the SKR Pico step pin (gpio14).
   - Measure the time between the UR30 output toggle and the first step pulse.
   - Expected: 5--20ms (dominated by RTDE cycle time + Klipper buffer).

10. **Run under robot motion** (the real use case):
    - Create a UR30 program that moves the robot arm in a straight line while commanding extrusion.
    - Verify that extrusion starts/stops in sync with arm motion within acceptable tolerances.

### Verification

- Stepper moves when UR30 commands extrude.
- Stepper stops when UR30 commands stop.
- Stepper reverses when UR30 commands retract.
- Emergency stop halts the stepper immediately.
- Status registers on the UR30 reflect the actual stepper state.
- End-to-end latency is within the 5--20ms target (if measured).

### Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Stepper does not respond to UR30 commands | Bridge not translating commands, register mapping error | Check bridge logs. Verify register names match between config.py, rtde_client.py, and the URScript program. |
| Stepper moves but at wrong speed | Extrusion multiplier wrong, `rotation_distance` wrong | Check `EXTRUSION_MULTIPLIER` in config.py. Verify `rotation_distance` in printer.cfg matches the pump's mechanical ratio. |
| Latency exceeds 50ms | Network delay, bridge loop rate too low, Klipper buffer | Check `LOOP_HZ` in config.py (should be 125). Check RTDE frequency. Profile bridge loop time at DEBUG level. |
| Stepper stutters or moves in bursts | Bridge sending moves faster than Klipper processes them | Reduce bridge loop rate. Increase Klipper `velocity` and `accel` limits. Check for Klipper `Move queue overflow` errors. |
| E-stop does not recover | Klipper in permanent shutdown | Must issue `FIRMWARE_RESTART` via Moonraker API or Mainsail. This is by design -- E-stop requires deliberate recovery. |

### Rollback

If the end-to-end test causes unexpected behavior, stop the bridge daemon (Ctrl+C), disable the stepper via Mainsail (`MANUAL_STEPPER STEPPER=pump ENABLE=0`), and stop the URScript program on the teach pendant. All components can be tested independently at their respective stages.

### Tools/Equipment

- Oscilloscope with 2+ channels (for latency measurement)
- Oscilloscope probes compatible with 3.3V logic signals
- All hardware from previous stages
- UR30 teach pendant

---

## Stage 8: Pi400 HMI

**Goal:** The Pi400 can access the Mainsail web UI and SSH into the headless Pi for monitoring and development.

**Estimated time:** 30 minutes -- 1 hour

**Prerequisites:**
- Stage 1 complete (Pi running Moonraker + Mainsail)
- Pi400 on the same network as the headless Pi (ethernet or WiFi)

### Action

1. **Connect the Pi400** to the same network as the headless Pi. This can be:
   - Same gigabit switch as the Pi and UR30 (preferred -- all devices on one subnet).
   - Same WiFi network (higher latency, fine for monitoring).

2. **Verify connectivity from Pi400:**
   ```
   ping w26-pi.local
   ```

3. **Open the Mainsail web UI** in a browser on the Pi400:
   ```
   http://w26-pi.local
   ```

   Mainsail should show:
   - Printer status (Ready, Idle, Printing, Error)
   - Temperature readings (MCU temp if configured)
   - Console for sending G-code commands
   - Toolhead position and stepper status

4. **Test SSH access:**
   ```
   ssh pi@w26-pi.local
   ```

5. **Optional: Install Mainsail bookmarks** in the browser for quick access.

6. **Optional: Configure Moonraker trusted clients** if not already done. Edit `~/printer_data/config/moonraker.conf` on the Pi:
   ```ini
   [authorization]
   trusted_clients:
       127.0.0.1
       192.168.0.0/16
       10.0.0.0/8
   cors_domains:
       *
   ```
   Restart Moonraker:
   ```
   sudo systemctl restart moonraker
   ```

### Verification

- Mainsail web UI loads on the Pi400 browser and shows "Ready" status.
- G-code commands sent from the Mainsail console on Pi400 move the stepper.
- SSH from Pi400 to Pi works without issues.

### Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Mainsail shows 502 | Moonraker not running or Klipper down | SSH into Pi, check `systemctl status moonraker klipper`. |
| `w26-pi.local` does not resolve from Pi400 | mDNS not working across network segments | Use the Pi's IP address directly. Install `avahi-daemon` on both devices. |
| Mainsail shows `Unauthorized` | Moonraker trusted_clients not configured | Add Pi400's IP or subnet to `moonraker.conf` trusted_clients. |
| Browser shows blank page | Mainsail not installed or wrong port | Check `moonraker.conf` for the correct port (default 7125 for API, Mainsail is typically served on port 80 by nginx). Verify nginx is running: `systemctl status nginx`. |

### Rollback

Pi400 HMI is purely a monitoring/development interface. If it does not work, the system still operates fully via SSH to the Pi or via the UR30 teach pendant. This stage is not on the critical path.

### Tools/Equipment

- Pi400 with keyboard, mouse, and monitor
- Ethernet cable (or WiFi)
- Web browser (Chromium, pre-installed on Pi OS)

---

## Week-by-Week Allocation

### Week 9: Spring Break (Mar 2--8) -- Primary Build

| Day | Target |
|-----|--------|
| Mon (Mar 2) | Stage 1: Flash Pi, install Klipper, verify SSH and Mainsail |
| Mon-Tue | Stage 2: Build firmware, flash SKR Pico, verify USB serial |
| Tue-Wed | Stage 3: Wire stepper, send test G-code, confirm motor moves |
| Wed-Thu | Stage 4: Read motor specs, set current, thermal test |
| Thu-Fri | Stage 5: Deploy bridge daemon, test with Klipper |
| Fri-Sat | Buffer for troubleshooting Stages 1--5 |

**Week 9 exit criteria:** Stepper motor moves on command from the Pi. Bridge daemon connects to Klipper and can command the stepper programmatically.

### Week 10 (Mar 9--15) -- RTDE Integration

| Day | Target |
|-----|--------|
| Lab sessions | Attend required labs (Festo PLC Lab 7). Parallelize project work. |
| Open time | Stage 6: Connect Pi to UR30 network, test RTDE register read/write |
| Open time | Begin Stage 7: First end-to-end test (UR30 command to stepper) |

**Week 10 exit criteria:** Bridge daemon reads RTDE registers from UR30 and writes status back. Basic end-to-end command flow works.

### Week 11 (Mar 16--22) -- End-to-End + Polish

| Day | Target |
|-----|--------|
| Lab sessions | Lab 8 -- Finalize motor driver. Adapt for project. |
| Open time | Stage 7: Full end-to-end testing under robot motion |
| Open time | Stage 8: Pi400 HMI setup |
| Open time | Tune extrusion multiplier and Klipper accel/velocity |
| Mar 22 | Stage 7 complete. Write Phase 3 progress memo. |

**Week 11 exit criteria:** Full end-to-end chain works. UR30 sends extrude command, stepper responds at correct speed. Pi400 can monitor via Mainsail. Phase 3 progress memo submitted.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Motor/pump not received in time | Medium | High (blocks Stage 3+) | Test with a spare NEMA 17 motor. Tune current/speed for actual motor when received. |
| Pi model not selected yet | Medium | Medium (delays Stage 1) | Order immediately. Pi 4B or Pi 5 recommended. In worst case, use the Pi400 as both Klipper host and HMI (changes architecture slightly but is functional). |
| `ur-rtde` library won't install on ARM | Low | Medium (delays Stage 6) | Use the UR official Python RTDE client as fallback. Or cross-compile on x86 and copy. |
| Klipper `kinematics: none` incompatible with `[manual_stepper]` | Low | Medium | Tested in Phase 2 design. Fallback: use `kinematics: cartesian` with dummy XYZ steppers. |
| USB serial disconnects under motor noise | Low | Medium | Switch to UART serial (requires rewiring). Use ferrite beads on USB cable. Ensure common ground between Pi and SKR Pico. |
| UR30 not available during Spring Break | Medium | High (delays Stage 6-7) | Complete Stages 1--5 independently. Stage 6+ requires UR30 access (lab or room with UR30). Coordinate lab access with instructor. |
| 24V power supply not available for lab testing | Low | Low | Use a bench supply from the electronics lab. Any 24V / 2A+ supply works. |

---

## Equipment Checklist

Gather all items before starting Stage 1.

- [ ] Raspberry Pi (model TBD) + MicroSD card (32 GB+) + 5.1V/3A power supply
- [ ] BigTreeTech SKR Pico V1.0
- [ ] USB-C cable (data-capable, not charge-only)
- [ ] Stepper motor (provided) + 4-wire cable
- [ ] 24V power supply (bench supply or UR controller power block)
- [ ] Ethernet cables (x2: Pi to switch, switch to UR30)
- [ ] Gigabit ethernet switch
- [ ] Raspberry Pi 400 + monitor + keyboard + mouse
- [ ] SD card reader/writer
- [ ] Multimeter
- [ ] Small screwdrivers (for screw terminals)
- [ ] Oscilloscope + probes (for Stage 7 latency measurement)
- [ ] Infrared thermometer (for Stage 4 thermal testing, optional)
- [ ] USB drive (for URScript file transfer to UR30)
- [ ] Spare NEMA 17 stepper motor (if primary motor not yet received)
