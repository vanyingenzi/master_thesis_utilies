#!/bin/bash

LOG_DIR=$(jq -r .log_dir /tmp/interop-variables.json)

pkill -SIGINT -f 'perf record'

sleep 3 # wait for perf to finish

if [ -d ${LOG_DIR} ]; then
    echo "perf data directory exists"
else
    echo "perf data directory does not exist"
    exit 127
fi

touch ${LOG_DIR}/perf.json

echo "perf data succeeded"
sudo perf script -i ${LOG_DIR}/perf.data > ${LOG_DIR}/perf_record.txt
sudo rm ${LOG_DIR}/perf.data

