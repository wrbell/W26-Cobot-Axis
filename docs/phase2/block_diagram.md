# System Block Diagram — Functions and Signals

**For:** Phase 2 Memo, Figure 1
**Author:** Willem
**Date:** 2026-02-12
**Status:** Rough draft — redraw in draw.io/Visio for Word submission

---

## Mermaid Diagram (for repo reference)

```mermaid
flowchart LR
    subgraph UR30["UR30 Robot Controller"]
        UR_RTDE["RTDE Server\n(port 30004)"]
        UR_Script["URScript\nProgram"]
    end

    subgraph Network["Gigabit Ethernet Switch"]
        SW["Unmanaged Switch\n5-port"]
    end

    subgraph Pi["Raspberry Pi 4B (Headless)"]
        Bridge["RTDE Bridge\nDaemon (Python)"]
        Klippy["Klipper Host\n(klippy)"]
        Moonraker["Moonraker\nAPI Server"]
    end

    subgraph SKR["SKR Pico V1.0 (RP2040)"]
        MCU["Klipper MCU\nFirmware"]
        TMC["TMC2209\nDriver (E-axis)"]
    end

    Motor["NEMA 17\nStepper Motor"]
    Pump["Metal Paste\nPump"]

    subgraph Pi400["Pi 400 (Optional HMI)"]
        SSH["SSH Terminal"]
        Web["Mainsail\nWeb UI"]
    end

    subgraph Power["Power Distribution"]
        UR_24V["UR30 24V\nPower Block"]
        Fuse["3A Blade Fuse\n+ TVS (SMBJ24CA)"]
        Buck["Pololu D24V22F5\n24V → 5.1V"]
    end

    %% Signal paths
    UR_Script --> UR_RTDE
    UR_RTDE -->|"RTDE/TCP\nport 30004\n6 output registers"| SW
    SW -->|"Ethernet\nCat5e"| Bridge
    Bridge -->|"Status writeback\n5 input registers"| SW
    SW -->|"RTDE/TCP"| UR_RTDE

    Bridge -->|"G-code commands\nUnix socket\n/tmp/klippy_uds"| Klippy
    Klippy -->|"Status subscription\nJSON-RPC"| Bridge

    Klippy -->|"Klipper binary\nUSB serial\n12 Mbps"| MCU
    MCU -->|"Status reports"| Klippy

    MCU --> TMC
    TMC -->|"Step/Dir/Enable\n+ UART config"| Motor
    Motor --> Pump

    %% Power paths
    UR_24V --> Fuse
    Fuse -->|"24V / 2A\n18 AWG"| Buck
    Fuse -->|"24V direct\n18 AWG"| SKR
    Buck -->|"5.1V / 1.5A\nGPIO pins 2+6"| Pi

    %% Optional HMI
    SW -.->|"Ethernet"| Pi400
    Moonraker -.->|"HTTP/WS\nport 7125"| Web
    Pi -.->|"SSH\nport 22"| SSH

    %% Styling
    style Pi400 stroke-dasharray: 5 5
    style SSH stroke-dasharray: 5 5
    style Web stroke-dasharray: 5 5
```

---

## Block Diagram Description (for redrawing in draw.io/Visio)

### Functional Blocks

| Block | Label | Shape | Notes |
|-------|-------|-------|-------|
| UR30 Robot Controller | "UR30 Controller" | Rectangle | Contains RTDE server + URScript program |
| Gigabit Switch | "Gigabit Switch" | Small rectangle | Unmanaged, 5-port |
| Raspberry Pi 4B | "Pi (Klipper Host + RTDE Bridge)" | Rectangle | Main control node |
| SKR Pico | "SKR Pico V1.0 (RP2040 + TMC2209)" | Rectangle | MCU + driver |
| Stepper Motor | "NEMA 17 Stepper" | Circle/oval | Actuator |
| Pump | "Metal Paste Pump" | Circle/oval | End effector |
| Pi 400 | "Pi 400 (HMI)" | Dashed rectangle | Optional |
| Power Distribution | "24V Power" | Rectangle (shaded) | Fuse + TVS + buck |

### Signal Paths (solid arrows)

| From | To | Label | Protocol | Direction |
|------|----|-------|----------|-----------|
| UR30 | Switch | "RTDE/TCP (port 30004)" | RTDE over TCP/IP | Bidirectional |
| Switch | Pi | "Ethernet (Cat5e)" | TCP/IP | Bidirectional |
| Pi (Bridge) | Pi (Klippy) | "Unix socket (/tmp/klippy_uds)" | Klipper JSON-RPC | Bidirectional |
| Pi (Klippy) | SKR Pico | "USB serial (12 Mbps)" | Klipper binary protocol | Bidirectional |
| SKR Pico (TMC2209) | Motor | "Step/Dir/Enable + UART" | GPIO + TMC2209 | Output |
| Motor | Pump | "Shaft coupling" | Mechanical | Output |

### Power Paths (thick/colored arrows)

| From | To | Label | Specs |
|------|----|-------|-------|
| UR30 Power Block | Fuse + TVS | "24V / 2A" | 18 AWG, 3A fuse, SMBJ24CA TVS |
| Distribution | SKR Pico VIN | "24V direct" | 18 AWG |
| Distribution | Buck Converter | "24V → 5.1V" | Pololu D24V22F5 |
| Buck Converter | Pi GPIO | "5.1V / 1.5A" | 22 AWG, 2A polyfuse |

### Feedback Path (dashed arrows, return direction)

| From | To | Data |
|------|----|------|
| TMC2209 | Klipper MCU | drv_status (UART: stall, OT, open load) |
| Klipper MCU | klippy host | Status reports (binary serial) |
| klippy host | Bridge daemon | Status subscription (JSON-RPC) |
| Bridge daemon | UR30 | 5 input registers (status, error, rate, ready, fault) |

### Optional Path (dashed, lighter)

| From | To | Label |
|------|----|-------|
| Switch | Pi 400 | "Ethernet (SSH, Mainsail)" |

---

## Figure Caption

**Figure 1.** System block diagram showing all functional blocks, communication protocols, power distribution, and feedback paths. The UR30 sends extrusion commands via RTDE to the Raspberry Pi, which translates them to Klipper G-code. The SKR Pico MCU generates step pulses for the TMC2209 stepper driver. Status feedback flows back through the same chain. Dashed elements (Pi 400) are optional and not in the real-time control loop. Power is distributed from the UR30's 24V power block through a blade fuse and TVS diode to both the SKR Pico (24V direct) and a buck converter (5.1V for the Pi).

---

## Key Points for the Memo Text

- **Closed-loop control architecture:** Commands flow forward (UR30 → Pi → SKR Pico → motor), status flows backward (motor → TMC2209 → Klipper → bridge → UR30)
- **Single real-time path:** UR30 → switch → Pi → SKR Pico (the Pi 400 is explicitly outside this path)
- **Protocol at each link:** RTDE/TCP, Unix socket JSON-RPC, Klipper binary serial, TMC2209 UART + step/dir GPIO
- **Power from a single source:** UR30 24V power block feeds the entire system
- **Estimated end-to-end latency:** 5–20 ms typical (see latency budget table)
