# Trade Study: UR30-to-Pi Communication Protocol

**Project:** W26 Cobot Axis -- ME 472 Winter 2026
**Author:** Willem (Software/EE Lead)
**Date:** 2026-02-12
**Status:** RECOMMENDATION READY
**Originator:** Phase 2 design analysis; protocol selection required before RTDE bridge development begins

---

## 1. Purpose

This trade study evaluates six candidate communication protocols for the real-time data link between the UR30 robot controller and the external Raspberry Pi (Klipper host + RTDE bridge daemon). The Pi translates extrusion commands into Klipper G-code to drive a stepper motor via the SKR Pico.

The communication link must carry:
- **UR30 to Pi:** Extrusion mode, commanded rate, robot TCP speed, enable/disable flags
- **Pi to UR30:** Stepper status, actual extrusion rate, fault flags

| # | Option | Transport | Port |
|---|--------|-----------|------|
| 1 | **RTDE** | TCP | 30004 |
| 2 | **Dashboard Server** | TCP (text) | 29999 |
| 3 | **Primary/Secondary Interface** | TCP (binary + script injection) | 30001 / 30002 |
| 4 | **Modbus TCP** | TCP | 502 |
| 5 | **URScript Socket Communication** | TCP (custom) | User-defined |
| 6 | **XML-RPC** | HTTP | 50000 |

Detailed protocol specifications are drawn from the project research document (`docs/ur_rtde.md`, Sections 4 and 6).

---

## 2. System Context

```
UR30 Controller ──[protocol under evaluation]──> Pi (headless) ──Klipper──> SKR Pico ──> Stepper
   (URScript)         Ethernet / gigabit switch     (bridge daemon)   (serial)    (extrusion)
```

**Key constraint:** The extrusion rate must track robot TCP speed with an end-to-end latency budget of approximately 5--20 ms (see `ur_rtde_research.md`, Section 6.2). At 50 mm/s print speed and 10 ms latency, the positional extrusion error is ~0.5 mm -- acceptable for large-scale metal paste dispensing. The protocol selection therefore prioritizes update rate and latency.

---

## 3. Candidate Descriptions

### 3.1 RTDE (Real-Time Data Exchange)

UR's purpose-built real-time interface. The client subscribes to specific output fields ("recipes") and receives robot state data at the full controller cycle rate -- 500 Hz on e-Series robots (2 ms period). The client can write input registers asynchronously; the controller applies them on the next cycle. Data is binary-packed. Typical round-trip latency is 2--5 ms over Ethernet. Two mature Python libraries exist: the official UR RTDE Python client (pure Python, low-dependency) and the SDU `ur_rtde` library (C++ with Python bindings, higher-level API, MIT license).

### 3.2 Dashboard Server

A text-based TCP interface for high-level robot lifecycle management. Commands are plain ASCII strings (e.g., `power on\n`, `brake release\n`, `load /programs/prog.urp\n`). Responses are single-line text. The interface is designed for robot power/program management, not data streaming. It provides no access to general-purpose registers, no streaming mode, and no robot state data beyond mode queries.

### 3.3 Primary/Secondary Interface

These interfaces stream a binary state packet (~1116 bytes on e-Series) at **10 Hz**. The client can inject URScript commands as plain-text strings for immediate execution. State packet parsing is complex and version-dependent. The two ports (30001, 30002) are functionally identical, allowing two independent clients. There is no structured input register mechanism -- commands are sent as raw URScript text.

### 3.4 Modbus TCP

The UR controller includes a built-in Modbus TCP server. External clients poll coils and holding registers mapped to digital I/O and general-purpose registers. Register width is 16-bit (INT16); floating-point values require encoding across two consecutive registers. Communication is polling-based (client-initiated), not pushed. Achievable cycle rates are typically 50--200 Hz depending on client implementation. Wide ecosystem of industrial libraries (pymodbus, libmodbus).

### 3.5 URScript Socket Communication

URScript provides built-in TCP socket functions (`socket_open()`, `socket_send_string()`, `socket_read_ascii_float()`). The robot program opens a connection to a server running on the Pi and exchanges ASCII-formatted data. The protocol is entirely custom -- the developer defines the message format. Latency depends on implementation, typically 4--10 ms. String parsing introduces overhead. No built-in flow control; maximum 10 simultaneous sockets in URScript.

### 3.6 XML-RPC

Available from URScript via `rpc_factory("xmlrpc", url)`. The robot program calls functions on an external XML-RPC server running on the Pi. Calls are synchronous -- URScript blocks until the response returns. Overhead includes HTTP framing and XML serialization/deserialization. Latency is typically 10--50 ms per call. Good for infrequent complex queries, poor for per-cycle streaming.

---

## 4. Evaluation Criteria

Criteria are weighted based on the W26 use case: real-time coordinated extrusion requiring low-latency bidirectional data exchange on a compressed schedule.

| # | Criterion | Weight | Description |
|---|-----------|--------|-------------|
| C1 | Update rate / bandwidth | 25% | Maximum data exchange frequency; how much data per second |
| C2 | Latency | 25% | Round-trip time from command send to state update received |
| C3 | Bidirectional data | 20% | Ability to exchange rich, structured data in both directions (robot state feedback to Pi, commands from Pi to robot) |
| C4 | Ease of implementation | 15% | Library availability, Python support, documentation quality, development effort |
| C5 | Reliability | 15% | Error handling, reconnection behavior, robustness under load |

---

## 5. Scoring

Each candidate is scored 1--5 (5 = best).

### C1: Update Rate / Bandwidth (Weight: 25%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **RTDE** | **5** | 500 Hz streaming on e-Series. Binary-packed data with configurable field selection minimizes bandwidth. Far exceeds the ~50--100 Hz update rate needed for smooth extrusion tracking. |
| **Dashboard Server** | **1** | On-demand text commands only. No streaming capability. Response time is variable and unpredictable. Not designed for data exchange. |
| **Primary/Secondary** | **2** | 10 Hz state output. Adequate for monitoring but 50x slower than RTDE. Insufficient for smooth extrusion rate tracking at higher robot speeds. |
| **Modbus TCP** | **3** | Polling-based, achievable at 50--200 Hz depending on implementation. Reasonable bandwidth but limited by 16-bit register width and polling overhead. |
| **URScript Socket** | **3** | Update rate depends on URScript loop timing and `sync()` calls. Practically limited to ~100--250 Hz due to string formatting overhead and URScript execution speed. |
| **XML-RPC** | **1** | Synchronous blocking calls with HTTP/XML overhead. Practical maximum of ~20--50 calls/second. Each call stalls the URScript thread. |

### C2: Latency (Weight: 25%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **RTDE** | **5** | 2--5 ms round-trip (write input, receive next output). Cycle-aligned -- worst case is one missed 2 ms cycle. This is within the latency budget with significant margin. |
| **Dashboard Server** | **1** | Variable, typically 50--200 ms. Text parsing and command queuing add unpredictable delay. Completely outside the latency budget. |
| **Primary/Secondary** | **2** | ~100 ms effective latency due to 10 Hz update rate. Even if script injection is fast, state feedback only arrives at 10 Hz, making closed-loop latency unacceptable. |
| **Modbus TCP** | **3** | 5--20 ms depending on polling rate. Achievable within the latency budget at higher polling rates, but slower than RTDE and adds polling jitter. |
| **URScript Socket** | **4** | 4--10 ms round-trip. Competitive with RTDE for simple payloads. Latency depends on implementation quality and can degrade under load. |
| **XML-RPC** | **2** | 10--50 ms per call. HTTP connection overhead, XML parsing, and synchronous blocking make this marginal for the latency budget even in best case. |

### C3: Bidirectional Data (Weight: 20%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **RTDE** | **5** | Purpose-built for bidirectional exchange. 48 integer + 48 double + 64 boolean general-purpose registers in each direction. Full robot state (joint positions, TCP pose, velocities, forces, I/O) available as subscribable output fields. Richest data access of any UR interface. |
| **Dashboard Server** | **1** | Unidirectional in practice. Can query robot mode/status with text commands, but cannot read registers, joint data, or TCP state. Cannot write registers. |
| **Primary/Secondary** | **3** | Robot-to-client state streaming is comprehensive (full binary packet). Client-to-robot is limited to injecting URScript text strings -- functional but unstructured. No register-based input mechanism. |
| **Modbus TCP** | **3** | Bidirectional via Modbus read/write. However, register width is 16-bit, requiring multi-register encoding for floats. Limited to I/O and general-purpose registers -- no direct access to TCP pose, joint velocities, or forces. |
| **URScript Socket** | **3** | Fully bidirectional, but the developer must design the message format, serialization, and parsing from scratch. No built-in access to robot state -- URScript must explicitly read and send each value. |
| **XML-RPC** | **3** | Bidirectional with structured arguments and return values. URScript can pass any data as function arguments, and the server can return complex responses. However, synchronous model means only one direction is active at a time. No passive state streaming. |

### C4: Ease of Implementation (Weight: 15%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **RTDE** | **4** | Two well-documented Python libraries available. SDU `ur_rtde` provides a high-level API with reconnection handling and installs via pip. XML-based recipe configuration. Moderate learning curve but extensive examples in the research document and upstream docs. |
| **Dashboard Server** | **5** | Trivial to implement -- open a TCP socket, send ASCII strings, read responses. No special library needed. However, this simplicity reflects its limited functionality, not its suitability. |
| **Primary/Secondary** | **2** | Binary packet parsing is complex and version-dependent. No official high-level library for Python. Script injection requires careful string formatting and error handling. Limited documentation for the binary format. |
| **Modbus TCP** | **4** | Mature ecosystem. `pymodbus` is a well-maintained Python library. Modbus is a standard industrial protocol with extensive documentation. Setup is straightforward if register mapping is simple. |
| **URScript Socket** | **3** | No library needed on the robot side (built-in URScript functions). Pi side requires a custom TCP server. Developer must design and debug the message protocol, handle framing, and manage timeouts. Moderate effort. |
| **XML-RPC** | **4** | Python's `xmlrpc.server` is in the standard library. URScript's `rpc_factory()` handles the client side. Minimal boilerplate. Good for simple function-call patterns. |

### C5: Reliability (Weight: 15%)

| Candidate | Score | Rationale |
|-----------|-------|-----------|
| **RTDE** | **5** | UR's official real-time interface with defined protocol versioning, recipe negotiation, and pause/resume capability. SDU `ur_rtde` library includes automatic reconnection. If the client misses a cycle, the controller continues with last-known values (safe default). Well-tested in industrial deployments. |
| **Dashboard Server** | **3** | Simple and stable for its intended use (lifecycle management). No data loss concerns because it is request-response. But not designed for continuous operation -- connection can be dropped by the controller during mode changes. |
| **Primary/Secondary** | **3** | Stable for state monitoring. Script injection has no acknowledgment mechanism -- sent scripts execute or silently fail. No built-in error reporting for injected commands. Connection can be dropped if the controller enters certain modes. |
| **Modbus TCP** | **4** | Industrial-grade protocol with well-defined error codes and exception responses. Robust under load. Polling model means the client controls timing. However, UR's Modbus implementation is secondary to RTDE and may have edge cases with register consistency during rapid updates. |
| **URScript Socket** | **2** | No built-in flow control, framing, or error detection. String-based parsing is fragile (buffer splits, partial reads). Socket timeouts in URScript can cause the robot program to stall or error. Under high load, messages can be lost or corrupted. Requires careful defensive coding. |
| **XML-RPC** | **3** | HTTP provides reliable transport with error codes. However, synchronous blocking means a network timeout stalls the URScript program. No built-in reconnection -- if the server goes down, the robot program faults. Requires timeout handling in URScript (limited). |

---

## 6. Weighted Score Summary

| Criterion | Weight | RTDE | Dashboard | Pri/Sec | Modbus | Socket | XML-RPC |
|-----------|--------|------|-----------|---------|--------|--------|---------|
| C1: Update rate | 0.25 | 5 | 1 | 2 | 3 | 3 | 1 |
| C2: Latency | 0.25 | 5 | 1 | 2 | 3 | 4 | 2 |
| C3: Bidirectional data | 0.20 | 5 | 1 | 3 | 3 | 3 | 3 |
| C4: Ease of implementation | 0.15 | 4 | 5 | 2 | 4 | 3 | 4 |
| C5: Reliability | 0.15 | 5 | 3 | 3 | 4 | 2 | 3 |
| **Weighted Total** | **1.00** | **4.85** | **1.70** | **2.35** | **3.30** | **3.05** | **2.30** |

### Ranking

| Rank | Protocol | Score | Assessment |
|------|----------|-------|------------|
| 1 | **RTDE** | **4.85** | Clear best choice for primary real-time channel |
| 2 | Modbus TCP | 3.30 | Viable alternative; lower bandwidth and richer data access than RTDE |
| 3 | URScript Socket | 3.05 | Functional fallback; custom protocol adds development and debugging burden |
| 4 | Primary/Secondary | 2.35 | 10 Hz rate is disqualifying for real-time extrusion coordination |
| 5 | XML-RPC | 2.30 | Synchronous blocking model is a poor fit for streaming control |
| 6 | Dashboard Server | 1.70 | Not a data exchange protocol; useful only for robot lifecycle management |

---

## 7. Qualitative Discussion

**RTDE** is UR's purpose-built solution for exactly this use case -- low-latency, high-frequency, bidirectional exchange of structured data between a robot controller and an external application. It scores highest in every performance-critical criterion. The 500 Hz update rate provides 10x headroom over the minimum needed for smooth extrusion tracking, and the 2--5 ms round-trip latency keeps the system well within the 20 ms end-to-end budget even after downstream Klipper latency is added.

**Modbus TCP** is the strongest alternative. It is a proven industrial protocol with excellent library support, and its 50--200 Hz polling rate could meet the project's needs. Its main weaknesses are the 16-bit register width (awkward for floating-point extrusion rates) and the polling model (adds jitter compared to RTDE's push-based streaming). If RTDE were unavailable -- for example, on an older CB3 controller without RTDE support -- Modbus would be the recommended fallback.

**URScript Socket Communication** offers competitive latency (4--10 ms) and full flexibility, but the lack of a defined protocol means the developer must handle framing, serialization, error detection, and reconnection manually. For a two-person team on a compressed schedule, this custom protocol work is unnecessary when RTDE provides a turnkey solution.

**Primary/Secondary Interface** is disqualified by its 10 Hz update rate. At 10 Hz, the effective latency for state feedback is 100 ms, producing up to 5 mm of extrusion error during a 50 mm/s speed change -- outside the acceptable tolerance.

**XML-RPC** has the worst latency profile of the bidirectional options due to HTTP overhead and synchronous blocking. It is well-suited for infrequent complex queries (e.g., requesting the Pi to compute a new extrusion profile) but is fundamentally wrong for per-cycle streaming control.

**Dashboard Server** is not a competitor -- it is a robot management interface with no data exchange capability. It should be used alongside RTDE for startup/shutdown automation (power on, brake release, load program).

---

## 8. Recommendation

**Use RTDE (TCP port 30004) as the primary communication protocol between the UR30 and the Pi.**

The weighted score analysis (RTDE: 4.85, next-best Modbus: 3.30) demonstrates a decisive advantage. RTDE is the only protocol that simultaneously provides 500 Hz streaming, 2--5 ms latency, rich bidirectional register access, mature Python libraries, and production-grade reliability. It is the interface UR designed for this class of application.

**Supplementary protocols:**
- **Dashboard Server** (port 29999): Use for robot lifecycle automation (power on, brake release, program load/play/stop) from the Pi at startup and shutdown.
- **XML-RPC or URScript Sockets:** Available as a supplementary channel for non-time-critical operations if needed (e.g., one-time configuration queries). Not required for MVP.

### Implementation Plan

1. Install SDU `ur_rtde` library on the Pi (`pip install ur-rtde`); fall back to the official UR Python RTDE client if ARM build issues arise
2. Define output recipe: `output_int_register_0` (extrusion mode), `output_double_register_0` (commanded rate), `output_double_register_1` (TCP speed), `output_bit_register_64` (enable)
3. Define input recipe: `input_int_register_0` (stepper status), `input_double_register_0` (actual rate), `input_bit_register_64` (ready), `input_bit_register_65` (fault)
4. Write RTDE bridge daemon (Python, systemd service) that translates RTDE register data to Klipper G-code via the Klipper Unix socket (`/tmp/klippy_uds`)
5. Write corresponding URScript program that reads/writes the agreed registers in its main loop with `sync()` calls

Register allocation details are specified in `docs/ur_rtde.md`, Section 3.4.

---

## References

- UR RTDE Guide: https://www.universal-robots.com/articles/ur/interface-communication/real-time-data-exchange-rtde-guide/
- SDU ur_rtde library: https://sdurobotics.gitlab.io/ur_rtde/
- UR Client Interfaces overview: https://www.universal-robots.com/articles/ur/interface-communication/remote-control-via-tcp-ip/
- UR Dashboard Server: https://www.universal-robots.com/articles/ur/dashboard-server-e-series-ur20-ur30/
- Project research document: `docs/ur_rtde.md`
- Bolton, W. *Mechatronics*, 7th Ed. -- Step 5: Selection of a suitable solution
