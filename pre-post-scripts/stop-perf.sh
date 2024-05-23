#!/bin/bash

LOG_DIR=$(jq -r .log_dir /tmp/interop-variables.json)

if pgrep -f 'perf record' > /dev/null; then
    echo "A perf record process is already running. Stopping it..."
    pkill -SIGINT -f 'perf record'
    sleep 1
else
    echo "No existing perf record process found."
fi

sudo perf script -i "${LOG_DIR}/perf.data" > "${LOG_DIR}/perf_record.txt"
sudo rm "${LOG_DIR}/perf.data"