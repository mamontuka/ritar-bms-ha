#!/usr/bin/env bash
set -e

echo "Ritar BMS Service started"

CONFIG_PATH="/data/options.json"

# Create symlink from mounted custom modules from host to debug home dir
ln -sf /config/united_bms /home/debug/custom
chown -h debug:debug /home/debug/custom || true
chown -R debug:debug /home/debug/custom || true

# Extract SSH config options
SSH_ENABLED=$(jq -r '.enable_debug_shell // false' "$CONFIG_PATH")
SSH_PORT="${HASSIO_HOST_NETWORK_2222_TCP_PORT:-2222}"

# Optional SSH shell
if [ "$SSH_ENABLED" = "true" ]; then
    echo "[INFO] United BMS Debug Shell Starting"
    /usr/sbin/dropbear -E -p "$SSH_PORT" &
else
    echo "[INFO] United BMS Debug Shell is Disabled"
fi

# Always run the main Python app
echo "[INFO] United BMS Core Starting"
exec python3 -u /united_bms_core/main.py
