#!/bin/bash

apt install -y net-tools

LOG_DIR=$(jq -r .log_dir /tmp/interop-variables.json)

if ls ${LOG_DIR}/netstat-start.txt 1> /dev/null 2>&1; then
    netstat -su > ${LOG_DIR}/netstat-stop.txt
else
    netstat -su > ${LOG_DIR}/netstat-start.txt
fi