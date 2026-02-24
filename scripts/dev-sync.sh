#!/bin/bash
# dev-sync.sh -- Quick-sync repo changes to Pi and restart services.
#
# Pushes Python bridge code, Klipper config, and klippy extras to the Pi
# via rsync, then restarts the affected services. Much faster than a full
# deploy.sh run (~5 seconds on LAN vs minutes).
#
# Usage: bash scripts/dev-sync.sh [PI_HOST]
# Example: bash scripts/dev-sync.sh pi@192.168.1.50

set -euo pipefail

PI_HOST="${1:-pi@raspberrypi.local}"
# Tilde expands on the remote side via SSH/rsync
# shellcheck disable=SC2088
REMOTE_DIR="~/W26-Cobot-Axis"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[sync]${NC} $*"; }
success() { echo -e "${GREEN}[done]${NC} $*"; }

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: bash scripts/dev-sync.sh [PI_HOST]"
    echo ""
    echo "  PI_HOST  SSH target (default: pi@raspberrypi.local)"
    echo ""
    echo "Syncs src/ to the Pi and restarts w26-bridge and klipper."
    echo "Use this for iterative development instead of full deploy.sh."
    exit 0
fi

# Sync bridge code + configs (excludes build artifacts and local files)
info "Syncing src/ to $PI_HOST:$REMOTE_DIR/src/"
rsync -avz --delete \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='.claude' \
    src/ "$PI_HOST:$REMOTE_DIR/src/"
success "Source files synced"

# Check ur_rtde is installed (not in stub mode)
info "Checking ur_rtde on Pi..."
# shellcheck disable=SC2088
if ! ssh "$PI_HOST" "~/klippy-env/bin/python -c 'import rtde_receive; print(\"ur_rtde OK\")' 2>/dev/null"; then
    echo -e "\033[0;33m[warn]\033[0m ur_rtde not installed — bridge will run in stub mode (no real RTDE)"
fi

# Restart bridge daemon
info "Restarting w26-bridge service..."
ssh "$PI_HOST" "sudo systemctl restart w26-bridge"
success "w26-bridge restarted"

# Sync klippy extras and restart Klipper (if stallguard_monitor.py exists)
if [ -f src/klipper_mods/klippy_extras/stallguard_monitor.py ]; then
    info "Syncing stallguard_monitor.py and restarting Klipper..."
    # shellcheck disable=SC2029,SC2088
    ssh "$PI_HOST" "cp $REMOTE_DIR/src/klipper_mods/klippy_extras/stallguard_monitor.py ~/klipper/klippy/extras/ && sudo systemctl restart klipper"
    success "Klipper restarted with updated klippy extras"
fi

echo ""
success "Dev sync complete — $PI_HOST is up to date"
