#!/bin/bash

LOG_DIR=$(jq -r .log_dir /tmp/interop-variables.json)

if ls ${LOG_DIR}/rx-interrupts-start.txt 1> /dev/null 2>&1; then
    head /proc/interrupts -n 1 > ${LOG_DIR}/rx-interrupts-stop.txt && grep mlx /proc/interrupts >> ${LOG_DIR}/rx-interrupts-stop.txt
else
    head /proc/interrupts -n 1 > ${LOG_DIR}/rx-interrupts-start.txt && grep mlx /proc/interrupts >> ${LOG_DIR}/rx-interrupts-start.txt
fi