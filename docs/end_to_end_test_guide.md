# End-to-End Test Guide — UR30 → Pi → Klipper → Motor

Run-book for coordinated motor-spin tests that exercise the full chain. Use this whenever you want UR30-driven motor motion (not just direct Klipper MANUAL_STEPPER from the Pi, which is `docs/pi_operator_guide.md` §6).

First end-to-end spin achieved 2026-04-22. The hard-won lessons from that session are baked into this playbook.

Companion references:

- [`docs/pi_operator_guide.md`](pi_operator_guide.md) — terminal-level sanity checks at the Pi console
- [`docs/register_allocation.md`](register_allocation.md) — authoritative register map (post PR #29)
- [`SETUP.md`](../SETUP.md) §10 — first-time production deploy troubleshooting
- [`CHANGELOG.md`](../CHANGELOG.md) — dated entries `[2026-04-22]`, `[2026-04-22b]`, `[2026-04-22c]` are the field log

---

## 1. Preflight checklist

Before pushing any URScript, walk this list top-to-bottom. Every item here came from a real thing that bit us.

**Network**

- [ ] Lab switch powered, link lights green on Pi port + UR30 port
- [ ] `ping -c 2 192.168.0.3` from the Pi succeeds (`0% packet loss`, ~0.3 ms)
- [ ] Pi eth0 is `192.168.0.4/24` (UR30 firewall whitelist is `.4/32`, so a different IP will look like "ports closed")
- [ ] If pushing from the Mac: `sudo ifconfig en9 alias 192.168.0.100 netmask 255.255.255.0` — this alias drops on every `en9` link bounce

**UR30**

- [ ] Teach pendant booted, `Robotmode: RUNNING`, `Safetystatus: NORMAL`
- [ ] **Remote Control is ENABLED** (top bar shows "Remote", not "Local"). Without this, ports 30001–30003 refuse URScript. Set at the pendant; cannot be flipped to Remote from Dashboard for ISO safety reasons
- [ ] Operational mode: **Manual** with 3PE button held middle, **or Automatic** (Automatic is simpler — no button to hold)
- [ ] Speed slider > 0% (a 0% slider refuses even non-motion programs)

**Pi + Klipper + bridge**

- [ ] `systemctl is-active klipper` → `active`; klippy.log last line is a `Stats` heartbeat (printer is ready, no `halted`)
- [ ] `systemctl is-active w26-bridge` → `active`; bridge journal ends with `Bridge running at 125 Hz`
- [ ] `ls /dev/serial/by-id/` shows `usb-Klipper_rp2040_<serial>-if00`
- [ ] 24 V VIN is connected to the SKR Pico VIN (TMC2209 drivers won't respond on UART without motor voltage)
- [ ] TMC init success — grep klippy.log: *no* `TMC pump failed to init` in the current session

**Optional but recommended**

- [ ] Run `docs/pi_operator_guide.md` §6 `curl` motor spin first, to prove Pi→Klipper→motor works independently. If that fails, don't bother with RTDE yet.

---

## 2. Two run paths

### Path A — Pendant + USB stick (production demo path)

1. Copy `src/urscript/test_motor_only.script` to a FAT32 USB stick
2. Plug stick into the teach pendant's USB-A port (back of pendant)
3. Pendant → **New Program** → Empty
4. **Add Node** → **Advanced** → **Script** (`Script Code` variant)
5. Paste the contents of `test_motor_only.script` into the script node
6. **Save As** → `motor_test.urp`
7. Tap **Play** (▶) at the bottom of the pendant
8. Motor should ramp up, hold 5 s at ~4 mm/s, and ramp down

This path is the one to use for an oral defense or any scripted demo — it's fully self-contained.

### Path B — Secondary Interface push from the Pi (fast iteration)

```bash
# On the Pi (or via SSH from the Mac if the lab subnet is reachable):
cat /home/pi/W26-Cobot-Axis/src/urscript/test_motor_only.script \
    > /dev/tcp/192.168.0.3/30002
```

That's it. Secondary Interface executes URScript immediately (no pendant interaction).

To watch the RTDE registers flow in real-time while the script runs, open a second shell and run:

```bash
/home/pi/klippy-env/bin/python - <<'PY'
from rtde_receive import RTDEReceiveInterface
import time
r = RTDEReceiveInterface("192.168.0.3")
prev = (-1, -1.0)
for i in range(120):                     # 12 seconds at 100 ms polling
    m = r.getOutputIntRegister(12)
    rate = r.getOutputDoubleRegister(12)
    if (m, rate) != prev:
        print(f"t={i*0.1:4.1f}s  mode={m}  rate={rate:.3f}")
        prev = (m, rate)
    time.sleep(0.1)
r.disconnect()
PY
```

**Trap**: URScript pushed via Secondary Interface *silently* rejects top-level variable assignments (e.g., `X = 5` outside any `def`). Put every constant inside the `def` you're calling at the end of the file, or pendant-load it as a `.urp` instead.

---

## 3. Expected success signatures

During and after a clean run:

**RTDE register polling trace** (Path B monitoring command above):

```
t= 0.0s  mode=0  rate=0.000
t= 1.2s  mode=1  rate=0.200
t= 1.3s  mode=1  rate=0.400
...
t= 3.1s  mode=1  rate=4.000
t= 8.2s  mode=0  rate=0.000
```

**Klipper stats** (`tail /home/pi/printer_data/logs/klippy.log`):

- `print_time` advances by ~1 s per second of commanded motion (5 s hold at 4 mm/s → `print_time` gains ~5 s)
- `buffer_time` fills to single-digit seconds during the hold, drains to 0 after
- no `Timed out waiting for klippy response` in the bridge journal

**Bridge journal** (`sudo journalctl -u w26-bridge --since "1 minute ago"`):

- no `ERROR` lines
- if you bumped `LOG_LEVEL=DEBUG` in `config.py`, you'll see per-tick activity; at default `INFO` the bridge is quiet during normal operation

**The motor**: audibly and visibly rotates during the hold phase.

---

## 4. Operational-mode matrix

Which combinations of Local/Remote × Manual/Automatic × 3PE actually let the chain work:

| Remote Control | Op Mode | 3PE state | URScript on :30002 | RTDE output reads | RTDE input writes |
|---|---|---|---|---|---|
| **OFF (Local)** | any | any | **BLOCKED** (ports drop) | OK | single-client only |
| ON (Remote) | Manual | held (safety NORMAL) | **OK** | OK | OK |
| ON (Remote) | Manual | released (TP_3PE_STOP) | existing script continues | OK | new subscriptions may fail |
| ON (Remote) | Automatic | n/a | **OK** | OK | OK |

**Simplest configuration for testing:** Remote Control ON + Automatic mode. No button to hold, no 3PE stop to worry about.

The Dashboard Server (port 29999) can switch operational mode via `SetOperationalMode manual|automatic` (FW 5.0+) but **cannot** flip Local↔Remote (ISO safety restriction — external clients can't put themselves in control). If you need Remote Control, set it once at the pendant and leave it.

---

## 5. Troubleshooting matrix

| Symptom | Likely cause | Fix |
|---|---|---|
| URScript push succeeds but nothing happens; `programState: STOPPED <unnamed>` | Top-level `X = Y` assignments in the script; Secondary Interface drops them silently | Move everything inside a `def`; end the file with a call |
| URScript push succeeds and script executes but bridge journal is empty and motor doesn't move | Klipper is halted (hit an error earlier); `print_time` stuck, `buffer_time=0` | `curl -s -X POST http://localhost:7125/printer/gcode/script --data-urlencode 'script=FIRMWARE_RESTART'`, restart bridge |
| `RTDEReceiveInterface(...)` → `Connection reset by peer` | Safety stop (`TP_3PE_STOP`), OR another RTDE client has the registers, OR fieldbus (EtherNet/IP / PROFINET / MODBUS) claimed them | Hold 3PE middle → safety NORMAL; check for second RTDE client; disable fieldbus in the UR30's installation |
| `RuntimeError: One of the RTDE input registers are already in use!` | Another RTDE input-register client is active | Stop the other client, or wait 30 s for timeout; the bridge also holds inputs open while running |
| Port probes on 30001–30004 time out; 29999 (Dashboard) also closed | UR30 inbound firewall whitelist excludes your IP | Pi must be `192.168.0.4` (or whatever the UR30 installation whitelisted) |
| Ports open but URScript on :30002 rejected | Robot in Local mode | Switch to Remote Control at the pendant |
| Motor commands succeed but shaft doesn't turn | 24 V VIN missing, or wrong stepper slot, or coil phases interleaved | See `docs/pi_operator_guide.md` §6; verify wire order matches SKR Pico E-axis pinout |
| Bridge `ERROR: Klipper move failed: Timed out waiting for klippy response` | Lookahead queue stalled after many small moves | `FIRMWARE_RESTART` via Moonraker curl; then restart bridge |
| Motor makes noise but doesn't rotate | Coil phases crossed in connector (A1 B1 A2 B2 instead of A1 A2 B1 B2) | Swap the middle two wires in the 4-pin connector |

---

## 6. After-run cleanup

**Between successful runs**: usually nothing. The bridge and Klipper both return to idle automatically. Push the next script.

**After a klippy queue stall** (one of the `Timed out waiting for klippy response` bridge errors):

```bash
curl -s -X POST http://localhost:7125/printer/gcode/script \
     --data-urlencode 'script=FIRMWARE_RESTART' > /dev/null
sudo systemctl restart w26-bridge
```

**After a URScript error on the pendant** (red banner, robot stopped): hit OK on the pendant, check the program log at the bottom of PolyScope, retry with corrected URScript. The Pi side is unaffected.

**End-of-session shutdown** (leaving the lab):

```bash
ssh w26-pi-lab 'sudo shutdown -h now'   # from the Mac, if reachable
# OR at the Pi console:
sudo shutdown -h now
```

Wait for the green ACT LED to stop blinking before pulling power.

---

## 7. Known unknowns

- **3PE stop + RTDE subscription** — officially undocumented. Empirically, an already-subscribed session keeps running during a 3PE stop, but a freshly-opened `RTDEReceiveInterface` can fail with `Connection reset by peer`. If you see this, the bridge's session is already holding the registers; kill the test script and let the bridge alone, or restart the bridge to re-subscribe cleanly.
- **CSV logging during the test run** — the bridge has a `--log` flag that writes per-tick telemetry to `/tmp/w26_logs/*.csv`, which `scripts/report_figures.py` consumes for Figures 8 / 10. We didn't capture CSV during the 2026-04-22 spin; do so on the next run if you need publication-quality plots.
- **Fieldbus + RTDE coexistence** — if someone enables EtherNet/IP or PROFINET on the robot's Installation, the bridge will fail to reserve input registers. Keep those disabled unless you have a reason.
