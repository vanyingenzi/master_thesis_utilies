#!/bin/bash

# Install ethtool if not already installed
apt install -y ethtool

INTERFACES=$(jq -r '.interfaces[]' /tmp/interop-variables.json)
LOG_DIR=$(jq -r .log_dir /tmp/interop-variables.json)


for INTERFACE in $INTERFACES; do
    sudo ethtool -N $INTERFACE rx-flow-hash udp4 sdfn
    if ls "${LOG_DIR}/ethtool-start-${INTERFACE}.txt" 1> /dev/null 2>&1; then
        ethtool -S "${INTERFACE}" > "${LOG_DIR}/ethtool-stop-${INTERFACE}.txt"
    else
        ethtool -S "${INTERFACE}" > "${LOG_DIR}/ethtool-start-${INTERFACE}.txt"
    fi
done
