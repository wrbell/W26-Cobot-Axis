# Klipper Communication Protocols and API Reference

> Research document for W26-Cobot-Axis project.
> Context: UR30 (URScript/RTDE) --> Pi400 (Klipper host) --> BigTree Pico (RP2040 MCU) --> Stepper Motor.
> This document covers how external software can send commands to Klipper and how Klipper communicates with its MCUs.
>
> **Sources:** Klipper official documentation (klipper3d.org), Moonraker documentation (moonraker.readthedocs.io), Klipper source code (github.com/Klipper3d/klipper). Knowledge current as of mid-2025; verify against latest docs before implementation.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Klipper's API Server (Unix Socket / klippy)](#2-klippers-api-server-unix-socket--klippy)
3. [Moonraker JSON-RPC API](#3-moonraker-json-rpc-api)
4. [Sending G-code Programmatically](#4-sending-g-code-programmatically)
5. [Klipper Serial Protocol (Host to MCU)](#5-klipper-serial-protocol-host-to-mcu)
6. [Bidirectional Communication and Status Feedback](#6-bidirectional-communication-and-status-feedback)
7. [Protocol Summary and Comparison](#7-protocol-summary-and-comparison)
8. [Non-3D-Printer Use Cases and Extensibility](#8-non-3d-printer-use-cases-and-extensibility)
9. [Recommendations for W26 Architecture](#9-recommendations-for-w26-architecture)
10. [Official Documentation Links](#10-official-documentation-links)

---

## 1. Architecture Overview

Klipper is a 3D printer firmware that splits work between a **host process** (klippy, written in Python, running on a Linux SBC like a Raspberry Pi) and one or more **MCU processes** (compiled C firmware running on microcontrollers). The host handles kinematics, G-code parsing, and motion planning; the MCU handles real-time step generation and GPIO control.

```
                     External Client (our URScript bridge)
                            |
                  +---------+---------+
                  |                   |
           Unix Socket          Moonraker (HTTP/WS)
           (direct to klippy)   (wraps klippy API)
                  |                   |
                  +----->  klippy  <--+
                        (Python host process on Pi400)
                            |
                     Klipper Serial Protocol
                     (USB-serial / UART / SPI / CAN)
                            |
                    BigTree Pico (RP2040 MCU)
                            |
                      Stepper Motor Driver
```

There are **three layers** of communication to understand:

| Layer | Protocol | Purpose |
|-------|----------|---------|
| External --> Klipper host | Unix socket (JSON) or Moonraker (HTTP/JSON-RPC/WebSocket) | Send G-code, query status |
| Klipper host --> MCU | Klipper serial protocol (binary, custom) | Step timing, GPIO, sensor reads |
| External --> Moonraker --> klippy | JSON-RPC over HTTP or WebSocket | Full printer management |

---

## 2. Klipper's API Server (Unix Socket / klippy)

### 2.1 Overview

Klipper's host process (klippy) exposes a **Unix domain socket** API server. This is the lowest-level external API and is the interface that Moonraker itself uses to communicate with Klipper. You can also connect to it directly from any process on the same machine.

- **Socket path:** `/tmp/klippy_uds` (default; configurable in klippy startup arguments)
- **Protocol:** Newline-delimited JSON over Unix domain socket
- **Authentication:** None (relies on Unix file permissions)
- **Concurrency:** Supports multiple simultaneous client connections

### 2.2 Request/Response Format

Each message is a single line of JSON terminated by `\x03` (ASCII ETX, end-of-text character). The format follows a simplified JSON-RPC-like convention:

**Request:**
```json
{"id": 123, "method": "info", "params": {}}
```

**Response:**
```json
{"id": 123, "result": {"state_message": "Printer is ready", "hostname": "pi400", ...}}
```

The `id` field correlates requests to responses. Responses without an `id` are asynchronous notifications (subscriptions).

### 2.3 Available API Methods

Key methods available on the klippy Unix socket:

| Method | Description | Params |
|--------|-------------|--------|
| `info` | Returns server info, state, software version | `{}` |
| `emergency_stop` | Immediately halt the printer | `{}` |
| `restart` | Restart klippy host software | `{}` |
| `firmware_restart` | Restart MCU firmware | `{}` |
| `gcode/help` | List available G-code commands | `{}` |
| `gcode/script` | Execute a G-code script | `{"script": "G1 X10 F600"}` |
| `gcode/subscribe_output` | Subscribe to G-code response messages | `{"response_template": {...}}` |
| `objects/list` | List available status objects | `{}` |
| `objects/query` | Query current status of objects | `{"objects": {"toolhead": null, "extruder": ["temperature"]}}` |
| `objects/subscribe` | Subscribe to status object changes | `{"objects": {"toolhead": null}, "response_template": {...}}` |
| `register_remote_method` | Register a method callable from G-code macros | `{"response_template": ..., "remote_method": "name"}` |

### 2.4 Sending G-code via Unix Socket

The most important method for our use case is `gcode/script`:

```json
{"id": 1, "method": "gcode/script", "params": {"script": "G1 E10 F300"}}
```

This executes G-code as if it were sent from a serial console. Multiple commands can be sent in one script, separated by newlines:

```json
{"id": 2, "method": "gcode/script", "params": {"script": "G91\nG1 E5 F300\nG90"}}
```

### 2.5 Python Client Example

```python
import socket
import json

KLIPPY_SOCKET = "/tmp/klippy_uds"

def send_klippy_command(method, params=None):
    """Send a command to klippy via Unix socket and return the response."""
    if params is None:
        params = {}
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(KLIPPY_SOCKET)

    msg = json.dumps({"id": 1, "method": method, "params": params}) + "\x03"
    sock.sendall(msg.encode())

    response = b""
    while b"\x03" not in response:
        response += sock.recv(4096)

    sock.close()
    return json.loads(response.strip(b"\x03"))

# Send G-code
result = send_klippy_command("gcode/script", {"script": "G1 E10 F300"})

# Query toolhead position
result = send_klippy_command("objects/query", {
    "objects": {"toolhead": ["position", "status"]}
})
```

### 2.6 Connection Lifecycle

1. Client connects to the Unix socket.
2. Client can send requests and receive responses.
3. Client can subscribe to status updates (responses arrive asynchronously).
4. Connection persists until the client disconnects or klippy restarts.
5. When klippy restarts, all connections are dropped; clients must reconnect.

---

## 3. Moonraker JSON-RPC API

### 3.1 Overview

Moonraker is a separate Python service that wraps Klipper's klippy API and exposes it over **HTTP** and **WebSocket** interfaces. Moonraker is the standard way web frontends (Mainsail, Fluidd, KlipperScreen) interact with Klipper.

Moonraker connects to klippy via the same Unix socket described above. It adds features like:
- HTTP REST-style endpoints
- WebSocket with JSON-RPC 2.0
- Authentication and authorization
- File management (G-code uploads)
- Update management
- Power device control
- Job queue management
- History tracking
- Announcements and notifications

### 3.2 Transport Options

| Transport | URL | Format | Use Case |
|-----------|-----|--------|----------|
| HTTP POST | `http://<host>:7125/api/...` | REST-like JSON | Simple one-shot commands |
| HTTP POST (JSON-RPC) | `http://<host>:7125/server/jsonrpc` | JSON-RPC 2.0 | Batch commands |
| WebSocket | `ws://<host>:7125/websocket` | JSON-RPC 2.0 | Persistent connection, subscriptions |

Default port is **7125** (configurable in `moonraker.conf`).

### 3.3 Key HTTP Endpoints

#### Printer Status and Control

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/printer/info` | GET | Klipper host info and state |
| `/printer/objects/list` | GET | Available status objects |
| `/printer/objects/query?toolhead` | GET | Query object status |
| `/printer/objects/subscribe` | POST | Subscribe to object updates (WS only) |
| `/printer/gcode/script?script=G28` | POST | Execute G-code |
| `/printer/gcode/help` | GET | List available G-code commands |
| `/printer/emergency_stop` | POST | Emergency stop |
| `/printer/restart` | POST | Restart klippy |
| `/printer/firmware_restart` | POST | Restart MCU firmware |

#### Server Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/server/info` | GET | Moonraker server info |
| `/server/config` | GET | Moonraker configuration |
| `/server/temperature_store` | GET | Cached temperature data |
| `/server/gcode_store` | GET | Cached G-code responses |

### 3.4 JSON-RPC 2.0 via WebSocket

The WebSocket interface is the most capable transport for persistent, bidirectional communication.

**Connect:**
```
ws://pi400.local:7125/websocket
```

**Send G-code:**
```json
{
    "jsonrpc": "2.0",
    "method": "printer.gcode.script",
    "params": {"script": "G1 E10 F300"},
    "id": 1
}
```

**Query status:**
```json
{
    "jsonrpc": "2.0",
    "method": "printer.objects.query",
    "params": {"objects": {"toolhead": null, "extruder": ["temperature", "target"]}},
    "id": 2
}
```

**Subscribe to status updates:**
```json
{
    "jsonrpc": "2.0",
    "method": "printer.objects.subscribe",
    "params": {"objects": {"toolhead": null, "extruder": ["temperature"]}},
    "id": 3
}
```

After subscribing, Moonraker pushes `notify_status_update` messages whenever subscribed fields change:
```json
{
    "jsonrpc": "2.0",
    "method": "notify_status_update",
    "params": [{"toolhead": {"position": [0.0, 0.0, 5.0, 10.0]}}, 1234567890.123]
}
```

### 3.5 HTTP Example (curl)

```bash
# Send G-code
curl -X POST "http://pi400.local:7125/printer/gcode/script?script=G1%20E10%20F300"

# Query toolhead status
curl "http://pi400.local:7125/printer/objects/query?toolhead"

# Get printer info
curl "http://pi400.local:7125/printer/info"
```

### 3.6 Python WebSocket Example

```python
import asyncio
import websockets
import json

async def klipper_client():
    uri = "ws://pi400.local:7125/websocket"
    async with websockets.connect(uri) as ws:
        # Subscribe to toolhead updates
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "printer.objects.subscribe",
            "params": {"objects": {"toolhead": null, "extruder": null}},
            "id": 1
        }))

        # Send G-code
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "printer.gcode.script",
            "params": {"script": "G1 E10 F300"},
            "id": 2
        }))

        # Listen for responses and status updates
        async for message in ws:
            data = json.loads(message)
            if "method" in data and data["method"] == "notify_status_update":
                print(f"Status update: {data['params']}")
            elif "id" in data:
                print(f"Response to {data['id']}: {data.get('result')}")

asyncio.run(klipper_client())
```

### 3.7 Authentication

Moonraker supports optional API key authentication and trusted client configuration:

- **Trusted clients:** IP ranges configured in `moonraker.conf` under `[authorization]` that skip authentication (useful for localhost / same-subnet devices).
- **API key:** Generated token passed as `X-Api-Key` HTTP header or `?token=` query parameter.
- **One-time token:** Short-lived tokens for WebSocket connections.

For our project, configuring the Pi400's IP and the UR30's IP as trusted clients in `moonraker.conf` would be simplest:

```ini
[authorization]
trusted_clients:
    127.0.0.1
    192.168.0.0/24
cors_domains:
    *
```

---

## 4. Sending G-code Programmatically

There are four methods to send G-code to Klipper, ordered from lowest to highest level:

### 4.1 Method 1: klippy Unix Socket (Direct)

- **Access:** Local processes on the Pi400 only
- **Latency:** Lowest (no HTTP overhead)
- **Format:** JSON over Unix domain socket
- **Command:** `{"method": "gcode/script", "params": {"script": "G1 E10 F300"}, "id": 1}`
- **Best for:** A bridge daemon running on the Pi400 that receives RTDE data and forwards to Klipper

### 4.2 Method 2: Moonraker HTTP POST

- **Access:** Any device on the network
- **Latency:** Low (single HTTP request-response)
- **Format:** `POST /printer/gcode/script?script=<gcode>`
- **Best for:** Simple command-response patterns from the UR30

### 4.3 Method 3: Moonraker WebSocket JSON-RPC

- **Access:** Any device on the network
- **Latency:** Very low after initial connection (persistent connection, no HTTP overhead per message)
- **Format:** JSON-RPC 2.0 over WebSocket
- **Best for:** High-frequency commands with status feedback (ideal for our extrusion control)

### 4.4 Method 4: Virtual Serial Port

Klipper can be configured to expose a virtual serial port (`/tmp/printer` by default) that accepts raw G-code text, one command per line. This mimics a traditional serial console connection (like OctoPrint would use).

```bash
echo "G1 E10 F300" > /tmp/printer
```

This is the simplest interface but offers no structured response handling. Not recommended for production use in our project.

### 4.5 Comparison for Our Use Case

| Method | Network Access | Latency | Bidirectional | Structured Response |
|--------|---------------|---------|---------------|-------------------|
| Unix Socket | Local only | ~0.1ms | Yes (subscribe) | Yes (JSON) |
| HTTP POST | Network | ~1-5ms | No | Yes (JSON) |
| WebSocket | Network | ~0.5-2ms | Yes (push) | Yes (JSON-RPC) |
| Virtual Serial | Local only | Variable | No | No |

**Recommendation for W26:** Use a Python bridge daemon on the Pi400 that:
1. Listens for RTDE commands from the UR30 over TCP/IP
2. Translates them to Klipper G-code
3. Sends them via the klippy Unix socket (lowest latency) or Moonraker WebSocket (if status subscriptions are needed)

---

## 5. Klipper Serial Protocol (Host to MCU)

### 5.1 Overview

The communication between the klippy host (Pi400) and the MCU (BigTree Pico / RP2040) uses Klipper's custom **binary serial protocol**. This is an internal protocol -- external applications do not need to speak it directly. It is documented here for completeness and to understand system constraints.

The protocol runs over:
- **USB-CDC serial** (most common; USB cable from Pi to MCU)
- **Hardware UART** (direct TX/RX pins)
- **SPI** (for secondary MCUs)
- **CAN bus** (for CAN-connected toolheads)

For the BigTree Pico connected to a Pi, **USB-CDC serial** is the standard connection.

### 5.2 Protocol Format

Messages are encoded in a compact binary format:

```
<length> <sequence> <content> <crc16>
```

| Field | Size | Description |
|-------|------|-------------|
| `length` | 1 byte | Total message length (including header, 5 minimum) |
| `sequence` | 1 byte | Low 4 bits = sequence number, high 4 bits = retransmit count |
| `content` | variable | One or more encoded commands |
| `crc16` | 2 bytes | CRC-16-CCITT of the entire message |

- Maximum message size: 64 bytes
- Sequence numbers: 0-15 (4-bit), wrapping
- Reliable delivery via ACK/retransmit mechanism

### 5.3 Command Encoding

Commands within the content field use **variable-length integer encoding** (VLQ):
- Values 0-127 encode in 1 byte
- Larger values use continuation bits (MSB = 1 means more bytes follow)
- Strings are length-prefixed

Each command is identified by a **command ID** assigned during the "identify" phase at connection startup. The host and MCU negotiate available commands and their IDs at connection time.

### 5.4 Connection Startup (Identify Phase)

When klippy connects to an MCU:

1. Host sends `identify` commands to read the MCU's command dictionary
2. The dictionary describes all available commands, their parameters, and response formats
3. Host verifies firmware version compatibility
4. Host and MCU synchronize clocks
5. Host begins sending timed commands

The command dictionary is compiled into the MCU firmware at build time. It defines commands like:
- `stepper_config` -- configure a stepper motor
- `queue_step` -- queue stepper movement steps with precise timing
- `set_digital_out` -- set a GPIO pin
- `config_endstop` -- configure endstop pins
- `stepper_get_position` -- query stepper position

### 5.5 Clock Synchronization

Klipper maintains precise clock synchronization between the host and MCU:

- The MCU has its own clock counter (typically from a hardware timer)
- The host periodically sends `get_clock` commands to measure round-trip time
- Clock offset and drift are estimated using a linear regression model
- This allows the host to schedule future events in MCU clock ticks with microsecond precision

This is critical for step timing. The host computes step times in its own timebase, translates them to MCU clock ticks, and sends `queue_step` commands that the MCU executes at the precise tick count.

### 5.6 Step Generation Pipeline

```
G-code --> klippy parser --> kinematic solver --> move planner --> step generator
    --> queue_step commands --> serial protocol --> MCU --> stepper driver pins
```

The host pre-computes steps and queues them on the MCU ~100ms ahead of real time. This provides a timing buffer that absorbs jitter from the Linux host OS while maintaining precise step timing on the MCU.

### 5.7 RP2040-Specific Notes

- Klipper has full support for RP2040-based boards (including the Raspberry Pi Pico and BigTreeTech Pico variants)
- Flash via USB bootloader: hold BOOTSEL, connect USB, copy `klipper.uf2`
- USB serial is the primary connection method
- RP2040 runs at 125 MHz default; Klipper uses one of the hardware timers for its clock
- Supports: GPIO, stepper control, ADC, I2C, SPI, PWM, Neopixel
- Klipper `make menuconfig` target: "Raspberry Pi RP2040"
- BigTreeTech Pico-specific pin mappings are available in the Klipper config reference

### 5.8 Klipper Firmware Build for RP2040

```bash
cd ~/klipper
make menuconfig
# Select: Micro-controller Architecture -> Raspberry Pi RP2040
# Select: Bootloader offset -> No bootloader (or 16KiB for some boards)
# Select: Communication interface -> USB
make

# Flash: put RP2040 in bootloader mode (hold BOOTSEL + reset)
# Copy out/klipper.uf2 to the mounted USB drive
```

---

## 6. Bidirectional Communication and Status Feedback

This section is critical for the W26 project question: **Can Klipper report status/feedback back to an external caller?**

The answer is **yes**, through multiple mechanisms.

### 6.1 Status Object Subscriptions (Recommended)

Klipper exposes real-time printer state through "status objects." These can be queried on-demand or subscribed to for push-based updates.

**Available status objects relevant to our project:**

| Object | Key Fields | Description |
|--------|-----------|-------------|
| `toolhead` | `position`, `homed_axes`, `status`, `max_velocity`, `max_accel` | Current toolhead state |
| `extruder` | `temperature`, `target`, `pressure_advance`, `can_extrude` | Extruder state |
| `stepper_enable` | `steppers` | Which steppers are enabled |
| `motion_report` | `live_position`, `live_velocity`, `live_extruder_velocity` | Real-time motion data |
| `gcode_move` | `gcode_position`, `speed`, `extrude_factor` | G-code coordinate state |
| `print_stats` | `state`, `print_duration`, `filament_used` | Print job statistics |
| `idle_timeout` | `state`, `printing_time` | Idle state tracking |

**Querying via Unix socket:**
```json
{"id": 1, "method": "objects/query", "params": {
    "objects": {
        "motion_report": ["live_position", "live_extruder_velocity"],
        "extruder": ["temperature"]
    }
}}
```

**Subscribing via Moonraker WebSocket:**
```json
{
    "jsonrpc": "2.0",
    "method": "printer.objects.subscribe",
    "params": {"objects": {
        "motion_report": ["live_position", "live_extruder_velocity"],
        "toolhead": ["status"]
    }},
    "id": 1
}
```

Subscribed updates are pushed automatically when values change.

### 6.2 G-code Response Output

When G-code commands produce output (e.g., `M114` reports position, `M105` reports temperature), these responses can be captured:

**Via Unix socket:** Subscribe with `gcode/subscribe_output`
**Via Moonraker WebSocket:** Automatic `notify_gcode_response` notifications

```json
// Notification received after sending M114:
{
    "jsonrpc": "2.0",
    "method": "notify_gcode_response",
    "params": ["X:10.000 Y:0.000 Z:0.000 E:5.000"]
}
```

### 6.3 Custom G-code Macros with Response

Klipper supports custom G-code macros in the config file. These can use `RESPOND` to send messages back to the client, and `{action_respond_info()}` in Jinja2 templates:

```ini
# In printer.cfg
[respond]
# Enables the RESPOND and M118 commands

[gcode_macro REPORT_POSITION]
gcode:
    {% set pos = printer.toolhead.position %}
    RESPOND MSG="POS:{pos[0]:.3f},{pos[1]:.3f},{pos[2]:.3f},{pos[3]:.3f}"
```

The `RESPOND` output is received as a G-code response notification.

### 6.4 register_remote_method (Advanced Bidirectional)

The klippy Unix socket API supports `register_remote_method`, which allows an external client to register a callback that can be invoked from within Klipper G-code macros. This enables Klipper-initiated communication back to external software.

**External client registers a remote method:**
```json
{
    "id": 1,
    "method": "register_remote_method",
    "params": {
        "response_template": {"action": "callback"},
        "remote_method": "notify_ur30"
    }
}
```

**G-code macro invokes the remote method:**
```ini
[gcode_macro NOTIFY_EXTRUSION_COMPLETE]
gcode:
    {action_call_remote_method("notify_ur30", result="done", position=printer.toolhead.position[3])}
```

When this macro runs, the external client receives a message on its socket connection:
```json
{"action": "callback", "result": "done", "position": 10.5}
```

**This is the most powerful mechanism for W26.** It allows Klipper to proactively notify the bridge daemon (which can then relay status to the UR30 via RTDE) when events occur, such as:
- Extrusion move completed
- Endstop triggered
- Error condition detected

### 6.5 Stallguard / TMC Driver Feedback

For the stretch goal of stepper torque feedback, Klipper has built-in support for TMC stepper drivers (TMC2209, TMC2240, TMC5160, etc.) which provide:

- **StallGuard:** Load/torque estimation (available as `driver_SGRESULT` or `driver_SG_RESULT` in status objects)
- **StealthChop/SpreadCycle diagnostics**
- **Driver temperature, current, and error flags**

If the BigTree Pico board uses a TMC driver, these values are queryable via the status object system:

```json
{"id": 1, "method": "objects/query", "params": {
    "objects": {"tmc2209 extruder": ["drv_status", "driver_SGRESULT"]}
}}
```

This data could be relayed back to the UR30 via RTDE as a custom variable.

---

## 7. Protocol Summary and Comparison

| Interface | Transport | Format | Scope | Latency | Bidirectional | Best For |
|-----------|-----------|--------|-------|---------|---------------|----------|
| klippy Unix socket | Unix domain socket | JSON + `\x03` | Local | Lowest (~0.1ms) | Yes (subscribe + remote methods) | Bridge daemon on Pi400 |
| Moonraker HTTP | TCP/HTTP | REST JSON | Network | Low (~1-5ms) | No (request-response) | Simple one-shot commands |
| Moonraker WebSocket | TCP/WebSocket | JSON-RPC 2.0 | Network | Low (~0.5-2ms) | Yes (subscriptions + notifications) | Persistent control connection |
| Moonraker JSON-RPC POST | TCP/HTTP | JSON-RPC 2.0 | Network | Low (~1-5ms) | No | Batch commands |
| Virtual serial port | File I/O | Raw G-code text | Local | Variable | No | Legacy / simple scripting |
| Klipper serial (to MCU) | USB/UART/SPI/CAN | Binary (custom) | Internal | ~us | Yes (commands + responses) | Internal host-MCU only |

---

## 8. Non-3D-Printer Use Cases and Extensibility

### 8.1 Klipper as a General Motion Controller

Klipper is architecturally suitable for non-3D-printer applications because:

- **Configurable kinematics:** Supports cartesian, corexy, delta, polar, and `none` (for custom setups). A single-axis extrusion system maps trivially.
- **Standalone stepper control:** You can define stepper motors independently of any kinematic model using `[manual_stepper]` or `[extruder]` config sections.
- **G-code macros:** The Jinja2-based macro system allows defining custom commands that map to any motion sequence.
- **Multiple MCU support:** Can control multiple microcontrollers simultaneously from one host, each with its own serial connection.

### 8.2 `[manual_stepper]` for Independent Axis Control

For our project, `[manual_stepper]` may be more appropriate than `[extruder]` since we want direct position/velocity control from the UR30 rather than sliced G-code:

```ini
# In printer.cfg
[manual_stepper extrusion_axis]
step_pin: gpio2
dir_pin: gpio3
enable_pin: !gpio4
microsteps: 16
rotation_distance: 40  # mm per full rotation
velocity: 50            # mm/s default
accel: 100              # mm/s^2 default
```

Control via G-code:
```gcode
MANUAL_STEPPER STEPPER=extrusion_axis ENABLE=1
MANUAL_STEPPER STEPPER=extrusion_axis MOVE=10 SPEED=25
MANUAL_STEPPER STEPPER=extrusion_axis SET_POSITION=0
```

### 8.3 Custom Klipper Modules (klippy extras)

Klipper supports custom Python modules placed in `~/klipper/klippy/extras/`. These can:

- Define new G-code commands
- Register status objects (queryable/subscribable)
- Interact with MCU pins directly
- Implement custom communication protocols

A custom module for our project might:
- Parse incoming RTDE-formatted commands
- Translate UR30 extrusion parameters to stepper moves
- Report stepper status back in a format the UR30 expects

**Example skeleton for a custom klippy extra:**

```python
# ~/klipper/klippy/extras/ur30_bridge.py

class UR30Bridge:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')

        # Register custom G-code commands
        self.gcode.register_command(
            'UR30_EXTRUDE', self.cmd_UR30_EXTRUDE,
            desc="Extrude command from UR30"
        )

        # Register status reporting
        self.position = 0.0
        self.velocity = 0.0

    def cmd_UR30_EXTRUDE(self, gcmd):
        distance = gcmd.get_float('D', 0.)
        speed = gcmd.get_float('S', 10.)
        # ... translate to stepper motion ...
        self.position += distance
        gcmd.respond_info(f"Extruded {distance}mm at {speed}mm/s")

    def get_status(self, eventtime):
        return {
            'position': self.position,
            'velocity': self.velocity,
        }

def load_config(config):
    return UR30Bridge(config)
```

Config entry:
```ini
[ur30_bridge]
# Custom config options here
```

### 8.4 Existing Non-Printer Projects Using Klipper

Klipper has been adopted for various CNC and motion control projects beyond 3D printing:

- **CNC routers and mills:** Community configs exist for GRBL-style CNC machines running Klipper
- **Laser cutters/engravers:** Klipper supports PWM laser control
- **Pick-and-place machines:** The multi-extruder and toolchanger support has been adapted
- **Pen plotters:** Simple 2-axis + servo configurations
- **Klipper as a general stepper controller:** Multiple community members use Klipper's precise step timing for robotics and automation applications

The key advantage of Klipper for our use case over bare-metal RP2040 firmware is:

1. **Proven, tested step timing** with microsecond precision
2. **Pre-built communication stack** (we get the Unix socket API and Moonraker for free)
3. **Configuration-based setup** (no firmware development needed for basic stepper control)
4. **Status reporting infrastructure** already built in

### 8.5 Danger-Klipper (Kalico) and Extended Features

The community fork "Danger-Klipper" (also known as Kalico) extends Klipper with additional features. While not necessary for our project, it demonstrates the extensibility of Klipper's architecture for non-standard use cases. It adds features like multi-axis homing, additional kinematics types, and extended macro capabilities.

---

## 9. Recommendations for W26 Architecture

Based on this research, here is the recommended communication architecture for the W26-Cobot-Axis project.

### 9.1 Recommended Architecture

```
UR30 Controller                Pi400                              BigTree Pico (RP2040)
+---------------+    RTDE     +---------------------------+      +-------------------+
|               |   TCP/IP    |  RTDE Bridge Daemon       | USB  |                   |
|  URScript     |<----------->|  (Python)                 |Serial|  Klipper MCU      |
|  Program      |   ethernet  |    |                      |----->|  Firmware          |
|               |             |    v                      |      |    |              |
+---------------+             |  klippy Unix Socket       |      |    v              |
                              |  (/tmp/klippy_uds)        |      |  Stepper Driver   |
                              |    |                      |      |  Pins             |
                              |    v                      |      +-------------------+
                              |  klippy (Klipper host)    |
                              |    |                      |
                              |  Moonraker (optional,     |
                              |    for web UI monitoring)  |
                              +---------------------------+
```

### 9.2 Bridge Daemon Design

The central piece of custom software is a **Python bridge daemon** running on the Pi400:

1. **RTDE listener:** Uses the `ur_rtde` Python library to connect to the UR30 controller and read/write RTDE registers
2. **Klipper interface:** Connects to klippy via Unix socket at `/tmp/klippy_uds`
3. **Command translation:** Maps RTDE register values to Klipper G-code or `MANUAL_STEPPER` commands
4. **Status feedback:** Subscribes to Klipper status objects and writes position/velocity/error data back to RTDE output registers

```python
# Conceptual bridge daemon pseudocode
import ur_rtde
import klippy_socket

rtde = ur_rtde.RTDEReceive("192.168.0.3")  # UR30 IP
rtde_io = ur_rtde.RTDEIOInterface("192.168.0.3")
klipper = klippy_socket.connect("/tmp/klippy_uds")

# Subscribe to stepper status
klipper.subscribe({"motion_report": ["live_extruder_velocity"],
                    "toolhead": ["position"]})

while True:
    # Read extrusion command from UR30 RTDE registers
    target_pos = rtde.getActualDigitalOutputBits()  # or custom register
    target_vel = rtde.getSpeedScaling()              # or custom register

    # Send to Klipper
    klipper.gcode(f"MANUAL_STEPPER STEPPER=extrusion_axis MOVE={target_pos} SPEED={target_vel}")

    # Read Klipper status and write back to UR30
    status = klipper.query_status()
    rtde_io.setStandardDigitalOutput(0, status['position'])
```

### 9.3 Klipper Configuration for Single-Axis Extrusion

Minimal `printer.cfg` for the BigTree Pico acting as a single extrusion axis:

```ini
[mcu]
serial: /dev/serial/by-id/usb-Klipper_rp2040_XXXXXXXXXXXX-if00
# Find actual device path with: ls /dev/serial/by-id/

[manual_stepper extrusion_axis]
step_pin: gpio2       # Verify against BigTree Pico pinout
dir_pin: gpio3
enable_pin: !gpio4
microsteps: 16
rotation_distance: 40  # Calculate: (full_steps * microsteps) / steps_per_mm
velocity: 50
accel: 200

[respond]
# Enables RESPOND command for sending messages back to API clients

# Klipper requires a virtual printer definition even for non-printer use
[printer]
kinematics: none
max_velocity: 100
max_accel: 500

[virtual_sdcard]
path: ~/gcode_files

[idle_timeout]
timeout: 3600  # 1 hour before auto-shutdown
```

### 9.4 Latency Considerations

Estimated end-to-end latency for a command from URScript to stepper movement:

| Segment | Estimated Latency | Notes |
|---------|------------------|-------|
| UR30 --> Pi400 (RTDE/TCP) | 2-8 ms | Ethernet, depends on RTDE cycle time (default 8ms/125Hz) |
| RTDE bridge processing | <1 ms | Python on Pi400 |
| Bridge --> klippy (Unix socket) | <0.5 ms | Local IPC |
| klippy processing + motion planning | 1-5 ms | Depends on move complexity |
| klippy --> MCU (serial protocol) | <1 ms | USB serial |
| MCU step execution buffer | ~100 ms lookahead | Steps are pre-queued; actual execution is precise |
| **Total pipeline** | **~5-15 ms** + buffer | Moves execute precisely after buffer delay |

The ~100ms lookahead buffer means the stepper timing is extremely precise (microsecond-level), but there is an inherent latency between command issuance and physical motion. For extrusion control synchronized with robot arm movement, this latency must be characterized and compensated for. Options:

- **Time-shift commands:** Send extrusion commands ~100ms ahead of the corresponding robot arm position
- **Tune the lookahead buffer:** Klipper's `MOVE_QUEUE_SIZE` and other parameters can reduce this, though at the cost of potential stuttering
- **Use Klipper's `SET_VELOCITY_LIMIT`** to adjust acceleration/velocity in real-time

### 9.5 Do We Need the Slave Pi?

Based on this research, **the Slave Pi mentioned in the original architecture may not be necessary.** Klipper is designed to run the host (klippy) on one Linux SBC and communicate directly with the MCU over USB serial. The standard deployment is:

```
Pi400 (klippy host) --USB--> BigTree Pico (MCU firmware)
```

No intermediate Pi is needed. The Pi400 can simultaneously:
1. Run the RTDE bridge daemon (receiving UR30 commands)
2. Run klippy (Klipper host process)
3. Run Moonraker (for optional web monitoring)
4. Connect directly to the BigTree Pico via USB

The Slave Pi was likely proposed as a "comms bridge," but Klipper's architecture already handles this. Eliminating it simplifies the system and removes one source of latency.

---

## 10. Official Documentation Links

### Klipper Core Documentation
- Klipper home: https://www.klipper3d.org/
- API Server (Unix socket): https://www.klipper3d.org/API_Server.html
- MCU Serial Protocol: https://www.klipper3d.org/Protocol.html
- G-code Commands Reference: https://www.klipper3d.org/G-Codes.html
- Configuration Reference: https://www.klipper3d.org/Config_Reference.html
- Manual Stepper: https://www.klipper3d.org/Config_Reference.html#manual_stepper
- TMC Driver Config: https://www.klipper3d.org/TMC_Drivers.html
- RPi as Secondary MCU: https://www.klipper3d.org/RPi_microcontroller.html
- SDCard Updates (RP2040 flashing): https://www.klipper3d.org/SDCard_Updates.html

### Moonraker Documentation
- Moonraker docs: https://moonraker.readthedocs.io/en/latest/
- Web API reference: https://moonraker.readthedocs.io/en/latest/web_api/
- Configuration: https://moonraker.readthedocs.io/en/latest/configuration/
- GitHub: https://github.com/Arksine/moonraker

### Klipper Source Code
- Main repository: https://github.com/Klipper3d/klipper
- klippy extras (Python modules): https://github.com/Klipper3d/klipper/tree/master/klippy/extras
- MCU protocol code: https://github.com/Klipper3d/klipper/blob/master/klippy/serialhdl.py
- RP2040 MCU code: https://github.com/Klipper3d/klipper/tree/master/src/rp2040
- Command dictionary: https://github.com/Klipper3d/klipper/blob/master/klippy/msgproto.py

### UR RTDE (for bridge daemon)
- RTDE Guide: https://www.universal-robots.com/articles/ur/interface-communication/real-time-data-exchange-rtde-guide/
- ur_rtde Python library: https://sdurobotics.gitlab.io/ur_rtde/

### Community Resources
- Klipper Discord: https://discord.klipper3d.org/
- Danger-Klipper (Kalico) fork: https://github.com/KalicoCrew/kalico

---

*Document prepared for W26-Cobot-Axis project, ME472 Mechatronics capstone.*
*Last updated: 2025-02-12.*
