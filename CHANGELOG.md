# Changelog

All notable user-visible changes to this project are tracked here. The format
loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) grouped
by meaningful bringup checkpoints rather than strict semver — this is a Bolton
7-step capstone project, not a shipping product.

## [Unreleased]

Post-`v1.0.0-bringup` work done the evening of 2026-04-21 to smooth tomorrow's
first hardware integration.

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
