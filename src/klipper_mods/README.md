# W26 Klipper Modifications — Core1 StallGuard Monitor

Firmware overlay for the SKR Pico (RP2040) that uses the idle second
core to monitor the TMC2209 DIAG pin for real-time stall detection.

## Why

Klipper polls TMC2209 registers via UART at ~4 Hz (250ms). The DIAG
pin asserts in microseconds when the StallGuard threshold is crossed.
At high extrusion rates, 250ms of undetected stall can damage the
pump or workpiece. Core1 gives hardware-speed detection with zero
impact on Klipper's step timing on core0.

## Hardware Prerequisite

Install the **DIAG jumper** on the SKR Pico's E-stepper header. This
connects the TMC2209 DIAG output to gpio16. Without this jumper,
gpio16 floats and the monitor will never detect stalls.

## Files

| File | Purpose |
|------|---------|
| `stallguard_shared.h` | Shared SRAM struct + spinlock #16 helpers |
| `core1_stallguard.c` | Core1 entry: gpio16 init, debounce loop, FIFO launch |
| `stallguard_command.c` | Klipper DECL_COMMAND: `stallguard_query`, `stallguard_clear` |
| `Makefile.patch` | Add .c files to Klipper's rp2040 build |
| `main.c.patch` | Call `core1_launch()` before `sched_main()` |
| `klippy_extras/stallguard_monitor.py` | Klippy host module: polls MCU at 20 Hz, exposes status |

## Build & Deploy

### 1. Copy firmware sources into Klipper

```bash
KLIPPER=~/klipper

cp stallguard_shared.h  $KLIPPER/src/rp2040/
cp core1_stallguard.c   $KLIPPER/src/rp2040/
cp stallguard_command.c $KLIPPER/src/rp2040/
```

### 2. Patch Makefile (add source files)

Edit `$KLIPPER/src/rp2040/Makefile` and add after the existing `src-y` lines:

```makefile
src-y += rp2040/core1_stallguard.c
src-y += rp2040/stallguard_command.c
```

### 3. Patch main.c (launch core1)

Edit `$KLIPPER/src/rp2040/main.c`:

```c
// Add near the top (after #include "sched.h"):
/* W26: Core1 StallGuard DIAG pin monitor */
extern void core1_launch(void);

// In armcm_main(), immediately before sched_main():
core1_launch();     /* W26: start DIAG monitor on core1 */
sched_main();
```

### 4. Build and flash

```bash
cd $KLIPPER
make menuconfig   # select SKR Pico / RP2040
make

# Flash via USB boot mode (hold BOOT, plug USB):
make flash FLASH_DEVICE=/dev/ttyACM0
```

### 5. Install klippy extras

```bash
cp klippy_extras/stallguard_monitor.py $KLIPPER/klippy/extras/
```

### 6. Add to printer.cfg

```ini
[stallguard_monitor]
poll_interval: 0.05
```

### 7. Restart Klipper

```bash
sudo systemctl restart klipper
```

## Verification

Query the status object via Moonraker API:

```bash
curl http://localhost:7125/printer/objects/query?stallguard_monitor
```

Expected response:

```json
{
  "result": {
    "status": {
      "stallguard_monitor": {
        "stall_active": false,
        "stall_count": 0,
        "last_stall_us": 0
      }
    }
  }
}
```

To test: manually stall the motor (block the shaft), then re-query.
`stall_active` should become `true` and `stall_count` should increment.
