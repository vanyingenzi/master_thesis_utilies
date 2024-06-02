#!/bin/bash

# Install ifstat if not already installed
apt install -y ifstat

# Read log directory from JSON file
LOG_DIR=$(jq -r .log_dir /tmp/interop-variables.json)

touch "${LOG_DIR}/ifstat_monitor.txt" && > "${LOG_DIR}/ifstat_monitor.txt"

# Run the ifstat command every second and append the output to the file
ifstat -t 1 >> "${LOG_DIR}/ifstat_monitor.txt"