FROM python:3.9-slim

ENV HASSIO_DATA_PATH=/data

# === FIX MISSING PACKAGES ===
RUN apt-get update && apt-get install -y --no-install-recommends apt-utils

# Install required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    dropbear \
    sudo \
    jq \
    python3-serial \
    openssl \
    nano \
    && rm -rf /var/lib/apt/lists/*

# === Generate dropbear host keys (safely) ===
RUN mkdir -p /etc/dropbear && \
    rm -f /etc/dropbear/dropbear_*_host_key && \
    dropbearkey -t rsa -f /etc/dropbear/dropbear_rsa_host_key && \
    dropbearkey -t dss -f /etc/dropbear/dropbear_dss_host_key && \
    dropbearkey -t ecdsa -f /etc/dropbear/dropbear_ecdsa_host_key && \
    dropbearkey -t ed25519 -f /etc/dropbear/dropbear_ed25519_host_key && \
    chmod 600 /etc/dropbear/dropbear_*_host_key && \
    chown root:root /etc/dropbear/dropbear_*_host_key

# United BMS Shell
COPY united_bms/united_bms_ssh_cli/start_bms_shell.sh /usr/local/bin/start_bms_shell.sh
RUN chmod 755 /usr/local/bin/start_bms_shell.sh && \
    chown root:root /usr/local/bin/start_bms_shell.sh

# Create debug user with home and sudo
RUN useradd -m -d /home/debug -s /bin/bash debug && \
    #useradd -m -s /bin/bash tester && echo "tester:tester" | chpasswd && \
    echo "debug ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/debug && \
    echo "debug:debug" | chpasswd

RUN cat << 'EOF' >> /etc/bash.bashrc

# Force shell_main for debug user
if [ "$USER" = "debug" ]; then
  exec /usr/local/bin/start_bms_shell.sh
fi
EOF

# Use custom MOTD and remove default MOTD scripts
COPY united_bms/united_bms_ssh_cli/motd /etc/motd
RUN rm -f /etc/update-motd.d/* && chmod 644 /etc/motd

# Copy core logic
COPY *.py /united_bms_core/
COPY united_bms/united_bms_standalone_cli/cli.py /united_bms_core/
COPY united_bms/united_bms_standalone_cli/register_map.yaml /home/debug/
# Copy SSH shell logic
COPY united_bms/united_bms_ssh_cli/cli_api.py /united_bms_core/
COPY united_bms/united_bms_ssh_cli/shell_main.py /united_bms_core/

# Fix ownership
RUN chown -R debug:debug /home/debug /united_bms_core

# Entrypoint
COPY run.sh /
RUN chmod a+x /run.sh

# Install Python deps
RUN pip3 install --no-cache-dir pyyaml paho-mqtt pyserial prompt_toolkit

# Expose ports
EXPOSE 2222

# Start script
CMD [ "sh", "/run.sh" ]
