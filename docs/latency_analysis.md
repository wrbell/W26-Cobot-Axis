# End-to-End Latency Analysis

**Project:** W26 Cobot Axis
**Author:** Willem (Software/EE)
**Date:** 2026-02-12
**Status:** Preliminary (pre-hardware)

---

## Overview

This document analyzes the expected end-to-end latency from UR30 extrusion command to physical stepper motor response. The latency budget determines whether the system can maintain acceptable deposition quality during coordinated motion.

---

## Communication Chain

```
UR30 Controller ──[1]──▶ Gigabit Switch ──[2]──▶ Pi (RTDE Bridge) ──[3]──▶ klippy (Klipper Host) ──[4]──▶ SKR Pico (MCU) ──[5]──▶ Stepper Motor
```

---

## Per-Segment Latency Breakdown

| # | Segment | Latency | Source | Notes |
|---|---------|---------|--------|-------|
| 1 | UR30 RTDE output cycle | 0 – 2 ms | UR RTDE spec | e-Series runs at 500 Hz (2ms cycle). Worst case: command just missed a cycle. |
| 2 | Ethernet transmission (via switch) | 0.1 – 0.5 ms | Network fundamentals | Gigabit switch adds < 0.1ms. Direct connection would be similar. |
| 3 | RTDE bridge processing (Python) | 0.5 – 2 ms | Estimate | Python RTDE receive + command translation + Unix socket write. Single-threaded worst case. |
| 4a | klippy Unix socket IPC | < 0.5 ms | Klipper docs | Local Unix domain socket, JSON encode/decode. |
| 4b | klippy motion planning | 1 – 5 ms | Klipper architecture | G-code parse → kinematic solve → step generation → queue to MCU. |
| 5 | USB serial to SKR Pico | 0.5 – 1 ms | Klipper MCU protocol | USB Full-Speed (12 Mbps), binary protocol, max 64-byte messages. |
| 6 | MCU step execution | < 0.1 ms | Hardware timer | RP2040 hardware timer triggers step pulses at precise clock ticks. |
| 7 | Stepper motor mechanical response | 0.5 – 2 ms | Motor physics | Electrical time constant + rotor inertia. TBD — parameterized on motor receipt. |
| | **Total (command to first step)** | **~3 – 13 ms** | | **Typical: ~8 ms** |

### Klipper Lookahead Buffer

Klipper pre-queues step commands ~100ms ahead of real time on the MCU. This means:

- **Step timing precision** is microsecond-level (driven by RP2040 hardware timers)
- **Command-to-motion latency** includes the buffer fill time for the first command
- **Steady-state streaming** commands are absorbed into the buffer smoothly
- For continuous extrusion at a steady rate, the buffer provides jitter immunity

The 100ms lookahead is the dominant latency contributor for the *first* command. During steady-state operation, new speed changes propagate through the buffer with the per-segment latencies above.

---

## Latency vs. Extrusion Error

When robot TCP speed changes, the extrusion rate must track. If the extrusion lags by time `dt`:

```
Position error = |v_new - v_old| × dt
```

| Scenario | Speed Change | dt = 5 ms | dt = 10 ms | dt = 20 ms |
|----------|-------------|-----------|------------|------------|
| Gradual accel | 10 → 20 mm/s | 0.05 mm | 0.1 mm | 0.2 mm |
| Moderate accel | 0 → 50 mm/s | 0.25 mm | 0.5 mm | 1.0 mm |
| Sudden stop | 50 → 0 mm/s | 0.25 mm | 0.5 mm | 1.0 mm |
| Corner (worst) | 50 → 0 → 50 mm/s | 0.5 mm | 1.0 mm | 2.0 mm |

**For metal paste dispensing:**
- Typical UR30 deposition speed: 10 – 50 mm/s (slower than desktop 3D printers)
- Typical bead width: 1 – 5 mm (much larger than FDM)
- Acceptable position error: < 1 mm (generous tolerance for paste)

At our estimated 8ms typical latency and 30 mm/s typical speed, the worst-case error during a speed change is **~0.24 mm** — well within tolerance.

---

## Comparison to Alternatives

| Approach | Typical Latency | Notes |
|----------|----------------|-------|
| **Our system (RTDE → Klipper)** | **~8 ms typical** | Full digital control, rich feedback |
| Analog voltage (0-10V) | ~1 ms | Simple but no feedback, 12-bit resolution |
| Direct GPIO step/dir from Pi | ~2 ms | No motion planning, jitter-prone on Linux |
| Industrial fieldbus (PROFINET) | < 1 ms | Requires licensed option on UR30 |
| ROS2 + ur_robot_driver | 10 – 50 ms | Heavy overhead, not justified for single axis |

Our latency is competitive with most approaches and adequate for the application.

---

## Latency Mitigation Strategies

### 1. Use Target TCP Speed (Feed-Forward)

The UR30 plans trajectories ahead of time. Reading `target_TCP_speed` instead of `actual_TCP_speed` provides a look-ahead that compensates for downstream processing latency.

```
Effective latency reduction: ~2 ms (one RTDE cycle)
```

### 2. Speed-Proportional Mode

Instead of commanding absolute positions, command a speed setpoint proportional to TCP speed. This naturally handles smooth speed changes and avoids position synchronization entirely.

```
extrusion_rate = K × tcp_speed
```

The bridge daemon continuously updates the Klipper speed setpoint. Position errors accumulate only during transients, not during steady-state motion.

### 3. Tune Klipper Lookahead

For the initial command latency, Klipper's `MOVE_QUEUE_SIZE` and acceleration limits can be tuned to reduce buffer depth. Trade-off: smaller buffer = more susceptible to host-side jitter.

### 4. Time-Shift Commands

If latency is measured and stable (e.g., consistently ~8ms), the bridge daemon can issue Klipper commands early by that offset. This requires characterizing the actual latency during Phase 4 testing.

---

## Measurements Needed (Phase 4)

| Measurement | Method | Purpose |
|-------------|--------|---------|
| RTDE round-trip time | Timestamp registers, measure in Python | Characterize segment 1-2 |
| Bridge processing time | Python `time.perf_counter()` profiling | Characterize segment 3 |
| Command-to-step latency | Oscilloscope on step pin, trigger on RTDE write | End-to-end hardware measurement |
| Steady-state jitter | Log timestamps over 10,000+ cycles | Quantify worst-case outliers |
| Klipper buffer drain time | Klipper status objects (`queue_empty` events) | Characterize lookahead behavior |

---

## Conclusion

The estimated end-to-end latency of **~8 ms typical (3–13 ms range)** is adequate for metal paste dispensing at UR30 speeds. The worst-case extrusion position error during speed transients is < 0.5 mm at typical operating conditions, well within the tolerance for paste deposition.

The primary risk is the Klipper lookahead buffer adding ~100ms of initial command latency. This is mitigated by speed-proportional control mode (no position synchronization needed) and can be further reduced by feed-forward from target TCP speed.

Formal latency characterization with hardware measurements is planned for Phase 4 testing.
