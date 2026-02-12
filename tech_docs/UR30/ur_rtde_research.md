# Universal Robots RTDE Research Document

**Project:** W26 Cobot Axis -- UR30 to Raspberry Pi 400 (Klipper) External Stepper Axis
**Author:** Willem (Software/EE)
**Date:** February 2026
**Course:** ME 472 -- Mechatronics, Winter 2026

---

## Table of Contents

1. [RTDE Protocol Overview](#1-rtde-protocol-overview)
2. [UR Official & Community Python Libraries](#2-ur-official--community-python-libraries)
3. [RTDE Input/Output Registers](#3-rtde-inputoutput-registers)
4. [Alternative UR Communication Protocols](#4-alternative-ur-communication-protocols)
5. [URCaps Overview](#5-urcaps-overview)
6. [Latency Considerations for Coordinated Extrusion Control](#6-latency-considerations-for-coordinated-extrusion-control)
7. [Existing Projects Bridging UR Robots to External Stepper/Extrusion Systems](#7-existing-projects-bridging-ur-robots-to-external-stepperextrusion-systems)
8. [Recommendations for W26 Architecture](#8-recommendations-for-w26-architecture)
9. [References & Links](#9-references--links)

---

## 1. RTDE Protocol Overview

### What Is RTDE?

RTDE (Real-Time Data Exchange) is a TCP/IP-based communication interface provided by Universal Robots for synchronous, low-latency data exchange between an external application and the UR controller. It was introduced in controller software version 3.4 (CB3) and is available on all e-Series and newer robots, including the UR30.

RTDE replaces the older approach of parsing the 1800-byte binary state packets from the Primary/Secondary/Real-Time interfaces. It provides a structured, subscription-based protocol where the external client defines exactly which data fields ("recipes") it wants to read or write.

**Official documentation:**
- https://www.universal-robots.com/articles/ur/interface-communication/real-time-data-exchange-rtde-guide/

### How It Works

RTDE follows a client-server model over TCP port **30004**:

1. **Connection:** The external client opens a TCP connection to the robot controller on port 30004.
2. **Protocol Negotiation:** Client and server negotiate protocol version (currently version 2).
3. **Recipe Setup:** The client sends "setup" messages declaring:
   - **Output recipe:** Which robot state variables the client wants to *read* (e.g., actual joint positions, TCP pose, digital I/O states).
   - **Input recipe:** Which registers the client wants to *write* (e.g., general-purpose registers, digital output commands).
4. **Start Synchronization:** The client sends a "start" command. The controller then begins streaming output data at a fixed cycle rate.
5. **Steady-State Exchange:** On each controller cycle, the robot sends the requested output fields. The client can send input data at any time; the controller applies it on the next cycle.
6. **Pause/Resume:** The client can pause and resume synchronization without disconnecting.

### Data Exchange Model

```
                    TCP Port 30004
  UR30 Controller  <=================>  External Client (Pi400)
       |                                       |
       |  [Output Recipe: robot state data]    |
       | ------------------------------------> |
       |    (sent every controller cycle)       |
       |                                       |
       |  [Input Recipe: commands/registers]    |
       | <------------------------------------ |
       |    (sent asynchronously by client)     |
       |                                       |
```

- **Outputs** (robot to client): Read-only. The controller pushes data at the controller cycle rate.
- **Inputs** (client to robot): Write-only. The client sends data which the controller applies on the next cycle.
- Data is exchanged as binary-packed fields. Each recipe has an associated ID for demultiplexing.

### Synchronization & Cycle Times

The UR controller runs an internal real-time control loop:

| Robot Series | Control Loop Frequency | Cycle Time |
|---|---|---|
| CB3 (UR3/5/10) | 125 Hz | 8 ms |
| e-Series (UR3e/5e/10e/16e/20e/30e) | 500 Hz | 2 ms |

The UR30 is an e-Series robot, so **RTDE output data is streamed at 500 Hz (every 2 ms)**. This is the maximum rate; the client can choose to process at a lower rate but the controller always streams at the full rate.

### Typical Round-Trip Latency

The total latency from "client writes an input" to "robot acts on it and reports updated state" involves:

| Component | Typical Latency |
|---|---|
| Network transmission (Ethernet, direct or via switch) | 0.1 -- 0.5 ms |
| RTDE protocol processing (controller side) | < 0.5 ms |
| Controller cycle alignment (worst case: just missed a cycle) | 0 -- 2 ms |
| Total round-trip (write input, read next output) | ~2 -- 4 ms |

For a direct Ethernet connection (no switch), typical observed round-trip latency is **2 -- 5 ms**. Adding a gigabit switch introduces negligible additional latency (< 0.1 ms for a modern managed switch).

### Protocol Packet Types

| Type | Direction | Description |
|---|---|---|
| `RTDE_REQUEST_PROTOCOL_VERSION` | Client -> Server | Negotiate protocol version |
| `RTDE_GET_URCONTROL_VERSION` | Client -> Server | Query controller software version |
| `RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS` | Client -> Server | Define output recipe |
| `RTDE_CONTROL_PACKAGE_SETUP_INPUTS` | Client -> Server | Define input recipe |
| `RTDE_CONTROL_PACKAGE_START` | Client -> Server | Start synchronization |
| `RTDE_CONTROL_PACKAGE_PAUSE` | Client -> Server | Pause synchronization |
| `RTDE_DATA_PACKAGE` | Bidirectional | Actual data payload |

---

## 2. UR Official & Community Python Libraries

### 2.1 UR's Official RTDE Python Client

Universal Robots provides an official Python RTDE client library as sample code. It is available on their GitHub:

- **Repository:** https://github.com/UniversalRobots/RTDE_Python_Client_Library
- **License:** BSD-style
- **Python version:** Python 2.7 / 3.x compatible

#### Installation

```bash
# Clone the repository
git clone https://github.com/UniversalRobots/RTDE_Python_Client_Library.git

# Or install via pip (if packaged)
pip install ur-rtde  # Note: this is the C++ library's Python bindings, see below

# For the official UR Python client, copy rtde.py into your project
cp RTDE_Python_Client_Library/rtde/rtde.py /your/project/
```

#### Basic Usage Pattern

The official library uses XML configuration files to define recipes. Here is the essential flow:

**Configuration file (`rtde_configuration.xml`):**
```xml
<?xml version="1.0"?>
<rtde_config>
    <recipe key="out">
        <field name="actual_TCP_pose" type="VECTOR6D"/>
        <field name="actual_q" type="VECTOR6D"/>
        <field name="runtime_state" type="UINT32"/>
        <field name="output_int_register_0" type="INT32"/>
        <field name="output_double_register_0" type="DOUBLE"/>
        <field name="actual_digital_output_bits" type="UINT64"/>
    </recipe>
    <recipe key="in">
        <field name="input_int_register_0" type="INT32"/>
        <field name="input_double_register_0" type="DOUBLE"/>
        <field name="input_bit_register_64" type="BOOL"/>
    </recipe>
</rtde_config>
```

**Python client code (official library style):**
```python
import rtde.rtde as rtde
import rtde.rtde_config as rtde_config

ROBOT_HOST = "192.168.1.100"  # UR30 IP address
ROBOT_PORT = 30004
CONFIG_FILE = "rtde_configuration.xml"

# Parse configuration
conf = rtde_config.ConfigFile(CONFIG_FILE)
output_names, output_types = conf.get_recipe("out")
input_names, input_types = conf.get_recipe("in")

# Connect to robot
con = rtde.RTDE(ROBOT_HOST, ROBOT_PORT)
con.connect()

# Get controller version
con.get_controller_version()

# Setup recipes
con.send_output_setup(output_names, output_types)
input_setup = con.send_input_setup(input_names, input_types)

# Start synchronization
con.send_start()

# Main loop
try:
    while True:
        # Receive robot state (outputs)
        state = con.receive()
        if state is not None:
            tcp_pose = state.actual_TCP_pose    # [x, y, z, rx, ry, rz]
            joint_pos = state.actual_q           # [q0, q1, q2, q3, q4, q5]

            # Write to input registers (client -> robot)
            input_setup.input_int_register_0 = 42
            input_setup.input_double_register_0 = 3.14
            input_setup.input_bit_register_64 = True
            con.send(input_setup)
except KeyboardInterrupt:
    con.send_pause()
    con.disconnect()
```

### 2.2 SDU ur_rtde Library (C++ with Python Bindings)

The SDU (University of Southern Denmark) `ur_rtde` library is a widely-used, higher-performance alternative with both C++ and Python APIs. It wraps the RTDE protocol with a more ergonomic interface and adds robot control functions.

- **Documentation:** https://sdurobotics.gitlab.io/ur_rtde/
- **Repository:** https://gitlab.com/sdurobotics/ur_rtde
- **PyPI:** `pip install ur-rtde`
- **License:** MIT

#### Installation

```bash
pip install ur-rtde

# On Raspberry Pi (ARM), may need to build from source:
sudo apt-get install libboost-all-dev
pip install ur-rtde
```

#### Key Classes

| Class | Purpose |
|---|---|
| `RTDEControlInterface` | Send motion commands and control the robot (movej, movel, speedl, etc.) |
| `RTDEReceiveInterface` | Subscribe to and read robot state data |
| `RTDEIOInterface` | Control digital/analog I/O |
| `DashboardClient` | Access dashboard server commands (power, brake release, load program) |

#### Example: Reading Robot State

```python
import rtde_receive
import time

# Connect to robot and subscribe to state data
rtde_r = rtde_receive.RTDEReceiveInterface("192.168.1.100")

while True:
    # Read current joint positions (radians)
    q = rtde_r.getActualQ()
    print(f"Joint positions: {q}")

    # Read TCP pose [x, y, z, rx, ry, rz] (meters, radians)
    tcp = rtde_r.getActualTCPPose()
    print(f"TCP pose: {tcp}")

    # Read TCP speed
    tcp_speed = rtde_r.getActualTCPSpeed()

    # Read digital outputs
    digital_out = rtde_r.getActualDigitalOutputBits()

    # Read general-purpose output registers
    int_val = rtde_r.getOutputIntRegister(0)
    double_val = rtde_r.getOutputDoubleRegister(0)

    time.sleep(0.002)  # Match 500 Hz cycle
```

#### Example: Writing Input Registers (for URScript to read)

```python
import rtde_control
import rtde_io

# Control interface (also writes registers)
rtde_c = rtde_control.RTDEControlInterface("192.168.1.100")

# IO interface
rtde_io_ctrl = rtde_io.RTDEIOInterface("192.168.1.100")

# Write to general-purpose integer register (accessible in URScript)
rtde_c.setInputIntRegister(0, 100)       # write_input_integer_register(0) in URScript
rtde_c.setInputDoubleRegister(0, 3.14)   # write_input_float_register(0) in URScript

# Set digital outputs
rtde_io_ctrl.setStandardDigitalOut(0, True)   # Set digital out 0 HIGH
rtde_io_ctrl.setToolDigitalOut(0, True)       # Set tool digital out 0 HIGH

# Set analog outputs
rtde_io_ctrl.setStandardAnalogOut(0, 0.5)     # Set analog out 0 to 0.5
```

#### Example: URScript Reading RTDE Input Registers

On the robot side, a URScript program reads the values written by the external client:

```urscript
# URScript running on UR30
while True:
    # Read integer register written by external client via RTDE
    extrusion_speed = read_input_integer_register(0)

    # Read float register
    extrusion_rate = read_input_float_register(0)

    # Read boolean register
    extrusion_enable = read_input_boolean_register(64)

    # Use the values to control behavior
    if extrusion_enable:
        # Set a digital output to signal the stepper controller
        set_standard_digital_out(0, True)

        # Write current robot speed to output register for client to read
        tcp_speed = get_actual_tcp_speed()
        write_output_float_register(0, norm(tcp_speed))
    else:
        set_standard_digital_out(0, False)
    end

    sync()  # Synchronize with controller cycle
end
```

### 2.3 Library Comparison

| Feature | UR Official Python | SDU ur_rtde |
|---|---|---|
| Language | Pure Python | C++ with Python bindings |
| Performance | Good for most use cases | Better, lower overhead |
| API style | Low-level, recipe-based | High-level, method-based |
| Motion commands | No (protocol only) | Yes (movej, movel, speedl, etc.) |
| I/O control | Via registers | Dedicated IO class |
| Raspberry Pi support | Yes (pure Python) | Yes (may need build from source on ARM) |
| Maintenance | Official but minimal updates | Actively maintained community project |
| **Recommendation for W26** | **Simpler, lower dependency** | **More capable, better API** |

---

## 3. RTDE Input/Output Registers

### 3.1 Output Fields (Robot -> Client, Read-Only)

These are values the external client can subscribe to read:

#### Robot State

| Field Name | Type | Description |
|---|---|---|
| `timestamp` | DOUBLE | Time elapsed since controller start (s) |
| `target_q` | VECTOR6D | Target joint positions (rad) |
| `target_qd` | VECTOR6D | Target joint velocities (rad/s) |
| `target_qdd` | VECTOR6D | Target joint accelerations (rad/s^2) |
| `target_current` | VECTOR6D | Target joint currents (A) |
| `target_moment` | VECTOR6D | Target joint torques (Nm) |
| `actual_q` | VECTOR6D | Actual joint positions (rad) |
| `actual_qd` | VECTOR6D | Actual joint velocities (rad/s) |
| `actual_current` | VECTOR6D | Actual joint currents (A) |
| `joint_control_output` | VECTOR6D | Joint control currents (A) |
| `actual_TCP_pose` | VECTOR6D | Actual TCP pose [x,y,z,rx,ry,rz] (m, rad) |
| `actual_TCP_speed` | VECTOR6D | Actual TCP speed (m/s, rad/s) |
| `actual_TCP_force` | VECTOR6D | Generalized forces at TCP (N, Nm) |
| `target_TCP_pose` | VECTOR6D | Target TCP pose (m, rad) |
| `target_TCP_speed` | VECTOR6D | Target TCP speed (m/s, rad/s) |
| `actual_momentum` | DOUBLE | Norm of Cartesian momentum (Nm*s) |

#### I/O States

| Field Name | Type | Description |
|---|---|---|
| `actual_digital_input_bits` | UINT64 | Current state of digital inputs (bit-packed) |
| `actual_digital_output_bits` | UINT64 | Current state of digital outputs (bit-packed) |
| `standard_analog_input0` | DOUBLE | Standard analog input 0 value |
| `standard_analog_input1` | DOUBLE | Standard analog input 1 value |
| `standard_analog_output0` | DOUBLE | Standard analog output 0 value |
| `standard_analog_output1` | DOUBLE | Standard analog output 1 value |
| `tool_analog_input0` | DOUBLE | Tool flange analog input 0 |
| `tool_analog_input1` | DOUBLE | Tool flange analog input 1 |
| `tool_output_voltage` | INT32 | Tool output voltage (0, 12, or 24V) |
| `tool_output_current` | DOUBLE | Tool output current (A) |
| `tool_temperature` | DOUBLE | Tool temperature (deg C) |
| `tool_mode` | UINT8 | Tool mode |

#### Program/Controller State

| Field Name | Type | Description |
|---|---|---|
| `runtime_state` | UINT32 | Program runtime state |
| `robot_mode` | INT32 | Robot mode (e.g., running, idle, power off) |
| `joint_mode` | VECTOR6INT32 | Joint control modes |
| `safety_mode` | INT32 | Safety mode |
| `safety_status_bits` | INT32 | Safety status bits |
| `robot_status_bits` | UINT32 | Robot status bitmap |
| `speed_scaling` | DOUBLE | Current speed scaling (0.0--1.0) |
| `target_speed_fraction` | DOUBLE | Target speed fraction set by user |
| `actual_execution_time` | DOUBLE | Controller execution time (s) |

#### General-Purpose Output Registers (set by URScript, read by client)

| Field Name | Type | Count |
|---|---|---|
| `output_int_register_0` through `output_int_register_47` | INT32 | 48 registers |
| `output_double_register_0` through `output_double_register_47` | DOUBLE | 48 registers |
| `output_bit_register_64` through `output_bit_register_127` | BOOL | 64 registers |

These are written by URScript using `write_output_integer_register(n, value)`, `write_output_float_register(n, value)`, and `write_output_boolean_register(n, value)`.

### 3.2 Input Fields (Client -> Robot, Write-Only)

These are values the external client can write for URScript to read:

#### General-Purpose Input Registers

| Field Name | Type | Count |
|---|---|---|
| `input_int_register_0` through `input_int_register_47` | INT32 | 48 registers |
| `input_double_register_0` through `input_double_register_47` | DOUBLE | 48 registers |
| `input_bit_register_64` through `input_bit_register_127` | BOOL | 64 registers |

These are read by URScript using `read_input_integer_register(n)`, `read_input_float_register(n)`, and `read_input_boolean_register(n)`.

#### Digital/Analog Output Control (via Input Fields)

| Field Name | Type | Description |
|---|---|---|
| `speed_slider_mask` | UINT32 | Mask for speed slider control |
| `speed_slider_fraction` | DOUBLE | Speed slider value (0.0--1.0) |
| `standard_digital_output_mask` | UINT8 | Mask for which outputs to set |
| `standard_digital_output` | UINT8 | Desired output states |
| `configurable_digital_output_mask` | UINT8 | Mask for configurable outputs |
| `configurable_digital_output` | UINT8 | Desired configurable output states |
| `tool_digital_output_mask` | UINT8 | Mask for tool digital outputs |
| `tool_digital_output` | UINT8 | Desired tool output states |
| `standard_analog_output_mask` | UINT8 | Mask for analog outputs |
| `standard_analog_output_type_0` | UINT8 | Analog output 0 type (current/voltage) |
| `standard_analog_output_type_1` | UINT8 | Analog output 1 type |
| `standard_analog_output_0` | DOUBLE | Analog output 0 value |
| `standard_analog_output_1` | DOUBLE | Analog output 1 value |

### 3.3 Digital I/O Bit Mapping

The UR30 controller has the following physical I/O:

| I/O | Count | Bits in RTDE |
|---|---|---|
| Standard Digital Inputs | 8 (DI0--DI7) | Bits 0--7 of `actual_digital_input_bits` |
| Configurable Digital Inputs | 8 (CI0--CI7) | Bits 8--15 |
| Tool Digital Inputs | 2 (TI0--TI1) | Bits 16--17 |
| Standard Digital Outputs | 8 (DO0--DO7) | Bits 0--7 of `actual_digital_output_bits` |
| Configurable Digital Outputs | 8 (CO0--CO7) | Bits 8--15 |
| Tool Digital Outputs | 2 (TO0--TO1) | Bits 16--17 |

### 3.4 Register Strategy for W26 Project

For the W26 Cobot Axis project, the following register allocation is proposed:

**Inputs (Pi400 -> UR30):**

| Register | Purpose |
|---|---|
| `input_int_register_0` | Stepper status (0=idle, 1=running, 2=error, 3=homing) |
| `input_int_register_1` | Current stepper position (steps) |
| `input_int_register_2` | Stepper error code |
| `input_double_register_0` | Actual extrusion rate (mm/s) |
| `input_double_register_1` | Actual stepper temperature (deg C, if available via Stallguard) |
| `input_bit_register_64` | Stepper ready flag |
| `input_bit_register_65` | Stepper fault flag |

**Outputs (UR30 -> Pi400):**

| Register | Purpose |
|---|---|
| `output_int_register_0` | Commanded extrusion mode (0=off, 1=extrude, 2=retract) |
| `output_int_register_1` | Commanded stepper position target (steps) |
| `output_double_register_0` | Commanded extrusion rate (mm/s) |
| `output_double_register_1` | Current robot TCP speed magnitude (mm/s) |
| `output_double_register_2` | Current robot TCP Z-height (mm) |
| `output_bit_register_64` | Extrusion enable |
| `output_bit_register_65` | Emergency stop / halt extrusion |
| `output_bit_register_66` | Home stepper command |

---

## 4. Alternative UR Communication Protocols

### 4.1 Overview of All UR Interfaces

| Interface | TCP Port | Direction | Frequency | Use Case |
|---|---|---|---|---|
| **RTDE** | 30004 | Bidirectional | 500 Hz (e-Series) | Real-time synchronized data exchange |
| **Primary Interface** | 30001 | Robot -> Client + Client can send URScript | 10 Hz | State monitoring, script injection |
| **Secondary Interface** | 30002 | Robot -> Client + Client can send URScript | 10 Hz | Same as Primary, separate connection |
| **Real-Time Interface** | 30003 | Robot -> Client | 500 Hz (e-Series) | High-frequency state monitoring only |
| **Dashboard Server** | 29999 | Bidirectional (text) | On-demand | Robot power/program management |
| **XML-RPC** | 50000 | Bidirectional | On-demand | Fieldbus gateway simulation |
| **Modbus TCP** | 502 | Bidirectional | On-demand | Industrial PLC integration |
| **PROFINET / EtherNet/IP** | Standard | Bidirectional | ~1 kHz | Industrial fieldbus (requires option) |
| **Socket (URScript)** | User-defined | Bidirectional | Script-limited | Custom TCP communication from URScript |

### 4.2 Dashboard Server (Port 29999)

A simple text-based TCP interface for high-level robot management. Commands are plain ASCII strings terminated by newline.

**Capabilities:**
- Power on/off the robot
- Release/engage brakes
- Load/play/stop/pause programs
- Query robot mode, safety status, program state
- Popup messages on teach pendant
- Set operational mode (manual/automatic)

**Example commands:**
```
power on\n
brake release\n
load /programs/my_program.urp\n
play\n
stop\n
get robot mode\n
```

**Relevance to W26:** Useful for automating startup/shutdown of the UR30 from the Pi400, but **not suitable for real-time data exchange**. Complement RTDE, do not replace it.

### 4.3 Primary/Secondary Interface (Ports 30001/30002)

These interfaces stream a binary packet (~1116 bytes on e-Series) containing complete robot state at 10 Hz. The client can also send URScript commands as plain text strings over these connections, which the robot will execute immediately.

**Key characteristics:**
- 10 Hz update rate (too slow for real-time coordination)
- Can inject URScript commands for immediate execution
- The Secondary interface is identical but on a separate port (allows two independent clients)
- State packet format is versioned and documented but complex to parse

**Relevance to W26:** Could be used for sending URScript commands dynamically, but the 10 Hz rate makes it inadequate for real-time extrusion coordination. **RTDE is superior for this project.**

### 4.4 Real-Time Interface (Port 30003)

Streams the same binary state packet as Primary/Secondary but at the full controller rate (500 Hz on e-Series). However, it is **output-only** -- you can only read state, not write inputs.

**Relevance to W26:** Superseded by RTDE which provides the same 500 Hz rate with bidirectional data exchange and selective field subscription. **Use RTDE instead.**

### 4.5 XML-RPC (Port 50000)

Available from URScript via `rpc_factory()`. Allows URScript to call functions on an external XML-RPC server. This effectively allows the robot program to invoke Python functions on the Pi400.

```urscript
# URScript: Call a function on external XML-RPC server
proxy = rpc_factory("xmlrpc", "http://192.168.1.200:50000")
result = proxy.get_extrusion_rate(tcp_speed)
```

```python
# Python XML-RPC server on Pi400
from xmlrpc.server import SimpleXMLRPCServer

def get_extrusion_rate(tcp_speed):
    return tcp_speed * EXTRUSION_MULTIPLIER

server = SimpleXMLRPCServer(("0.0.0.0", 50000))
server.register_function(get_extrusion_rate)
server.serve_forever()
```

**Characteristics:**
- Synchronous RPC call -- URScript blocks until response returns
- Higher latency than RTDE (HTTP overhead, XML parsing)
- Flexible: can call arbitrary functions with complex arguments
- Good for infrequent, complex operations (e.g., path planning queries)

**Relevance to W26:** Could supplement RTDE for complex operations (e.g., requesting the Pi400 to calculate a new extrusion profile), but **too slow for per-cycle coordination**. RTDE should be the primary real-time channel.

### 4.6 URScript Socket Communication

URScript has built-in socket functions (`socket_open()`, `socket_send_string()`, `socket_read_ascii_float()`, etc.) that allow direct TCP socket communication with external servers.

```urscript
# URScript: Open socket to Pi400
socket_open("192.168.1.200", 12345, "extruder")

while True:
    # Send current TCP speed to Pi400
    tcp_speed = get_actual_tcp_speed()
    speed_mag = norm(tcp_speed)
    socket_send_string(to_str(speed_mag), "extruder")
    socket_send_byte(10, "extruder")  # newline

    # Read response
    response = socket_read_ascii_float(1, "extruder", timeout=0.01)
    if response[0] == 1:
        extrusion_rate = response[1]
    end

    sync()
end
```

**Characteristics:**
- Flexible, custom protocol
- Latency depends on implementation (typically 4--10 ms round-trip)
- String parsing overhead
- Can be unreliable under load (no built-in flow control)
- Maximum of 10 simultaneous sockets in URScript

**Relevance to W26:** A viable alternative to RTDE for simple command passing, but **RTDE is more robust, lower latency, and better documented**. Socket communication could be a fallback option.

### 4.7 Modbus TCP (Port 502)

The UR controller includes a built-in Modbus TCP server. External devices can read/write Modbus registers that map to robot I/O and general-purpose registers.

**Key registers:**

| Address Range | Description |
|---|---|
| 0--7 | Digital outputs |
| 0--7 | Digital inputs (read) |
| 128--255 | General-purpose registers (INT16) |
| 400--455 | General-purpose registers (FLOAT, via two consecutive INT16) |

**Characteristics:**
- Standard industrial protocol
- Wide ecosystem of libraries and tools
- Limited register width (16-bit integers natively)
- Polling-based (client must poll; not pushed)
- Typical cycle: 5--20 ms depending on polling rate

**Relevance to W26:** Modbus is a viable alternative, especially since Klipper or the Pi400 could run a Modbus client. However, **RTDE provides richer data, higher frequency, and lower latency**. Modbus might be useful as a simple secondary channel.

### 4.8 Protocol Comparison for W26 Use Case

| Criterion | RTDE | Primary/Secondary | Socket | XML-RPC | Modbus |
|---|---|---|---|---|---|
| Update Rate | 500 Hz | 10 Hz | Custom | On-demand | ~50--200 Hz |
| Latency | 2--5 ms | ~100 ms | 4--10 ms | 10--50 ms | 5--20 ms |
| Bidirectional | Yes | Partial | Yes | Yes | Yes |
| Rich Robot State | Yes | Yes | No | No | Limited |
| Ease of Use | Medium | Low | Medium | High | Medium |
| Reliability | High | Medium | Medium | Medium | High |
| **Best for W26** | **Yes** | No | Fallback | Supplement | Alternative |

**Conclusion: RTDE is the clear best choice for the primary real-time communication channel.** Dashboard Server should be used alongside for robot lifecycle management. XML-RPC or socket communication can supplement for non-time-critical operations.

---

## 5. URCaps Overview

### What Are URCaps?

URCaps (Universal Robots Capability Plugins) are software plugins that extend the functionality of the UR teach pendant (PolyScope) and robot controller. They allow third-party developers to:

- Add custom nodes to the PolyScope program tree (program nodes)
- Add custom screens for installation/configuration (installation nodes)
- Run background services (daemon processes) on the controller
- Integrate with external hardware seamlessly

**Official documentation:**
- https://www.universal-robots.com/articles/ur/urcaps/
- URCaps SDK: https://www.universal-robots.com/articles/ur/urcaps/urcaps-starter-package/

### How URCaps Are Made

URCaps are developed using the URCap SDK, which is Java-based:

- **Language:** Java (URCap API)
- **Build system:** Maven
- **IDE:** IntelliJ IDEA or Eclipse (with URCap plugin)
- **SDK:** Provided by UR as a starter package
- **Packaging:** `.urcap` file (JAR archive with metadata)
- **Deployment:** Installed via USB stick or SSH to the robot controller

#### URCap Architecture

```
URCap Package (.urcap)
  |
  ├── ProgramNode      -- Custom program tree nodes (Java)
  │     └── Generates URScript snippets inserted into the program
  │
  ├── InstallationNode -- Configuration UI on Installation tab (Java)
  │     └── Stores persistent settings (e.g., IP address, calibration)
  │
  └── Daemon           -- Background process running on controller (any language)
        └── Communicates with external hardware, runs services
```

#### Development Requirements

- Java 8 or later
- URCap SDK (download from UR+)
- URSim (UR simulator) for testing
- Maven for building
- The daemon can be written in any language (Python, C++, etc.) and is packaged as a native executable or script

### Do We Need a URCap for W26?

**Short answer: No, a URCap is not strictly required, but could be beneficial for usability.**

#### Without a URCap (RTDE + URScript approach)

For the W26 project, the architecture can work entirely without a URCap:

1. **Pi400 side:** Python script using ur_rtde or the official RTDE library connects to the UR30 and exchanges data via general-purpose registers.
2. **UR30 side:** A URScript program (`.urp` or `.script`) reads input registers, sends extrusion commands via output registers, and coordinates robot motion with extrusion.
3. **Integration:** The operator loads the URScript program on the teach pendant and runs it. The Pi400 script runs automatically on boot.

**This approach is sufficient for a capstone project** and avoids the complexity of Java development and URCap packaging.

#### With a URCap (enhanced usability)

A URCap would add:
- A custom "Extrude" node in the program tree that the operator drags into their program
- A configuration screen where the operator sets Pi400 IP, extrusion parameters, etc.
- Automatic URScript generation (no manual scripting needed)
- A background daemon that manages the RTDE connection

**This is a stretch goal** -- appropriate if time permits and operator usability is a priority.

#### Recommendation for W26

| Approach | Effort | Usability | Recommendation |
|---|---|---|---|
| RTDE + URScript only | Low | Functional but requires manual setup | **Use this for MVP** |
| RTDE + URScript + URCap | High (Java dev, SDK setup) | Polished, integrated UI | Stretch goal only |

---

## 6. Latency Considerations for Coordinated Extrusion Control

### 6.1 The Latency Budget

For coordinated extrusion (extruder speed proportional to robot TCP speed), the key question is: **how fast must the extrusion rate update in response to changes in robot motion?**

#### Typical 3D Printing / Extrusion Parameters

| Parameter | Typical Value |
|---|---|
| Print speed (TCP linear velocity) | 10 -- 100 mm/s |
| Layer height | 0.2 -- 1.0 mm |
| Nozzle diameter | 0.4 -- 2.0 mm |
| Acceptable position error during speed change | < 1 mm |

#### Latency vs. Extrusion Error

If the extrusion rate lags behind a robot speed change by time `dt`:

```
Position error = |v_new - v_old| * dt
```

For a worst-case speed change of 50 mm/s -> 0 mm/s (sudden stop):

| Latency (dt) | Extrusion error |
|---|---|
| 2 ms | 0.1 mm |
| 5 ms | 0.25 mm |
| 10 ms | 0.5 mm |
| 20 ms | 1.0 mm |
| 50 ms | 2.5 mm |

### 6.2 End-to-End Latency Analysis for W26

The complete signal path for the W26 system:

```
UR30 Controller --[RTDE]--> Pi400 --[Klipper]--> Slave Pi --[Serial]--> BigTree Pico --> Stepper Motor
```

| Segment | Expected Latency | Notes |
|---|---|---|
| UR30 RTDE output | 0 -- 2 ms | Aligned to 500 Hz cycle |
| Ethernet transmission | 0.1 -- 0.5 ms | Direct connection or via switch |
| Pi400 RTDE processing | 0.5 -- 2 ms | Python processing, depends on implementation |
| Pi400 -> Klipper command | 1 -- 5 ms | G-code via Klipper API/socket |
| Klipper -> Slave Pi | 1 -- 5 ms | Klipper MCU communication |
| Slave Pi -> BigTree Pico (Serial) | 1 -- 3 ms | UART at 250 kbaud typical for Klipper |
| BigTree Pico step generation | < 0.1 ms | Hardware timer, negligible |
| Stepper motor response | 0.5 -- 2 ms | Mechanical inertia, depends on load |
| **Total end-to-end** | **~5 -- 20 ms** | **Typical: ~10 ms** |

### 6.3 Is This Fast Enough?

At 10 ms total latency and 50 mm/s print speed:
- Extrusion position error during a speed change: **0.5 mm**
- This is **within acceptable tolerance** for most large-scale robotic 3D printing applications

At the typical print speeds for a UR30 (which moves slower than desktop 3D printers, usually 10--50 mm/s):
- The error is even smaller: **0.1 -- 0.25 mm**

**Conclusion: The latency budget is adequate for this application.** The RTDE 500 Hz cycle is fast enough. The bottleneck will likely be the Klipper communication chain, not RTDE itself.

### 6.4 Latency Mitigation Strategies

1. **Predictive extrusion:** Since the UR30 plans its trajectories in advance, the trajectory target (`target_TCP_speed`) can be used instead of `actual_TCP_speed`. This provides a "look-ahead" that effectively compensates for downstream latency.

2. **Feed-forward from trajectory:** If the URScript program knows the planned motion, it can pre-compute extrusion rates and send them ahead of time via RTDE registers.

3. **Time-shifting G-code:** If the total latency is measured and predictable (e.g., consistently ~10 ms), the Pi400 can issue Klipper commands early by that offset.

4. **Direct serial bypass:** For minimum latency, the Pi400 could bypass Klipper and drive the BigTree Pico's step/direction pins directly via GPIO, though this sacrifices Klipper's motion planning features.

5. **Speed-proportional mode:** Rather than commanding absolute positions, command a speed setpoint to the stepper that is proportional to TCP speed. This naturally handles smooth speed changes without requiring position synchronization.

### 6.5 RTDE Timing Guarantees

Important caveats:

- **RTDE is not hard real-time on the client side.** The UR30 controller runs a real-time OS and guarantees 500 Hz output, but the Pi400 running Linux has no real-time guarantees. Occasional scheduling jitter (1--10 ms) is possible.
- **Solutions:** Use a real-time kernel (PREEMPT_RT) on the Pi400, or use a dedicated thread with high priority for RTDE communication. Klipper already requires PREEMPT_RT, so this may already be configured.
- **The UR controller does not block on RTDE input.** If the client misses a cycle, the controller continues with the last received values. This is safe but means the extrusion rate may be stale for one cycle.

---

## 7. Existing Projects Bridging UR Robots to External Stepper/Extrusion Systems

### 7.1 Robotic 3D Printing with UR Robots

Several research groups and companies have implemented extrusion systems on UR robots:

#### AI Build (Commercial)

- Uses UR robots for large-scale 3D printing
- Custom extruder mounted on UR arm
- Proprietary software for toolpath generation and extrusion control
- Communication via UR interfaces (specifics not public)
- Website: https://ai-build.com/

#### CEAD / CFAM (Continuous Fiber Additive Manufacturing)

- Large-scale composite 3D printing using robot arms
- Custom extruder with pellet-feed system
- UR robots used in some configurations
- Extruder control typically via analog voltage or fieldbus

#### Branch Technology

- Large-scale 3D printing with industrial robots (including UR)
- Custom control software for coordinated extrusion
- Uses robot controller I/O for extruder speed control

### 7.2 Open-Source Projects

#### Grasshopper/KUKA|prc/Robots Plugin

- Grasshopper (Rhino3D) plugins for robotic fabrication
- Primarily KUKA and ABB, some UR support
- Generate robot programs with synchronized extruder commands
- Extrusion typically controlled via analog output or digital I/O

#### ROS-Industrial + Universal Robots

- **ur_robot_driver** (ROS 2 package): Official UR ROS2 driver
  - Uses RTDE internally for state feedback
  - Supports external control mode via `ur_rtde`
  - Repository: https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver
- Could be used on Pi400 (ROS 2 runs on ARM/Raspberry Pi)
- Overhead may be too high for this project's scope

#### Machina.NET / Robots

- .NET-based framework for robotic fabrication
- Supports UR robots
- Includes extruder control primitives
- Probably too heavyweight for embedded use on Pi400

### 7.3 Relevant Research Papers and Projects

- **"Robotic Concrete 3D Printing"** -- Multiple universities have used UR robots with custom extruders controlled via analog outputs or dedicated controllers.
- **"Clay 3D Printing with UR5"** -- Common in architecture/design research. Typically uses a peristaltic pump controlled via UR analog output (0--10V).
- **"FDM 3D Printing on UR Robot Arms"** -- Several maker/research projects mount standard FDM extruders on UR robots. Control approaches vary:
  - Analog output proportional to speed (simplest)
  - Digital I/O for on/off + external speed controller
  - RTDE register exchange with external MCU (most sophisticated, closest to W26 approach)

### 7.4 Key Takeaway for W26

Most existing robotic extrusion projects use one of two approaches:

1. **Analog output approach:** Robot sends 0--10V analog signal proportional to desired extrusion rate. External controller converts voltage to stepper speed. Simple but limited resolution (12-bit DAC = 4096 steps) and no feedback.

2. **Digital communication approach (like W26):** Robot exchanges data with an external controller via RTDE/Ethernet. More complex but allows:
   - Higher resolution commands (32-bit float via RTDE registers)
   - Bidirectional feedback (actual extrusion rate, temperature, errors)
   - Dynamic parameter adjustment
   - Diagnostic data logging

**The W26 architecture (RTDE -> Pi400 -> Klipper -> stepper) is among the more sophisticated approaches** and is well-suited for a mechatronics capstone. The RTDE register exchange approach is proven and documented, and the main engineering challenge is the downstream Klipper integration and end-to-end latency management.

---

## 8. Recommendations for W26 Architecture

### 8.1 Recommended Communication Stack

```
UR30 (URScript)
    |
    | RTDE (TCP port 30004, 500 Hz)
    | - Output registers: extrusion commands, robot speed, enable/disable
    | - Input registers: stepper status, position feedback, error codes
    |
Pi400 (Python + Klipper Host)
    |
    | Klipper API (Unix socket or HTTP)
    |
Klipper MCU chain
    |
    | Serial (UART, 250 kbaud)
    |
BigTree Pico (Klipper firmware)
    |
    | Step/Dir signals
    |
Stepper Motor (Extrusion)
```

### 8.2 Software Components to Develop

| Component | Language | Platform | Description |
|---|---|---|---|
| URScript program | URScript | UR30 | Reads RTDE input registers, writes output registers, coordinates motion with extrusion commands |
| RTDE bridge | Python | Pi400 | Connects to UR30 via RTDE, translates extrusion commands to Klipper G-code |
| Klipper config | Klipper CFG | Pi400 | Configures stepper motor parameters, microstepping, current, acceleration |
| Klipper firmware | C (Klipper) | BigTree Pico | Standard Klipper firmware for RP2040 |

### 8.3 Recommended Library Choice

**Use the SDU `ur_rtde` library** (`pip install ur-rtde`) for the Pi400 RTDE bridge. Rationale:
- Higher-level API reduces development time
- Built-in reconnection handling
- Well-documented with examples
- Active maintenance
- Python bindings work on ARM (Raspberry Pi)

**Fallback:** If `ur_rtde` has build issues on the Pi400 (ARM compilation of C++ dependencies), use the official UR Python RTDE client (pure Python, no compilation needed).

### 8.4 Minimum Viable Prototype (Phase 3 Target)

1. Pi400 connects to UR30 via RTDE and reads `actual_TCP_speed`
2. Pi400 computes extrusion rate = f(TCP_speed) using a simple linear relationship
3. Pi400 sends G-code to Klipper to set stepper speed
4. URScript program moves robot along a predefined path
5. Stepper extrudes proportionally to robot speed

This MVP demonstrates the full communication chain without requiring advanced features like URCaps, Stallguard feedback, or path planning.

---

## 9. References & Links

### Official Universal Robots Documentation

| Resource | URL |
|---|---|
| RTDE Guide | https://www.universal-robots.com/articles/ur/interface-communication/real-time-data-exchange-rtde-guide/ |
| RTDE Python Client (GitHub) | https://github.com/UniversalRobots/RTDE_Python_Client_Library |
| Client Interfaces (overview) | https://www.universal-robots.com/articles/ur/interface-communication/remote-control-via-tcp-ip/ |
| Dashboard Server | https://www.universal-robots.com/articles/ur/dashboard-server-e-series-ur20-ur30/ |
| URScript Manual | https://www.universal-robots.com/articles/ur/urscript/ |
| URCaps Developer Guide | https://www.universal-robots.com/articles/ur/urcaps/ |
| UR30 Product Page | https://www.universal-robots.com/products/ur30-robot/ |
| Primary/Secondary Interface | https://www.universal-robots.com/articles/ur/interface-communication/remote-control-via-tcp-ip/ |

### Community Libraries & Tools

| Resource | URL |
|---|---|
| SDU ur_rtde (C++/Python) | https://sdurobotics.gitlab.io/ur_rtde/ |
| ur_rtde GitLab | https://gitlab.com/sdurobotics/ur_rtde |
| ur_rtde PyPI | https://pypi.org/project/ur-rtde/ |
| UR ROS2 Driver | https://github.com/UniversalRobots/Universal_Robots_ROS2_Driver |
| python-urx (legacy) | https://github.com/SintefManufacturing/python-urx |

### Klipper / Stepper Control

| Resource | URL |
|---|---|
| Klipper Documentation | https://www.klipper3d.org/ |
| Klipper API Reference | https://www.klipper3d.org/API_Server.html |
| BigTreeTech Pico | https://github.com/bigtreetech/BIGTREETECH-Pico |

### Related Research & Projects

| Resource | URL |
|---|---|
| AI Build (robotic 3D printing) | https://ai-build.com/ |
| UR+ Ecosystem | https://www.universal-robots.com/plus/ |
| ROS-Industrial | https://rosindustrial.org/ |

---

*This document was prepared as part of the W26 Cobot Axis project (ME 472, Winter 2026). Information is based on publicly available UR documentation, community library documentation, and established robotics engineering knowledge. URLs should be verified as UR occasionally reorganizes their documentation site.*
