#!/bin/bash

# Install ethtool if not already installed
apt install -y ethtool

# Read interfaces and log directory from JSON file
INTERFACES=$(jq -r '.interfaces[]' /tmp/interop-variables.json)
LOG_DIR=$(jq -r .log_dir /tmp/interop-variables.json)

# If the ethtool-start.txt file does not yet exist, it is created,
# otherwise, the output is saved under ethtool-stop.txt. If this script
# runs more than twice, only the first and last run are saved.

for INTERFACE in $INTERFACES; do
    if ls "${LOG_DIR}/ethtool-start-${INTERFACE}.txt" 1> /dev/null 2>&1; then
        ethtool -S "${INTERFACE}" > "${LOG_DIR}/ethtool-stop-${INTERFACE}.txt"
    else
        ethtool -S "${INTERFACE}" > "${LOG_DIR}/ethtool-start-${INTERFACE}.txt"
    fi
done
