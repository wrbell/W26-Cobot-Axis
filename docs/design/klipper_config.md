# Moonraker and Mainsail Configuration Design

> **Project:** W26 Cobot Axis (ME472 Mechatronics Capstone)
> **Author:** Willem (Software/EE)
> **Date:** 2026-02-12
> **Status:** Design document -- no implementation yet
>
> **Context:** This document defines the Moonraker and Mainsail configuration
> for the W26 single-axis stepper system. The existing Klipper config is at
> `src/klipper/printer.cfg`. The bridge daemon (`src/bridge/`) connects to
> klippy directly via Unix socket.

---

## Table of Contents

1. [System Context](#1-system-context)
2. [moonraker.conf Design](#2-moonrakerconf-design)
3. [Mainsail Configuration Design](#3-mainsail-configuration-design)
4. [Integration: Bridge Daemon and Moonraker Coexistence](#4-integration-bridge-daemon-and-moonraker-coexistence)
5. [File Layout and Deployment](#5-file-layout-and-deployment)
6. [Security Considerations](#6-security-considerations)
7. [Optional / Future Features](#7-optional--future-features)
8. [Open Questions](#8-open-questions)
9. [References](#9-references)

---

## 1. System Context

### 1.1 Where Moonraker and Mainsail Fit

```
UR30 Controller
    |
    | RTDE / TCP-IP (port 30004)
    v
Pi (headless Klipper host)
    |
    |-- klippy (Klipper host process)
    |       |
    |       +-- /tmp/klippy_uds  (Unix domain socket, multiple clients)
    |               |
    |               +---- Bridge daemon (src/bridge/)  [real-time control path]
    |               |
    |               +---- Moonraker (port 7125)        [monitoring/management path]
    |                         |
    |                         +---- Mainsail (static web UI, port 80/443)
    |                                    ^
    |                                    |
    |-- USB serial --------> SKR Pico (Klipper MCU) --> Stepper --> Pump
    |
    +--- (network) ---> Pi400 (optional HMI, accesses Mainsail via browser)
```

### 1.2 Role of Each Component

| Component | Role | Required? |
|-----------|------|-----------|
| klippy | Klipper host -- motion planning, G-code, MCU comms | Yes |
| Bridge daemon | RTDE-to-Klipper translator (real-time control path) | Yes |
| Moonraker | HTTP/WebSocket API layer over klippy | Recommended |
| Mainsail | Web UI for monitoring and manual control | Optional (HMI) |

Moonraker is not strictly required for the control path -- the bridge daemon
talks directly to klippy via the Unix socket. However, Moonraker provides:

- Web-based monitoring from Pi400 (or any device on the network)
- Software update management for Klipper, Moonraker, and Mainsail
- Machine control (reboot, shutdown) via the web UI
- A convenient debugging interface during development

### 1.3 Why Not Route the Bridge Through Moonraker?

The bridge daemon connects to klippy's Unix socket directly (`/tmp/klippy_uds`)
rather than through Moonraker's HTTP/WebSocket API. Reasons:

1. **Latency.** Unix socket IPC is ~0.1ms. Moonraker's HTTP adds ~1-5ms, and
   WebSocket adds ~0.5-2ms. For a 125 Hz control loop, every millisecond matters.
2. **Simplicity.** The bridge daemon is a local process; it does not need HTTP,
   authentication, or JSON-RPC framing.
3. **Independence.** The control path works even if Moonraker is down or
   restarting. Moonraker is a monitoring convenience, not a control dependency.

---

## 2. moonraker.conf Design

### 2.1 Purpose

Moonraker sits between klippy and web frontends (Mainsail/Fluidd). It wraps
klippy's Unix socket API into HTTP REST and WebSocket JSON-RPC interfaces,
adding authentication, file management, update management, and job history.

For the W26 project, Moonraker provides:
- Mainsail web UI access for the Pi400 HMI
- Software update management
- A secondary debugging interface (curl, browser, Postman)
- Machine shutdown/reboot from the web UI

### 2.2 File Location

```
~/printer_data/config/moonraker.conf
```

This is the standard location when using Klipper's `printer_data` directory
structure (used by KIAUH, MainsailOS, and manual installs).

### 2.3 Section-by-Section Design

#### [server]

```ini
[server]
host: 0.0.0.0
port: 7125
klippy_uds_address: /tmp/klippy_uds
max_upload_size: 1024
```

| Setting | Value | Rationale |
|---------|-------|-----------|
| `host` | `0.0.0.0` | Listen on all interfaces so Pi400 can connect over the network |
| `port` | `7125` | Moonraker default. No reason to change. |
| `klippy_uds_address` | `/tmp/klippy_uds` | Default klippy socket path. Must match klippy startup args. Matches `config.py` `KLIPPY_SOCKET`. |
| `max_upload_size` | `1024` | Max file upload in MB. We will not upload G-code files in normal operation, but keep a reasonable limit for development. |

**Notes:**
- `ssl_port` is omitted. SSL/TLS is unnecessary on an isolated lab network.
  If the Pi were internet-exposed, we would enable it, but that is explicitly
  not part of this system's threat model.

#### [file_manager]

```ini
[file_manager]
enable_object_processing: False
```

| Setting | Value | Rationale |
|---------|-------|-----------|
| `enable_object_processing` | `False` | Object processing parses G-code files for individual object tracking (cancel-object feature). Not applicable -- we do not process sliced G-code files. |

The `virtual_sdcard` path is already defined in `printer.cfg` as `~/gcode_files`.
Moonraker reads this from klippy and uses it for file operations. No need to
duplicate it here.

**What we do NOT need:**
- `queue_gcode_uploads` -- no print queue workflow
- `enable_inotify_warnings` -- default is fine

#### [authorization]

```ini
[authorization]
trusted_clients:
    127.0.0.1
    127.0.0.0/8
    192.168.0.0/16
    10.0.0.0/8
    172.16.0.0/12
    FE80::/10
    ::1/128
cors_domains:
    http://*.local
    http://*.local:*
    http://localhost
    http://localhost:*
    http://my.mainsail.xyz
    https://my.mainsail.xyz
force_logins: False
```

| Setting | Value | Rationale |
|---------|-------|-----------|
| `trusted_clients` | RFC 1918 private ranges + localhost + link-local IPv6 | Lab network only. All devices on the private network are trusted. No internet exposure. |
| `cors_domains` | `.local`, `localhost`, `my.mainsail.xyz` | `.local` covers mDNS hostnames (e.g., `pi.local`). `localhost` covers direct Pi access. `my.mainsail.xyz` is Mainsail's hosted instance that connects to a local Moonraker. |
| `force_logins` | `False` | No login required from trusted clients. Simplifies development. |

**Security note:** This is deliberately permissive because the system is on an
isolated lab network (UR30 + Pi + Pi400 on a dedicated switch, not
internet-routed). If the network topology changes, tighten `trusted_clients`
to the specific subnet or individual IPs.

**What we do NOT need:**
- API key authentication -- overkill for a lab network
- `default_source` -- default (moonraker database) is fine

#### [machine]

```ini
[machine]
provider: systemd_dbus
shutdown_command: /usr/sbin/shutdown -h now
reboot_command: /usr/sbin/shutdown -r now
```

| Setting | Value | Rationale |
|---------|-------|-----------|
| `provider` | `systemd_dbus` | Standard for Raspberry Pi OS. Allows Moonraker to manage Klipper/Moonraker services. Falls back to `systemd_cli` if dbus is unavailable. |
| `shutdown_command` | `/usr/sbin/shutdown -h now` | Enables "Shutdown Host" from Mainsail UI. Useful for safe Pi shutdown from Pi400. |
| `reboot_command` | `/usr/sbin/shutdown -r now` | Enables "Reboot Host" from Mainsail UI. |

**Notes:**
- Moonraker uses PolicyKit for privilege escalation. The install script sets
  this up. If using MainsailOS, it comes pre-configured.
- If `systemd_dbus` causes PolicyKit warnings, fall back to `systemd_cli`.

#### [data_store]

```ini
[data_store]
temperature_store_size: 600
gcode_store_size: 1000
```

| Setting | Value | Rationale |
|---------|-------|-----------|
| `temperature_store_size` | `600` | Number of temperature data points to retain (per sensor). At 1 sample/sec this is 10 minutes. We only have the MCU temperature sensor. |
| `gcode_store_size` | `1000` | Number of G-code response lines to cache. Useful for debugging bridge commands. |

#### [history]

```ini
[history]
```

Empty section enables the history component with defaults. This tracks
"print" jobs (in our case, extrusion sessions). Low cost, potentially useful
for Phase 4 testing data.

#### [octoprint_compat]

```ini
[octoprint_compat]
```

Empty section enables OctoPrint API compatibility. This is needed by some
Mainsail features and costs nothing to enable.

#### [update_manager]

```ini
[update_manager]
refresh_interval: 168
enable_auto_refresh: True

[update_manager mainsail]
type: web
channel: stable
repo: mainsail-crew/mainsail
path: ~/mainsail
```

| Setting | Value | Rationale |
|---------|-------|-----------|
| `refresh_interval` | `168` | Check for updates every 168 hours (1 week). |
| `enable_auto_refresh` | `True` | Automatically check for available updates. Does NOT auto-install. |
| `mainsail` section | web type, stable channel | Manages Mainsail web UI updates. The `path` is where Mainsail's static files are installed. |

**Notes:**
- Klipper and Moonraker update_manager entries are auto-generated by the
  install scripts. We only need to add the Mainsail entry explicitly.
- Updates should be applied deliberately during development, never during a
  test run. The `enable_auto_refresh` only checks for updates; it does not
  install them automatically.

#### [announcements]

```ini
[announcements]
subscriptions:
    mainsail
```

Subscribes to Mainsail announcements (release notes, breaking changes).
Low cost, occasionally useful.

### 2.4 Sections NOT Needed

The following Moonraker sections are not needed for the W26 use case:

| Section | Why Not Needed |
|---------|---------------|
| `[webcam]` | No camera on the system (stretch goal at best) |
| `[power]` | No smart power devices controlled by Moonraker |
| `[notifier]` | No push notifications needed |
| `[mqtt]` | No MQTT broker in the architecture |
| `[wled]` | No WLED LED strips |
| `[job_queue]` | No queued print jobs -- bridge daemon controls extrusion in real time |
| `[spoolman]` | No filament/spool tracking |
| `[sensor]` | No external MQTT/HTTP sensors |
| `[timelapse]` | No timelapse camera |

### 2.5 Complete moonraker.conf (Design)

Combining all sections above, the full `moonraker.conf` will be:

```ini
# W26 Cobot Axis -- Moonraker Configuration
# Location: ~/printer_data/config/moonraker.conf

# --- Server ---
[server]
host: 0.0.0.0
port: 7125
klippy_uds_address: /tmp/klippy_uds
max_upload_size: 1024

# --- Authorization ---
[authorization]
trusted_clients:
    127.0.0.1
    127.0.0.0/8
    192.168.0.0/16
    10.0.0.0/8
    172.16.0.0/12
    FE80::/10
    ::1/128
cors_domains:
    http://*.local
    http://*.local:*
    http://localhost
    http://localhost:*
    http://my.mainsail.xyz
    https://my.mainsail.xyz
force_logins: False

# --- File Manager ---
[file_manager]
enable_object_processing: False

# --- Machine Control ---
[machine]
provider: systemd_dbus
shutdown_command: /usr/sbin/shutdown -h now
reboot_command: /usr/sbin/shutdown -r now

# --- Data Store ---
[data_store]
temperature_store_size: 600
gcode_store_size: 1000

# --- History ---
[history]

# --- OctoPrint Compatibility ---
[octoprint_compat]

# --- Update Manager ---
[update_manager]
refresh_interval: 168
enable_auto_refresh: True

[update_manager mainsail]
type: web
channel: stable
repo: mainsail-crew/mainsail
path: ~/mainsail

# --- Announcements ---
[announcements]
subscriptions:
    mainsail
```

---

## 3. Mainsail Configuration Design

### 3.1 Purpose

Mainsail is a static web application that runs in the browser. It connects to
Moonraker's HTTP/WebSocket API to display printer status and send commands.
For W26, it serves as the optional HMI on the Pi400.

Mainsail has two configuration surfaces:
1. **mainsail.cfg** (or `client.cfg`) -- Klipper macros that Mainsail expects.
   This is included from `printer.cfg`.
2. **Mainsail UI settings** -- stored in the browser and/or Moonraker's database.
   Configured through the Mainsail web interface.

### 3.2 mainsail.cfg (Klipper Macros for Mainsail)

The `mainsail-config` project provides a `client.cfg` file with macros that
Mainsail's UI buttons depend on. The key macros are:

| Macro | Mainsail UI Element | W26 Relevance |
|-------|-------------------|---------------|
| `PAUSE` | Pause button | Moderate -- could pause extrusion |
| `RESUME` | Resume button | Moderate -- resume after pause |
| `CANCEL_PRINT` | Cancel button | Moderate -- stop extrusion session |
| `SET_PAUSE_NEXT_LAYER` | Layer-based pause | None -- no layers |
| `SET_PRINT_STATS_INFO` | Layer/file info | None |
| `_CLIENT_VARIABLE` | Internal state | Required if using other macros |

#### What We Need vs. What We Can Skip

For a single-axis pump system, most of the `client.cfg` macros are 3D-printer
specific (park head, retract filament, Z-hop). We have two options:

**Option A: Include mainsail-config as-is (recommended)**

```ini
# In printer.cfg
[include mainsail.cfg]
```

Where `mainsail.cfg` is a symlink or copy of the mainsail-config `client.cfg`.
The macros will exist but many will be no-ops since we have no XYZ axes, no
extruder heater, and no bed. Mainsail will not error, and the UI buttons will
work (even if their behavior is minimal).

Advantages:
- Zero maintenance. Update with `update_manager`.
- Mainsail never complains about missing macros.
- Pause/Resume/Cancel buttons work out of the box.

Disadvantages:
- Contains irrelevant macros (park, Z-hop, filament retract).
- Some macros may fail silently or produce warnings if they reference
  `extruder` or `toolhead` features not present in our config.

**Option B: Write minimal custom macros**

Define only the macros Mainsail requires, tailored to our pump system:

```ini
# mainsail.cfg -- W26 custom macros for Mainsail compatibility
#
# Minimal set: PAUSE, RESUME, CANCEL_PRINT, plus pump-specific macros.

[gcode_macro PAUSE]
description: Pause the pump
rename_existing: BASE_PAUSE
gcode:
    # Stop the pump stepper
    MANUAL_STEPPER STEPPER=pump SET_POSITION={printer["manual_stepper pump"].position}
    RESPOND MSG="Pump paused at position {printer['manual_stepper pump'].position}"
    BASE_PAUSE

[gcode_macro RESUME]
description: Resume the pump
rename_existing: BASE_RESUME
gcode:
    RESPOND MSG="Pump resuming"
    BASE_RESUME

[gcode_macro CANCEL_PRINT]
description: Cancel pump operation
rename_existing: BASE_CANCEL_PRINT
gcode:
    # Disable stepper
    MANUAL_STEPPER STEPPER=pump ENABLE=0
    RESPOND MSG="Pump operation cancelled"
    BASE_CANCEL_PRINT
```

Advantages:
- Clean, purpose-built macros.
- No dead code or irrelevant functionality.

Disadvantages:
- We must maintain it ourselves.
- May miss macros that future Mainsail versions expect.

**Recommendation:** Start with Option A during development. If Mainsail
produces errors or confusing behavior, switch to Option B.

### 3.3 Custom G-Code Macros for Pump Monitoring

Regardless of which mainsail.cfg approach we choose, we should define custom
macros that are useful for monitoring and debugging the pump system:

```ini
# --- W26 Pump Status Macros ---

[gcode_macro PUMP_STATUS]
description: Report pump stepper and TMC2209 status
gcode:
    {% set pump = printer["manual_stepper pump"] %}
    {% set tmc = printer["tmc2209 manual_stepper pump"] %}
    RESPOND MSG="Pump position: {pump.position:.3f} mm"
    RESPOND MSG="TMC run_current: {tmc.run_current}"
    RESPOND MSG="TMC hold_current: {tmc.hold_current}"

[gcode_macro PUMP_ENABLE]
description: Enable the pump stepper
gcode:
    MANUAL_STEPPER STEPPER=pump ENABLE=1
    RESPOND MSG="Pump stepper enabled"

[gcode_macro PUMP_DISABLE]
description: Disable the pump stepper
gcode:
    MANUAL_STEPPER STEPPER=pump ENABLE=0
    RESPOND MSG="Pump stepper disabled"

[gcode_macro PUMP_ZERO]
description: Set current pump position as zero
gcode:
    MANUAL_STEPPER STEPPER=pump SET_POSITION=0
    RESPOND MSG="Pump position zeroed"

[gcode_macro PUMP_TEST]
description: Test pump with a short extrusion
gcode:
    {% set distance = params.D|default(10)|float %}
    {% set speed = params.S|default(10)|float %}
    MANUAL_STEPPER STEPPER=pump ENABLE=1
    MANUAL_STEPPER STEPPER=pump MOVE={distance} SPEED={speed}
    RESPOND MSG="Pump test: {distance} mm at {speed} mm/s"
```

These macros can be invoked from:
- Mainsail's macro buttons in the web UI
- The Moonraker API (`/printer/gcode/script?script=PUMP_STATUS`)
- The klippy Unix socket (bridge daemon)

### 3.4 Mainsail UI Customization

Mainsail stores UI configuration in the browser (localStorage) and in
Moonraker's database. The following customizations should be applied through
the Mainsail web interface after deployment:

#### Dashboard Layout

For a single-axis pump system, the default Mainsail dashboard shows many
irrelevant panels. Customize to show:

| Panel | Action | Rationale |
|-------|--------|-----------|
| Toolhead / Axes | Hide X, Y, Z | We only have the pump axis |
| Temperature | Hide if no sensors | We only have MCU temp sensor |
| Extruder | Hide | We use `manual_stepper`, not `extruder` |
| Webcam | Hide | No camera |
| Bed mesh | Hide | Not applicable |
| Print status | Keep | Shows Klipper state (ready, error, etc.) |
| Console | Keep | G-code console for debugging |
| Macros | Keep | Shows PUMP_STATUS, PUMP_TEST, etc. |
| Machine info | Keep | Shows MCU version, host info |

#### Macro Button Configuration

Mainsail allows grouping macros into categories. Recommended grouping:

- **Pump Control:** PUMP_ENABLE, PUMP_DISABLE, PUMP_ZERO, PUMP_TEST
- **Diagnostics:** PUMP_STATUS, DUMP_TMC (built-in Klipper command)
- **System:** FIRMWARE_RESTART, RESTART (built-in Klipper commands)

#### Console Filters

Add console output filters to reduce noise:
- Filter out `// Klipper state: Ready` (frequent, not actionable)
- Keep `RESPOND` messages (pump status, errors)

### 3.5 What Mainsail Shows for `[manual_stepper]`

Klipper's `manual_stepper` objects expose the following status fields that
Mainsail can display:

| Field | Description | Mainsail Display |
|-------|-------------|-----------------|
| `position` | Current stepper position in mm | Shown in machine panel or via macro |
| `is_homing` | Whether a homing operation is active | Not typically shown |

The `tmc2209 manual_stepper pump` object exposes:

| Field | Description | Mainsail Display |
|-------|-------------|-----------------|
| `run_current` | Configured run current (A) | Via DUMP_TMC or macro |
| `hold_current` | Configured hold current (A) | Via DUMP_TMC or macro |
| `drv_status` | Driver status register | Via DUMP_TMC |
| `mcu_phase_offset` | Phase offset for phase stepping | Internal |

**Limitation:** Mainsail does not have a dedicated UI panel for
`manual_stepper` objects. The stepper position is not shown on the dashboard
by default. To monitor pump position, use either:
1. A custom macro (PUMP_STATUS) invoked from the macro buttons
2. The console (`MANUAL_STEPPER STEPPER=pump` with no args reports position)
3. A custom Mainsail panel (requires Mainsail plugin development -- not worth it)

---

## 4. Integration: Bridge Daemon and Moonraker Coexistence

### 4.1 Shared klippy Socket

Both the bridge daemon and Moonraker connect to the same klippy Unix socket
(`/tmp/klippy_uds`). This is explicitly supported:

> *"Klipper's Unix socket supports multiple simultaneous client connections."*
> -- `docs/klipper_protocols.md`, Section 2.1

There is no conflict. klippy handles concurrent clients via its event loop.
Each client has its own connection, its own `id` counter, and its own
subscription state.

### 4.2 Potential Interaction Issues

| Scenario | Risk | Mitigation |
|----------|------|------------|
| Both send G-code simultaneously | Low risk. klippy serializes commands. A Moonraker command (from Mainsail) could interleave with bridge commands. | Mainsail should be used for monitoring, not control, during operation. Document this for the team. |
| Moonraker issues EMERGENCY_STOP | Affects entire system including bridge. | Expected behavior. E-stop from any source should halt everything. |
| Moonraker restarts klippy (RESTART / FIRMWARE_RESTART) | Drops all socket connections. Bridge daemon must reconnect. | Bridge already has reconnection logic (`_connect_all()`). This is handled. |
| Moonraker is down | No effect on bridge. Bridge connects directly to klippy. | By design. Moonraker is not in the control path. |
| klippy restarts | Both Moonraker and bridge must reconnect. | Both have reconnection logic. |

### 4.3 Operational Discipline

During normal operation (UR30 running an extrusion program):
- **Do not** send G-code commands from Mainsail that could interfere with the
  bridge (e.g., `MANUAL_STEPPER STEPPER=pump MOVE=...`).
- **Safe to use:** PUMP_STATUS, DUMP_TMC, console queries.
- **Safe to use:** Machine info, temperature monitoring, log viewing.
- **Avoid:** Cancel, Pause, Resume buttons while the bridge is actively
  controlling extrusion (these macros may conflict with the bridge's state).

This should be documented in the HMI usage instructions.

### 4.4 Startup Order

The recommended service startup order is:

1. **klippy** (Klipper host) -- must start first, creates `/tmp/klippy_uds`
2. **Moonraker** -- connects to klippy, starts HTTP/WebSocket server
3. **Bridge daemon** -- connects to klippy, enters control loop

If using systemd, configure `After=klipper.service` for both Moonraker and
the bridge daemon. Moonraker's install script already sets this up. The bridge
daemon's systemd unit is at `src/systemd/w26-bridge.service` and declares
`After=klipper.service network.target`.

---

## 5. File Layout and Deployment

### 5.1 Target Directory Structure on the Pi

```
~/printer_data/
    config/
        printer.cfg           # Existing (src/klipper/printer.cfg)
        moonraker.conf        # New (this design)
        mainsail.cfg          # New (mainsail macros include)
    gcodes/                   # virtual_sdcard path (may be ~/gcode_files)
    logs/
        klippy.log
        moonraker.log
    database/                 # Moonraker's internal DB (auto-created)
    systemd/                  # Service unit overrides

~/mainsail/                   # Mainsail static web files (managed by update_manager)
```

### 5.2 Repository File Mapping

| Repo File | Deploy Location | Notes |
|-----------|----------------|-------|
| `src/klipper/printer.cfg` | `~/printer_data/config/printer.cfg` | Copy or symlink |
| `src/klipper/moonraker.conf` (to create) | `~/printer_data/config/moonraker.conf` | Copy or symlink |
| `src/klipper/mainsail.cfg` (to create) | `~/printer_data/config/mainsail.cfg` | Copy or symlink |

### 5.3 printer.cfg Changes Required

The existing `printer.cfg` needs one addition to include the Mainsail macros:

```ini
# Add at top of printer.cfg, after the header comment:
[include mainsail.cfg]
```

This is the only change to `printer.cfg`. All other sections remain as-is.

### 5.4 Installation Method

Two paths:

**Path A: MainsailOS (recommended for simplicity)**

MainsailOS is a pre-built Raspberry Pi OS image with Klipper, Moonraker, and
Mainsail pre-installed. Flash the image, drop in our config files, flash the
SKR Pico, and go.

- Pros: Zero manual dependency installation. Everything works out of the box.
- Cons: Harder to customize the base OS. Image may lag behind latest releases.

**Path B: Manual install via KIAUH**

KIAUH (Klipper Installation And Update Helper) is a shell script that installs
Klipper, Moonraker, and Mainsail on an existing Raspberry Pi OS.

```bash
# On a fresh Raspberry Pi OS Lite:
cd ~
git clone https://github.com/dw-0/kiauh.git
./kiauh/kiauh.sh
# Select: 1) Install
# Select: Klipper, Moonraker, Mainsail
```

- Pros: Full control over OS configuration. Latest packages.
- Cons: More steps. Requires manual verification.

**Recommendation:** Use MainsailOS for initial bring-up. Switch to manual
install only if MainsailOS causes problems.

---

## 6. Security Considerations

### 6.1 Threat Model

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|------------|
| Unauthorized network access | Low (isolated lab network) | High (can control stepper) | Trusted clients list; physical network isolation |
| Unauthorized Mainsail access | Low (lab network) | Medium (can send G-code) | No internet exposure; `force_logins: False` acceptable |
| Moonraker API abuse from internet | None (not internet-routed) | N/A | Network topology prevents this |
| UR30 sends malformed RTDE data | Low | Medium (bridge handles) | Bridge validates all RTDE values; rate clamping |
| Bridge daemon crash during operation | Medium | High (stepper stops) | Klipper watchdog disables stepper after ~5s timeout |

### 6.2 Network Isolation

The entire system (UR30, Pi, SKR Pico, Pi400) should be on a dedicated
network segment that is **not** connected to the internet or the university
network. A simple gigabit switch with no uplink is sufficient.

If the Pi must be on a routed network (e.g., for SSH access from outside the
lab), use a firewall rule to block port 7125 from non-local IPs:

```bash
sudo ufw allow from 192.168.0.0/16 to any port 7125
sudo ufw deny 7125
```

### 6.3 No SSL/TLS

Moonraker supports SSL but we do not configure it. Justification:
- Lab network only, no sensitive data in transit
- Certificate management adds complexity
- The UR30 controller does not support HTTPS for RTDE
- All traffic is on a physically isolated switch

---

## 7. Optional / Future Features

### 7.1 Webcam (Stretch Goal)

If a USB webcam is added for monitoring the extrusion process:

```ini
# Add to moonraker.conf:
[webcam pump_camera]
location: pump
enabled: True
service: mjpegstreamer
target_fps: 15
stream_url: http://localhost:8080/?action=stream
snapshot_url: http://localhost:8080/?action=snapshot
```

Requires installing `mjpg-streamer` or `crowsnest` on the Pi.

### 7.2 Power Device Control

If a smart power relay is added to control the 24V supply:

```ini
# Add to moonraker.conf:
[power pump_24v]
type: gpio
pin: gpiochip0/gpio23    # Pi GPIO pin controlling a relay
initial_state: off
off_when_shutdown: True
locked_while_printing: True
restart_klipper_when_powered: True
restart_delay: 2
```

This allows Moonraker/Mainsail to turn the 24V supply on/off from the web UI.

### 7.3 Neopixel Status LED

The SKR Pico has an onboard Neopixel (gpio24). Could be used for visual
system status (commented out in current `printer.cfg`):

```ini
# In printer.cfg (uncomment and add macros):
[neopixel status_led]
pin: gpio24
chain_count: 1
color_order: GRB
initial_RED: 0.0
initial_GREEN: 0.3
initial_BLUE: 0.0

[gcode_macro SET_STATUS_LED]
gcode:
    {% set r = params.R|default(0)|float %}
    {% set g = params.G|default(0)|float %}
    {% set b = params.B|default(0)|float %}
    SET_LED LED=status_led RED={r} GREEN={g} BLUE={b}
```

Color coding: green = ready, blue = running, red = error, off = disabled.

### 7.4 TMC2209 StallGuard Monitoring via Mainsail

For the stretch goal of torque feedback, the TMC2209 `sg_result` can be
displayed in Mainsail via a custom macro:

```ini
[gcode_macro SG_REPORT]
description: Report StallGuard value
gcode:
    {% set sg = printer["tmc2209 manual_stepper pump"].drv_status %}
    RESPOND MSG="StallGuard report: {sg}"
```

Or use the built-in `DUMP_TMC STEPPER="manual_stepper pump"` command from
the Mainsail console.

### 7.5 Fan Control for TMC2209 Cooling

If the stepper run current is increased above 0.8A:

```ini
# In printer.cfg (uncomment):
[fan]
pin: gpio17
# Fan0 port on SKR Pico -- runs proportional to duty cycle
```

Control from Mainsail's fan panel or via `M106 S255` / `M107` G-code.

---

## 8. Open Questions

| # | Question | Impact | Resolution Path |
|---|----------|--------|-----------------|
| 1 | Which Pi model for the headless control node? | Determines compute budget for running klippy + Moonraker + bridge concurrently | Team decision (Pi 4B recommended, see `todo.md`) |
| 2 | MainsailOS vs manual install? | Affects deployment complexity | Try MainsailOS first; fall back to KIAUH if issues |
| 3 | Should the bridge daemon register `register_remote_method` callbacks with klippy? | Would allow Klipper macros to push events to the bridge (e.g., move complete, stall detected) | Deferred to Phase 3 -- not needed for MVP |
| 4 | Does Mainsail display `manual_stepper` position on the dashboard? | Determines whether we need a custom panel or just macros | Test during deployment -- likely macros only |
| 5 | Should we add the bridge daemon as a Moonraker-managed service? | Would allow start/stop/restart of the bridge from Mainsail | Nice-to-have; add `[machine]` service entry if feasible |
| 6 | `printer_data` directory structure vs legacy flat layout? | Affects config file paths and symlinks | Use `printer_data` (modern standard) |
| 7 | virtual_sdcard path -- `~/gcode_files` vs `~/printer_data/gcodes`? | Must match between `printer.cfg` and Moonraker's expectation | Align with MainsailOS default on deployment |

---

## 9. References

### Moonraker Documentation
- [Moonraker Configuration Reference](https://moonraker.readthedocs.io/en/latest/configuration/)
- [Moonraker Sample Configuration](https://moonraker.readthedocs.io/en/latest/moonraker.conf)
- [Moonraker Installation Guide](https://moonraker.readthedocs.io/en/latest/installation/)
- [Moonraker GitHub Repository](https://github.com/Arksine/moonraker)
- [Moonraker Configuration (GitHub source)](https://github.com/Arksine/moonraker/blob/master/docs/configuration.md)

### Mainsail Documentation
- [Mainsail Configuration](https://docs.mainsail.xyz/setup/configuration)
- [Mainsail Macros Settings](https://docs.mainsail.xyz/overview/settings/macros)
- [mainsail-config Repository (client.cfg)](https://github.com/mainsail-crew/mainsail-config)
- [mainsail-config client.cfg Source](https://github.com/mainsail-crew/mainsail-config/blob/master/client.cfg)
- [Mainsail GitHub Repository](https://github.com/mainsail-crew/mainsail)

### Klipper Documentation
- [Klipper API Server](https://www.klipper3d.org/API_Server.html)
- [Klipper Configuration Reference](https://www.klipper3d.org/Config_Reference.html)

### Project Internal Documents
- Bridge daemon config: `src/bridge/config.py`
- Bridge Klipper client: `src/bridge/klipper_client.py`
- Klipper printer config: `src/klipper/printer.cfg`
- Klipper protocols research: `docs/klipper_protocols.md`
- SKR Pico specs: `docs/skr_pico_specs.md`
- SKR Pico + Klipper setup: `docs/skr_pico_klipper_setup.md`

### Third-Party Tools
- [KIAUH (Klipper Install And Update Helper)](https://github.com/dw-0/kiauh)
- [MainsailOS](https://docs.mainsail.xyz/setup/getting-started/mainsailos)
- [Fluidd moonraker.conf Reference](https://docs.fluidd.xyz/configuration/moonraker_conf)
