#!/bin/bash
# deploy.sh -- W26 Cobot Axis Deployment Script
# Run on the headless Pi as the 'pi' user.
# Usage: bash deploy.sh [--skip-flash] [--skip-stallguard]
#
# This script is idempotent: safe to run multiple times.
# It installs dependencies, deploys configs, and enables services.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO_DIR="$HOME/W26-Cobot-Axis"
KLIPPER_DIR="$HOME/klipper"
KLIPPY_ENV="$HOME/klippy-env"
MOONRAKER_DIR="$HOME/moonraker"
KLIPPY_UDS="/tmp/klippy_uds"
SERVICE_FILE="w26-bridge.service"

SKIP_FLASH=false
SKIP_STALLGUARD=false
for arg in "$@"; do
    case "$arg" in
        --skip-flash) SKIP_FLASH=true ;;
        --skip-stallguard) SKIP_STALLGUARD=true ;;
        --help|-h)
            echo "Usage: bash deploy.sh [--skip-flash] [--skip-stallguard]"
            echo ""
            echo "Options:"
            echo "  --skip-flash       Skip Klipper firmware build and flash"
            echo "  --skip-stallguard  Skip StallGuard firmware overlay deployment"
            echo ""
            echo "This script deploys the W26 Cobot Axis software stack."
            echo "Run as the 'pi' user on a Raspberry Pi with MainsailOS or"
            echo "Klipper already installed."
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $arg"
            echo "Usage: bash deploy.sh [--skip-flash] [--skip-stallguard]"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# OS detection for sed compatibility (GNU vs BSD)
# ---------------------------------------------------------------------------
if [[ "$(uname)" == "Darwin" ]]; then
    SED_INPLACE=(sed -i '')
else
    SED_INPLACE=(sed -i)
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }

step_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE} Step $1: $2${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# ---------------------------------------------------------------------------
# Step 1: Validate environment
# ---------------------------------------------------------------------------
step_header 1 "Validate environment"

# Check user
if [ "$(whoami)" = "root" ]; then
    error "Do not run as root. Run as the 'pi' user: bash deploy.sh"
    exit 1
fi
CURRENT_USER="$(whoami)"
if [ "$CURRENT_USER" != "pi" ]; then
    warn "Running as '$CURRENT_USER' instead of 'pi'. Paths assume user 'pi'."
    warn "If this is intentional, service file paths may need manual adjustment."
fi
success "Running as user: $CURRENT_USER"

# Check architecture
ARCH="$(uname -m)"
if [[ "$ARCH" != "aarch64" && "$ARCH" != "armv7l" ]]; then
    warn "Architecture is '$ARCH' (expected aarch64 or armv7l)."
    warn "This script is designed for Raspberry Pi. Continuing anyway."
else
    success "Architecture: $ARCH"
fi

# Check internet
info "Checking internet connectivity..."
if ping -c1 -W5 google.com > /dev/null 2>&1; then
    success "Internet connectivity OK"
else
    error "No internet connectivity. apt-get and pip require internet access."
    error "Check your network connection and try again."
    exit 1
fi

# Check repository
if [ ! -d "$REPO_DIR/src/bridge" ]; then
    error "Repository not found at $REPO_DIR"
    error "Clone the repo first: git clone <url> ~/W26-Cobot-Axis"
    exit 1
fi
success "Repository found at $REPO_DIR"

# ---------------------------------------------------------------------------
# Step 2: Install system dependencies
# ---------------------------------------------------------------------------
step_header 2 "Install system dependencies"

info "Updating apt package lists..."
sudo apt-get update -qq

info "Installing build tools and libraries..."
sudo apt-get install -y \
    build-essential \
    cmake \
    libboost-system-dev \
    libboost-thread-dev \
    libboost-filesystem-dev \
    python3-dev \
    python3-pip \
    git

success "System dependencies installed"

# ---------------------------------------------------------------------------
# Step 3: Verify Klipper installation
# ---------------------------------------------------------------------------
step_header 3 "Verify Klipper installation"

if [ ! -d "$KLIPPER_DIR" ]; then
    error "Klipper source not found at $KLIPPER_DIR"
    error "Install Klipper first (use MainsailOS or KIAUH)."
    error "See SETUP.md for instructions."
    exit 1
fi
success "Klipper source found at $KLIPPER_DIR"

if [ ! -d "$KLIPPY_ENV" ]; then
    error "Klipper virtualenv not found at $KLIPPY_ENV"
    error "Install Klipper first (use MainsailOS or KIAUH)."
    exit 1
fi
success "Klipper virtualenv found at $KLIPPY_ENV"

if systemctl is-enabled klipper > /dev/null 2>&1; then
    success "klipper.service is enabled"
else
    error "klipper.service is not enabled."
    error "Install Klipper first (use MainsailOS or KIAUH)."
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 4: Verify Moonraker installation (optional)
# ---------------------------------------------------------------------------
step_header 4 "Verify Moonraker installation"

if [ -d "$MOONRAKER_DIR" ] && systemctl is-enabled moonraker > /dev/null 2>&1; then
    success "Moonraker is installed and enabled"
else
    warn "Moonraker not found or not enabled."
    warn "Moonraker is optional but recommended for web UI monitoring."
    warn "Install via KIAUH or use MainsailOS which includes it."
fi

# ---------------------------------------------------------------------------
# Step 5: Install bridge Python dependencies
# ---------------------------------------------------------------------------
step_header 5 "Install bridge Python dependencies"

info "Upgrading pip in Klipper virtualenv..."
"$KLIPPY_ENV/bin/pip" install --upgrade pip 2>&1 | tail -1

info "Installing bridge dependencies (ur-rtde may take 5-15 min on ARM)..."
if "$KLIPPY_ENV/bin/pip" install -r "$REPO_DIR/src/bridge/requirements.txt"; then
    success "Python dependencies installed"
else
    warn "ur-rtde installation failed."
    warn "The bridge will run in stub mode (no robot connection)."
    warn "This is acceptable for development/testing without the UR30."
    warn "To retry later: $KLIPPY_ENV/bin/pip install -r $REPO_DIR/src/bridge/requirements.txt"
fi

# ---------------------------------------------------------------------------
# Step 6: Deploy Klipper configuration
# ---------------------------------------------------------------------------
step_header 6 "Deploy Klipper configuration"

# Determine Klipper config directory
KLIPPER_CONFIG_DIR="$HOME/printer_data/config"
if [ ! -d "$KLIPPER_CONFIG_DIR" ]; then
    KLIPPER_CONFIG_DIR="$HOME/klipper_config"
fi

if [ ! -d "$KLIPPER_CONFIG_DIR" ]; then
    warn "Klipper config directory not found at ~/printer_data/config/ or ~/klipper_config/"
    warn "Creating ~/printer_data/config/"
    mkdir -p "$HOME/printer_data/config"
    KLIPPER_CONFIG_DIR="$HOME/printer_data/config"
fi

# Backup existing printer.cfg if it is a real file (not our symlink)
if [ -f "$KLIPPER_CONFIG_DIR/printer.cfg" ] && [ ! -L "$KLIPPER_CONFIG_DIR/printer.cfg" ]; then
    BACKUP="$KLIPPER_CONFIG_DIR/printer.cfg.bak.$(date +%Y%m%d%H%M%S)"
    cp "$KLIPPER_CONFIG_DIR/printer.cfg" "$BACKUP"
    info "Backed up existing printer.cfg to $BACKUP"
fi

# Symlink our printer.cfg
ln -sf "$REPO_DIR/src/klipper/printer.cfg" "$KLIPPER_CONFIG_DIR/printer.cfg"
success "Symlinked printer.cfg -> $REPO_DIR/src/klipper/printer.cfg"

# Create gcode_files directory (required by virtual_sdcard in printer.cfg)
mkdir -p "$HOME/gcode_files"
success "Ensured ~/gcode_files/ exists"

# Reminder about serial path
echo ""
warn "REMINDER: The MCU serial path in printer.cfg must match your hardware."
warn "Current value: $(grep 'serial:' "$REPO_DIR/src/klipper/printer.cfg" | head -1 | xargs)"
warn "If it still says PLACEHOLDER, it will be updated in Step 9."

# ---------------------------------------------------------------------------
# Step 6b: Deploy StallGuard firmware overlay (optional)
# ---------------------------------------------------------------------------
step_header "6b" "Deploy StallGuard firmware overlay"

if [ "$SKIP_STALLGUARD" = true ]; then
    info "Skipping StallGuard overlay (--skip-stallguard specified)"
else
    MODS_DIR="$REPO_DIR/src/klipper_mods"
    RP2040_SRC="$KLIPPER_DIR/src/rp2040"

    if [ ! -d "$MODS_DIR" ]; then
        warn "StallGuard mods not found at $MODS_DIR — skipping overlay"
    elif [ ! -d "$RP2040_SRC" ]; then
        error "Klipper rp2040 source not found at $RP2040_SRC"
        error "Is Klipper installed? Run 'cd ~/klipper && git pull' first."
        exit 1
    else
        # 1. Copy C/H firmware sources into Klipper tree
        for f in stallguard_shared.h core1_stallguard.c stallguard_command.c; do
            cp "$MODS_DIR/$f" "$RP2040_SRC/$f"
        done
        success "Copied StallGuard firmware sources to $RP2040_SRC/"

        # 2. Patch Makefile — add src-y lines (idempotent)
        MAKEFILE="$RP2040_SRC/Makefile"
        if [ ! -f "$MAKEFILE" ]; then
            error "Makefile not found at $MAKEFILE — cannot patch"
            exit 1
        fi
        if grep -q 'core1_stallguard' "$MAKEFILE" 2>/dev/null; then
            info "Makefile already patched (core1_stallguard found)"
        else
            # Append after the last source file line (i2c.c) in the Makefile
            "${SED_INPLACE[@]}" '/rp2040\/i2c\.c/a src-y += rp2040/core1_stallguard.c\nsrc-y += rp2040/stallguard_command.c' "$MAKEFILE"
            success "Patched Makefile with StallGuard source files"
        fi

        # 3. Patch main.c — add core1_launch() call (idempotent)
        MAIN_C="$RP2040_SRC/main.c"
        if [ ! -f "$MAIN_C" ]; then
            error "main.c not found at $MAIN_C — cannot patch"
            exit 1
        fi
        if grep -q 'core1_launch' "$MAIN_C" 2>/dev/null; then
            info "main.c already patched (core1_launch found)"
        else
            # Add extern declaration after last #include
            "${SED_INPLACE[@]}" '/#include "sched.h"/a /* W26: Core1 StallGuard DIAG pin monitor */\nextern void core1_launch(void);' "$MAIN_C"
            # Add core1_launch() call before sched_main()
            "${SED_INPLACE[@]}" '/sched_main();/i \    core1_launch();     /* W26: start DIAG monitor on core1 */' "$MAIN_C"
            success "Patched main.c with core1_launch() call"
        fi

        # 4. Copy klippy extras module
        EXTRAS_SRC="$MODS_DIR/klippy_extras/stallguard_monitor.py"
        EXTRAS_DST="$KLIPPER_DIR/klippy/extras/stallguard_monitor.py"
        if [ -f "$EXTRAS_SRC" ]; then
            cp "$EXTRAS_SRC" "$EXTRAS_DST"
            success "Installed stallguard_monitor.py klippy extras module"
        else
            warn "klippy extras source not found at $EXTRAS_SRC"
        fi

        success "StallGuard firmware overlay deployed"
        info "The overlay will be compiled into firmware during Step 7."
    fi
fi

# ---------------------------------------------------------------------------
# Step 7: Flash Klipper firmware to SKR Pico (optional)
# ---------------------------------------------------------------------------
step_header 7 "Flash Klipper firmware to SKR Pico"

if [ "$SKIP_FLASH" = true ]; then
    info "Skipping firmware flash (--skip-flash specified)"
else
    info "Building Klipper firmware for RP2040..."
    cd "$KLIPPER_DIR"

    # Write non-interactive Kconfig for SKR Pico (RP2040, USB, W25Q080)
    cat > .config << 'KCONFIG'
CONFIG_LOW_LEVEL_OPTIONS=y
CONFIG_MACH_RP2040=y
CONFIG_RP2040_FLASH_W25Q080=y
CONFIG_RP2040_STAGE2_CLKDIV2=y
CONFIG_USB=y
CONFIG_USB_VENDOR_ID=0x1d50
CONFIG_USB_DEVICE_ID=0x614e
CONFIG_USB_SERIAL_NUMBER="12345"
CONFIG_INITIAL_PINS=""
CONFIG_HAVE_GPIO=y
CONFIG_HAVE_GPIO_ADC=y
CONFIG_HAVE_GPIO_SPI=y
CONFIG_HAVE_GPIO_I2C=y
CONFIG_HAVE_GPIO_HARD_PWM=y
CONFIG_CLOCK_FREQ=12000000
CONFIG_FLASH_SIZE=0x200000
CONFIG_RAM_START=0x20000000
CONFIG_RAM_SIZE=0x42000
CONFIG_STACK_SIZE=512
CONFIG_FLASH_APPLICATION_ADDRESS=0x10000000
CONFIG_FLASH_BOOT_ADDRESS=0x10000100
KCONFIG

    make clean KCONFIG_CONFIG=.config 2>&1 | tail -1
    make -j"$(nproc)" KCONFIG_CONFIG=.config
    success "Firmware built: $KLIPPER_DIR/out/klipper.uf2"

    # Attempt to flash
    SERIAL_DEVICE=$(find /dev/serial/by-id/ -maxdepth 1 -name 'usb-Klipper_rp2040_*' -print -quit 2>/dev/null || true)
    if [ -n "$SERIAL_DEVICE" ]; then
        info "Found Klipper device at $SERIAL_DEVICE -- flashing via make flash"
        if make flash FLASH_DEVICE="$SERIAL_DEVICE"; then
            success "Firmware flashed successfully"
        else
            warn "make flash failed. You may need to flash manually via UF2."
        fi
    else
        warn "No Klipper MCU device found on USB."
        echo ""
        echo "  Manual UF2 flash required:"
        echo "    1. Hold BOOTSEL on SKR Pico and plug in USB (or press RESET while holding BOOTSEL)"
        echo "    2. Find the USB drive: lsblk  (look for a ~128M disk, usually sda1)"
        echo "    3. sudo mount /dev/sda1 /mnt  (adjust device if lsblk shows a different name)"
        echo "    4. sudo cp $KLIPPER_DIR/out/klipper.uf2 /mnt/"
        echo "    5. sudo sync && sudo umount /mnt"
        echo "    6. The board reboots into Klipper automatically."
        echo ""
    fi

    cd "$REPO_DIR"
fi

# ---------------------------------------------------------------------------
# Step 8: Install and enable the systemd service
# ---------------------------------------------------------------------------
step_header 8 "Install systemd service"

sudo cp "$REPO_DIR/src/systemd/$SERVICE_FILE" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_FILE"
success "Installed and enabled $SERVICE_FILE"

# ---------------------------------------------------------------------------
# Step 9: Update MCU serial path
# ---------------------------------------------------------------------------
step_header 9 "Update MCU serial path in printer.cfg"

SERIAL_DEVICE=$(find /dev/serial/by-id/ -maxdepth 1 -name 'usb-Klipper_rp2040_*' -print -quit 2>/dev/null || true)
if [ -n "$SERIAL_DEVICE" ]; then
    success "Detected MCU at: $SERIAL_DEVICE"
    # Only update if printer.cfg still has the placeholder
    if grep -q "PLACEHOLDER" "$REPO_DIR/src/klipper/printer.cfg"; then
        "${SED_INPLACE[@]}" "s|serial: /dev/serial/by-id/usb-Klipper_rp2040_PLACEHOLDER-if00|serial: $SERIAL_DEVICE|" \
            "$REPO_DIR/src/klipper/printer.cfg"
        success "Updated printer.cfg serial path to $SERIAL_DEVICE"
    else
        info "printer.cfg serial path already configured (no PLACEHOLDER found)"
    fi
else
    warn "No Klipper MCU detected on USB."
    warn "Update printer.cfg manually after flashing the SKR Pico:"
    warn "  ls /dev/serial/by-id/usb-Klipper_rp2040_*"
    warn "  Then edit: $REPO_DIR/src/klipper/printer.cfg"
fi

# ---------------------------------------------------------------------------
# Step 10: Restart services
# ---------------------------------------------------------------------------
step_header 10 "Restart services"

info "Restarting Klipper..."
sudo systemctl restart klipper

info "Waiting for klippy socket (up to 30s)..."
for _ in $(seq 1 30); do
    if [ -S "$KLIPPY_UDS" ]; then
        break
    fi
    sleep 1
done

if [ -S "$KLIPPY_UDS" ]; then
    success "klippy socket is ready"
else
    warn "klippy socket not found after 30s. Klipper may still be starting."
fi

# Restart Moonraker if installed
if systemctl is-active moonraker > /dev/null 2>&1 || systemctl is-enabled moonraker > /dev/null 2>&1; then
    info "Restarting Moonraker..."
    sudo systemctl restart moonraker 2>/dev/null || true
fi

info "Starting bridge daemon..."
sudo systemctl start w26-bridge

# ---------------------------------------------------------------------------
# Step 11: Verification
# ---------------------------------------------------------------------------
step_header 11 "Deployment verification"

echo ""
echo "  Service Status:"
echo "  -----------------------------------------------"

KLIPPER_STATUS=$(systemctl is-active klipper 2>/dev/null || echo "not found")
MOONRAKER_STATUS=$(systemctl is-active moonraker 2>/dev/null || echo "not installed")
BRIDGE_STATUS=$(systemctl is-active w26-bridge 2>/dev/null || echo "not found")

if [ "$KLIPPER_STATUS" = "active" ]; then
    echo -e "    Klipper:    ${GREEN}$KLIPPER_STATUS${NC}"
else
    echo -e "    Klipper:    ${RED}$KLIPPER_STATUS${NC}"
fi

if [ "$MOONRAKER_STATUS" = "active" ]; then
    echo -e "    Moonraker:  ${GREEN}$MOONRAKER_STATUS${NC}"
else
    echo -e "    Moonraker:  ${YELLOW}$MOONRAKER_STATUS${NC}"
fi

if [ "$BRIDGE_STATUS" = "active" ]; then
    echo -e "    Bridge:     ${GREEN}$BRIDGE_STATUS${NC}"
else
    echo -e "    Bridge:     ${RED}$BRIDGE_STATUS${NC}"
fi

echo ""
echo "  System Check:"
echo "  -----------------------------------------------"

if [ -S "$KLIPPY_UDS" ]; then
    echo -e "    klippy socket:  ${GREEN}exists${NC}"
else
    echo -e "    klippy socket:  ${RED}MISSING${NC}"
fi

MCU_SERIAL=$(find /dev/serial/by-id/ -maxdepth 1 -name 'usb-Klipper_rp2040_*' -print -quit 2>/dev/null || true)
if [ -n "$MCU_SERIAL" ]; then
    echo -e "    MCU serial:     ${GREEN}$MCU_SERIAL${NC}"
else
    echo -e "    MCU serial:     ${YELLOW}NOT FOUND (flash SKR Pico first)${NC}"
fi

echo ""
echo "  Bridge Logs (last 5 lines):"
echo "  -----------------------------------------------"
journalctl -u w26-bridge --no-pager -n 5 2>/dev/null || echo "    (no logs yet)"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} Deployment complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  Next steps:"
echo "    - Verify Mainsail web UI: http://$(hostname).local/"
echo "    - View bridge logs:       journalctl -u w26-bridge -f"
echo "    - View Klipper logs:      tail -f /tmp/klippy.log"
echo "    - Re-run this script:     bash deploy.sh --skip-flash"
echo ""
