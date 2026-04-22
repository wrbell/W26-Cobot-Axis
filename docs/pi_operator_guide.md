# Pi Operator Guide — Terminal Troubleshooting at the Console

Short, command-first cheat sheet for an operator sitting at the Pi with a monitor and USB keyboard (no SSH). Use this when the lab's ethernet switch is down, your dev laptop can't reach the Pi, or you just want to verify the stack fast.

This guide complements rather than replaces:

- [`SETUP.md`](../SETUP.md) §10 — first-time install + production troubleshooting
- [`docs/dev_bench_guide.md`](dev_bench_guide.md) — dev bench (URSim + Pi) bring-up
- [`docs/end_to_end_test_guide.md`](end_to_end_test_guide.md) — running the motor-spin playbook

---

## 1. First contact

Log in at the console (`pi` / the password you set in Pi Imager). Then:

```bash
hostname                 # expect: w26-pi
ip -4 addr show eth0     # expect: inet 192.168.0.4/24
date                     # sanity: wall-clock is set
```

If `eth0` has no `192.168.0.x/24` address, the lab-subnet NetworkManager profile didn't come up. Repair with:

```bash
sudo nmcli connection up w26-lab
# or if the profile is missing entirely:
sudo nmcli con add type ethernet con-name w26-lab ifname eth0 \
    ipv4.method manual ipv4.addresses 192.168.0.4/24 \
    ipv4.never-default yes
sudo nmcli con up w26-lab
```

---

## 2. "Is everything up?" one-liner

Copy-paste this; it's the single most useful block when something feels wrong.

```bash
{
  echo "=== services ===";
  systemctl is-active klipper w26-bridge moonraker 2>&1;
  echo "=== serial ===";
  ls /dev/serial/by-id/ 2>/dev/null || echo "(no /dev/serial/by-id — Pico not seen)";
  echo "=== UR30 ping ===";
  ping -c 2 -W 1 192.168.0.3 | tail -3;
  echo "=== bridge tail ===";
  sudo journalctl -u w26-bridge -n 10 --no-pager | tail -10;
}
```

**What "healthy" looks like:**

```
=== services ===
active
active
active
=== serial ===
usb-Klipper_rp2040_<hexserial>-if00 -> ../../ttyACM0
=== UR30 ping ===
2 packets transmitted, 2 received, 0% packet loss
=== bridge tail ===
... Bridge running at 125 Hz (dry_run=False, extrusion_source=ur, ...)
```

Any `inactive` / `failed` / ping loss / missing serial → jump to §7.

---

## 3. Klipper health

```bash
systemctl status klipper --no-pager | head -15
tail -30 /home/pi/printer_data/logs/klippy.log
```

Lines to look for in klippy.log (most recent session — scroll to the bottom):

- `Loaded MCU 'mcu' 135 commands` — MCU firmware version match
- `Configured MCU 'mcu' (1024 moves)` — config accepted
- `StallGuard monitor started` — (only present on the StallGuard-overlay firmware)
- `Stats ...` lines — steady-state heartbeat (one per second)

Red flags:

| Message | Meaning | Fix |
|---|---|---|
| `Printer is halted` | Klipper threw an error and shut down motion | `FIRMWARE_RESTART` (see below) |
| `TMC pump failed to init: Unable to read tmc uart 'pump' register IFCNT` | 24 V VIN not reaching the TMC2209 | verify 24 V at SKR Pico VIN, restart klipper |
| `Option 'X' is not valid in section 'Y'` | `printer.cfg` parse error (often a stray leading-space section header) | fix the config line, `systemctl restart klipper` |
| `mcu 'mcu' shutdown` | MCU lost communication with host | `FIRMWARE_RESTART`; if persistent, re-seat USB cable / reflash Pico |

**Recover from halted:**

```bash
curl -s -X POST http://localhost:7125/printer/gcode/script \
     --data-urlencode 'script=FIRMWARE_RESTART' | head
```

You should see `{"result":"ok"}`. Wait ~5 s, then `tail -5 /home/pi/printer_data/logs/klippy.log` should show `Printer is ready`.

---

## 4. ur-rtde health (UR30 reachability + register read)

This one-liner opens an RTDE receive connection, reads mode/safety/register 12, and disconnects. It's the fastest proof the robot is actually talking.

```bash
/home/pi/klippy-env/bin/python - <<'PY'
from rtde_receive import RTDEReceiveInterface
try:
    r = RTDEReceiveInterface("192.168.0.3")
    print("  robot mode  :", r.getRobotMode())     # 7 = RUNNING
    print("  safety mode :", r.getSafetyMode())    # 1 = NORMAL
    print("  out_int_12  :", r.getOutputIntRegister(12))
    print("  out_dbl_12  :", r.getOutputDoubleRegister(12))
    print("  TCP pose Z  :", round(r.getActualTCPPose()[2], 4))
    r.disconnect()
except Exception as e:
    print("  RTDE failed:", e)
PY
```

Mode/safety quick reference:

| Robot mode | Meaning |
|---|---|
| 0 | DISCONNECTED |
| 3 | IDLE |
| 5 | POWER_OFF |
| 7 | RUNNING (normal operating state) |
| 8 | UPDATING_FIRMWARE |

| Safety mode | Meaning |
|---|---|
| 1 | NORMAL (go) |
| 11 | PROTECTIVE_STOP |
| 14 | TP_THREE_POSITION_ENABLING_STOP (3PE button released in Manual mode) |

If the call fails with `Connection reset by peer`, see `docs/end_to_end_test_guide.md` §Troubleshooting matrix — usually 3PE stop or another RTDE client has already claimed the input registers.

---

## 5. Bridge log tail

```bash
sudo journalctl -u w26-bridge -f      # live follow; Ctrl-C to exit
```

**Healthy signatures** (one-shot at startup):

```
[bridge.rtde_client] INFO: RTDE connected to 192.168.0.3
[bridge.klipper_client] INFO: Connected to klippy at /home/pi/printer_data/comms/klippy.sock
[bridge] INFO: Klipper state: Printer is ready
[bridge] INFO: Bridge running at 125 Hz (...)
```

After startup the bridge is intentionally quiet at `INFO` level — no news is good news. Errors you might see:

- `Failed to write RTDE status: ... already in use` — a fieldbus (EtherNet/IP / PROFINET / MODBUS) or another RTDE client has claimed the input registers. Only one client at a time.
- `Klipper move failed: Timed out waiting for klippy response` — klippy's lookahead queue is full. `FIRMWARE_RESTART` clears it.
- `RTDE disconnected` / `reconnecting` — ethernet blip or UR30 reboot. The bridge auto-reconnects via its state machine.

---

## 6. Manual motor spin (no UR30 in the loop)

The fastest way to prove Pi → Klipper → TMC2209 → motor independently of the robot. Run these three `curl`s through Moonraker's HTTP API:

```bash
curl -s -X POST http://localhost:7125/printer/gcode/script \
     --data-urlencode 'script=MANUAL_STEPPER STEPPER=pump ENABLE=1' && echo
curl -s -X POST http://localhost:7125/printer/gcode/script \
     --data-urlencode 'script=MANUAL_STEPPER STEPPER=pump MOVE=20 SPEED=4 ACCEL=70 SYNC=1' && echo
curl -s -X POST http://localhost:7125/printer/gcode/script \
     --data-urlencode 'script=MANUAL_STEPPER STEPPER=pump ENABLE=0' && echo
```

- `MOVE=20 SPEED=4` → 5 seconds of motion at 4 mm/s (one half-revolution at `rotation_distance=40`)
- `SYNC=1` blocks the HTTP call until the move completes — you can see elapsed time from the terminal
- Each call returns `{"result":"ok"}` when accepted

If the motor doesn't spin:

1. Did `MANUAL_STEPPER ... ENABLE=1` return `ok`? If no, klipper is halted — see §3.
2. Is 24 V at the SKR Pico VIN? Green 3V3 LED on = 5 V only, not enough for the TMC.
3. Is the motor cable plugged into the **E-axis stepper header** on the SKR Pico (not X/Y/Z)?
4. Motor coil pair order matters. Wrong order = motor hums without turning. See `docs/config_guide.md`.

---

## 7. Common failure modes (symptom → fix)

| Symptom | Likely cause | Fix |
|---|---|---|
| `systemctl is-active klipper` → `failed` | Bad `printer.cfg` | `sudo journalctl -u klipper -n 30`; fix config; `sudo systemctl restart klipper` |
| `/dev/serial/by-id` is empty | USB cable is charge-only, or Pico not in Klipper firmware | Swap to known-good data cable; if still empty, hold BOOTSEL + replug → flash `klipper.uf2` |
| `w26-bridge` in `activating` loop | `ExecStartPre` or CHDIR failure | `sudo journalctl -u w26-bridge -n 30` — usually missing dir or permission; see `CHANGELOG.md [2026-04-22]` for the `%h` / ProtectHome fix already landed |
| `ping 192.168.0.3` fails | UR30 off, cable, or wrong subnet | Check link lights at switch; `ip -4 addr show eth0`; cycle UR30 teach pendant if it's been sitting idle |
| Motor commands succeed but no spin | Missing 24 V VIN, or coil order | See §6 list |
| RTDE handshake `Connection reset by peer` | 3PE safety stop, or fieldbus claimed registers | Hold 3PE button middle (safety → NORMAL); or `docs/end_to_end_test_guide.md` troubleshooting matrix |

Deep dives live in:

- `CHANGELOG.md [2026-04-22]` and `[2026-04-22b]` — the four gotchas we actually hit during first bring-up
- `docs/end_to_end_test_guide.md` — run-book for coordinated UR30 + bridge + Klipper tests
- `SETUP.md` §10 — production deployment troubleshooting table

If nothing in this guide helps, grab the last 200 lines of each log for triage:

```bash
sudo journalctl -u klipper -n 200 > /tmp/klipper.log
sudo journalctl -u w26-bridge -n 200 > /tmp/bridge.log
cp /home/pi/printer_data/logs/klippy.log /tmp/klippy.log
ls -la /tmp/*.log
```

Pop a USB stick in and copy those files off for analysis.
