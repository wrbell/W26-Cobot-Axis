# URCap Blocker: MachineMotion → Secondary-Interface Workaround

## Symptom

On the lab's UR30, loading any `.urp` program from the teach pendant and tapping **Play** throws an error banner:

```
Check configuration — cannot connect to MachineMotion
```

The program does not run. Nothing on the Pi or the bridge is at fault; the robot's URControl refuses to start the program.

## Root cause

The lab's UR30 has the **Vention MachineLogic URCap** (also called *MachineMotion*) installed and enabled in its current Installation. At program start, PolyScope runs the Installation's URCap initialization blocks; MachineLogic tries to open a TCP connection to a Vention MachineMotion controller. We don't have a MachineMotion controller on the network, the connect attempt times out, and PolyScope blocks the program from running with the banner above.

The banner is misleading — it suggests "fix the configuration of your program," but the offender is actually the Installation-level URCap, not anything in our script.

## Who is affected

- **Any `.urp` Play from the pendant** — blocked by the URCap init, regardless of what's in the program.
- **Dashboard `play` command (port 29999)** — same path, same block.
- **URScript sent on the Primary / Secondary / Real-Time Interface (ports 30001 / 30002 / 30003)** — ✅ **not affected.** These interfaces execute URScript standalone without running the Installation's init blocks.

## Workaround: Secondary Interface push (port 30002)

Push URScript directly to port 30002 from the Pi. The script executes on the robot without triggering the URCap init path.

### Preconditions

1. **Remote Control is ON** at the pendant (top-right: Settings → System → Remote Control → toggle on). In Local mode, ports 30001 / 30002 / 30003 silently drop URScript writes.
2. **No `.urp` is currently `PLAYING`** on the pendant — even if it's stuck on the MachineMotion banner, the program state is `PLAYING` and the robot will refuse new URScript until it's stopped. Hit **Stop** (■) on the pendant, or File → Close Program.
3. **Operational mode = Automatic** (or Manual with the 3PE button held in the middle — Automatic is simpler).
4. **Robot initialized**: Robot mode `RUNNING`, Safety `NORMAL`, speed slider > 0 %.
5. **Script has no top-level variable assignments.** Secondary Interface silently drops `X = 5` outside a `def`. Put every constant inside the function you're calling; see `docs/end_to_end_test_guide.md` §2 Path B and the existing `src/urscript/test_motor_only.script` for the working pattern.

### Verification one-liner

```bash
# On the Pi (or over SSH from the Mac):
exec 3<>/dev/tcp/192.168.0.3/30002
echo "write_output_integer_register(12, 99)" >&3
sleep 1
exec 3<&-

# Read it back via ur_rtde:
/home/pi/klippy-env/bin/python -c "
from rtde_receive import RTDEReceiveInterface
r = RTDEReceiveInterface('192.168.0.3')
print('reg 12 =', r.getOutputIntRegister(12))
r.disconnect()
"
```

If `reg 12 = 99`, Secondary Interface is accepting and executing URScript — the full motor-test push will also work. If it stays at `0`, revisit the preconditions above (Remote Control OFF is by far the most common miss).

### Full motor-test push

```bash
cat /path/to/src/urscript/test_motor_only.script > /dev/tcp/192.168.0.3/30002
```

The proven pattern is documented in `docs/end_to_end_test_guide.md` §2 Path B, including live register polling and the bridge-log signatures to watch for.

## Clearing a stuck `motor_only_*.urp` program from the pendant

If a `.urp` is already stuck in `PLAYING` with the MachineMotion banner:

**Manual path (always works):** tap the red **Stop** (■) button at the bottom of the pendant. Optionally File → Close Program to unload it entirely.

**Dashboard path (requires Remote Control ON):**

```bash
exec 3<>/dev/tcp/192.168.0.3/29999
echo "stop" >&3
# expect: "Stopped" reply
exec 3<&-
```

If Remote Control is OFF, Dashboard answers `Command is not allowed due to safety reasons, please switch robot to Remote Control mode and reconnect to port 29999` — you're stuck with the manual path until Remote Control is flipped on at the pendant.

## Alternatives (not recommended for the submission demo)

- **New Installation without MachineLogic** — File → Installation → New Installation (save a backup copy first). Resets Safety, Tool TCP, Remote Control, and fieldbus settings; may require the safety password to confirm. Heavy-handed for a one-off demo.
- **Disable the URCap itself** — Installation → URCaps → MachineLogic → Disable. May be gated by an admin password configured by the lab. Persistent but disruptive to whoever else uses this robot.
- **Install a MachineMotion controller on the network** — out of scope.

The Secondary Interface push is the smallest-footprint workaround that keeps the lab's current Installation and safety configuration untouched.

## Bigger picture

This problem is a clean example of the rule: **`.urp` Play runs the Installation's URCap graph; URScript on ports 30001–30003 runs standalone.** When you're debugging "program won't run" errors with no obvious URScript fault, checking the Installation's active URCaps is the fast diagnostic.

## References

- `docs/end_to_end_test_guide.md` — full run-book (preflight, operational-mode matrix, troubleshooting matrix).
- `docs/pi_operator_guide.md` §6 — manual MANUAL_STEPPER spin via Moonraker (no UR30 at all).
- `docs/ur_rtde.md` §4 — UR client interfaces catalogue (ports 29999 / 30001 / 30002 / 30003 / 30004).
- `CHANGELOG.md [2026-04-23]` — this hurdle captured during the Phase 4 pendant test.
- [UR official — Send URScript commands on Primary/Secondary/Real-Time interfaces](https://docs.universal-robots.com/tutorials/urscript-tutorials/socket-communication.html)
