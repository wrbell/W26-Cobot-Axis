# Changelog

All notable user-visible changes to this project are tracked here. The format
loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) grouped
by meaningful bringup checkpoints rather than strict semver — this is a Bolton
7-step capstone project, not a shipping product.

## [Unreleased]

## [2026-04-22] — First end-to-end RTDE handshake

**Milestone: first real data read from the physical UR30.** Lab bringup took
the project from "software ready, hardware unseen" to "RTDE client pulling
live TCP pose + force + joint state from a real UR30" on the first lab visit.

### Achieved

- **Dashboard Server handshake** on port 29999 — `Connected: Universal Robots
  Dashboard Server`, `robotmode` / `safetystatus` / `programState` /
  `PolyscopeVersion` all responding.
- **RTDE receive handshake** on port 30004 from `/home/pi/klippy-env/bin/python`
  using `ur_rtde` 1.6.3. Live values captured:
  - robot mode 7 (RUNNING), safety mode 1 (NORMAL)
  - actual TCP pose `[-0.228, -0.993, -0.254, -3.051, 0.689, -0.016]` (m, rad)
  - actual TCP force `[0.03, 1.45, 0.86, -0.10, 0.07, 0.02]` (N / N·m, at-rest
    gravity residual)
  - joint positions, velocities, currents all streaming cleanly
- **PolyScope firmware confirmed:** `URSoftware 5.19.0.1210631 (Oct 23 2024)`.
  Classic PolyScope 5 (not PolyScope X), so no Network Security layer — simpler
  of the two controller firmware families.
- **UR30 MAC OUI confirmed:** `00:30:d6:*` (Universal Robots) at `192.168.0.3`.

### Network topology (now live)

| Node | Interface | Address | Notes |
|---|---|---|---|
| UR30 controller | onboard RJ45 | `192.168.0.3/24` | factory default, MAC `00:30:d6:41:17:60` |
| Pi (`w26-pi`) | `eth0` | `192.168.0.4/24` static | NetworkManager profile `w26-lab`; **moved from `.50`** (see below) |
| Mac (dev laptop) | `en9` (USB-ethernet AX88179B) | `192.168.0.100/24` alias over link-local | non-persistent: `sudo ifconfig en9 alias 192.168.0.100 netmask 255.255.255.0` |
| Lab switch | — | — | unmanaged L2, no DHCP, no router on the subnet |

### The big gotcha: UR30 inbound firewall whitelist

The lab's UR30 is pre-configured with a **"restricted inbound network access"
policy that only accepts TCP from `192.168.0.4/32`** (single host, /32 mask).
ICMP is not filtered — ping succeeds from any IP — but every TCP port
(29999 / 30001–30004) appears *closed* to non-whitelisted sources. Burned ~1 hr
chasing this as if URControl hadn't started. Resolution: moved the Pi's static
IP from `.50` (SETUP.md default) to `.4` to match the whitelist.

**Debugging heuristic for future labs:** if ICMP works but port 29999 is
closed, suspect the whitelist before debugging URControl, PolyScope mode, or
network security. The Dashboard Server on 29999 is always-on as soon as
URControl boots — no robot initialization required — so a closed 29999 with
working ICMP is a reliable firewall smell.

### Added

- `w26-pi-lab` SSH host alias in `~/.ssh/config` pointing at `192.168.0.4`.
- NetworkManager connection profile `w26-lab` on the Pi:
  `sudo nmcli con add type ethernet con-name w26-lab ifname eth0
   ipv4.method manual ipv4.addresses 192.168.0.4/24`. No gateway / DNS
  (no router on the subnet); `ipv4.never-default yes` avoids default-route
  hijack. Persists across reboot.

### Changed

- Pi static IP: **`192.168.0.50` → `192.168.0.4`** (forced by UR30 whitelist).
  SETUP.md §3 still documents `.50` as the planned address; the whitelist
  constraint overrides it for this specific lab / controller pairing. Rather
  than changing SETUP.md now, we'll revisit documentation if/when the
  whitelist is widened or we move to a different controller.

### Notes

- Pi runs NetworkManager (MainsailOS on Bookworm), **not** `dhcpcd`.
  SETUP.md §3 mentions both — the `nmcli` flow is the correct one for this
  image.
- `ur_rtde` on the Pi lives in `/home/pi/klippy-env`, not
  `/home/pi/moonraker-env` or system Python. `getRobotVoltage()` isn't
  available in this binding version; other getters (TCP pose/force/speed,
  joint position/velocity/current, robot mode, safety mode) all work.
- Robot must be in `Robotmode: RUNNING` (motors powered, brakes released)
  before ports 30001–30004 accept connections. `NO_CONTROLLER` state
  TCP-refuses them even though 29999 Dashboard remains open.

### Pico / Klipper bringup (same day)

- **SKR Pico v1.0 flashed with Klipper** (baseline `klipper-local.uf2`, no
  StallGuard overlay on this pass — fallback-first rollout). Flash workflow:
  BOOTSEL jumpered, plug into Mac → `RPI-RP2` mass storage mounts → drop UF2
  → auto-reboot. First flash required BOOTSEL jumper to be **removed** before
  the firmware would take hold; leaving the jumper in puts the board back
  into bootloader on every reset.
- **Pi ↔ Pico USB serial up.** Pico enumerates as:
  - `lsusb`: `ID 1d50:614e OpenMoko, Inc. rp2040` (Klipper's vendor/product)
  - `/dev/serial/by-id/usb-Klipper_rp2040_504450593048501C-if00 → /dev/ttyACM0`
- **`printer.cfg` serial placeholder patched** from
  `usb-Klipper_rp2040_PLACEHOLDER-if00` to the real serial. Klipper service
  now reports: `Loaded MCU 'mcu' 135 commands`, `Configured MCU 'mcu' (1024
  moves)`, `StallGuard monitor started`, stats streaming continuously.
- **Outstanding: TMC2209 UART init fails** — `TMC pump failed to init:
  Unable to read tmc uart 'pump' register IFCNT`. Root cause: **SKR Pico
  24V VIN not yet connected** — USB alone powers the RP2040 and the 3V3
  rail, but the TMC2209 drivers need motor voltage (24V VIN) before they
  respond on UART. Expected to clear as soon as 24V is applied and klipper
  restarts.

### USB cable gotcha

Two separate USB-C to USB-A cables were charge-only (no USB 2.0 data pair).
Symptom: `lsusb` / `dmesg` show zero new events on replug; the SKR Pico's
green 3V3 LED lights normally (because VBUS 5V still flows). Windows + Mac
also saw nothing. Burned ~30 min before swapping to a known-good cable.
Mitigation: keep a labeled "W26 DATA CABLE" in the lab kit.

### Added (bringup utility)

- `src/urscript/test_motor_only.script` — minimal end-to-end bringup
  URScript. Writes RTDE output registers (mode / rate / enable) to command
  the pump stepper through UR30 → Pi bridge → Klipper → TMC2209, with
  **zero arm motion** (no `movel` / `movej` / `speedl` / `speedj`). Ramps
  0 → 2 mm/s → hold 5 s → 0, cleans up, done. Two ways to run it: USB
  stick on the pendant, or `nc 192.168.0.3 30002` from the Pi for rapid
  iteration.

## [Previously Unreleased] — 2026-04-21

Work done the evening of 2026-04-21 to smooth the first hardware integration.

### Added

- **SSH reverse-proxy tunnel** procedure in `docs/headless_setup.md` §6.4 for
  corporate/enterprise WiFi that blocks Internet Sharing. Proven end-to-end:
  `apt-get update` on the Pi egresses through a tinyproxy on the laptop via
  `ssh -R 8888:127.0.0.1:8888`. Apt + pip + git proxy templates pre-staged on
  the Pi as `.disabled` files for one-line activation.
- `scripts/fake_ur30.py` — minimal RTDE handshake listener. Binds :30004,
  satisfies `REQUEST_PROTOCOL_VERSION` and `GET_URCONTROL_VERSION`, logs every
  subsequent request. Scaffold for Mac-side smoke testing without Docker /
  URSim; extend as needed for further handshake steps.
- `~/bringup-post-flash.sh` on the Pi (not in repo): idempotent script that
  captures the SKR Pico's `/dev/serial/by-id/...` path after BOOTSEL flash,
  patches `printer.cfg`, restarts Klipper, and starts `w26-bridge`.
- This CHANGELOG.

### Changed

- **Breaking:** default `UR30_HOST` is now `192.168.0.3` (UR30 factory default)
  instead of `192.168.1.100`. Project subnet swapped from `192.168.1.0/24` →
  `192.168.0.0/24` across `config.py`, SETUP.md, `network_architecture.md`,
  `deployment.md`, `dev-sync.sh`, and other docs. Unrelated example IPs
  preserved. (#18)
- CI `Firmware Build` workflow bumps the `awalsh128/cache-apt-pkgs-action`
  version key and sets `execute_install_scripts: true`, so dpkg post-install
  scripts replay on cache hit instead of leaving newlib headers unregistered
  with gcc-arm-none-eabi. (#17, fixes #16)

## [v1.0.0-bringup] — 2026-04-21

Bringup-readiness snapshot tag. All software complete and staged on the Pi the
night before first hardware integration.

### Added

- 479 bridge tests passing at 100% coverage, ruff clean.
- `klipper.uf2` staged on the Pi in two variants:
  - `~/klipper.uf2` — v1.0.0-rc1 release build (with StallGuard overlay).
  - `~/klipper-local.uf2` — freshly built from `~/klipper` tonight, baseline
    without StallGuard overlay (fallback if overlay misbehaves).
- `ur-rtde` 1.6.3 compiled into `~/klippy-env` on the Pi (~42 min on 4 cores;
  wheel cached at `~/.cache/pip/wheels/` for future rebuilds without
  recompilation).
- `w26-bridge.service` systemd unit installed and enabled on the Pi.
- `printer.cfg` symlinked into `~/printer_data/config/`; `~/gcode_files/`
  ensured to exist.

## [v1.0.0-rc1] — 2026-04-12

First formal release candidate. `klipper.uf2` firmware asset attached to this
release is the canonical pre-built artifact for Pi bringup — downloaded and
staged on the Pi ahead of tomorrow's integration.

### Fixed

- `klippy` Unix socket path in `bridge/config.py` defaults to MainsailOS's
  `~/printer_data/comms/klippy.sock`. `deploy.sh` apt-installs Boost dev
  packages needed for the ur-rtde C++ build. (#15, merged 2026-04-21 on top
  of rc1 but semantically part of the rc1 line of bringup prep.)

## [v2026.09.0] — 2026-02-24

End of Phase 2 memo drafting. Pre-release tag anchoring the state in which
Phase 2 deliverables (block diagram, schematic, pin table, power budget,
buck converter selection, BOM) were ready for typesetting. See
`docs/phase2/` for the memo drafts at this point.

## Earlier

The repo predates formal changelog tracking; see `git log` and merged PR
history (#5–#15) for per-commit detail prior to 2026-04-12. Major pre-rc1
milestones captured there:

- Firmware build pipeline with cppcheck, LTO-aware symbol verification, stack
  usage analysis, and SRAM/flash budget gates.
- StallGuard dual-core RP2040 firmware overlay with klippy-extras module and
  Pi-side event accumulator.
- Hardware configuration & calibration guide (`docs/config_guide.md`).
- Dashboard Server integration for UR30 lifecycle management.
- Extrusion profile library (linear / polynomial / lookup-table rate shaping).
- CI infrastructure: Codecov, Dependabot auto-merge, PR size labels, branch
  protection, pre-commit tooling, problem matchers, apt caching.
