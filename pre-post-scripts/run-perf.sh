#!/bin/bash

IMPLEMENTATION=$(jq -r .implementation /tmp/interop-variables.json)
ROLE=$(jq -r .role /tmp/interop-variables.json)
LOG_DIR=$(jq -r .log_dir /tmp/interop-variables.json)

while [ -z "$(pgrep -f $IMPLEMENTATION-$ROLE)" ]; do
    sleep 0.2
done

pid=$(pgrep -f $IMPLEMENTATION-$ROLE)
perf_pid=0

if [[ $IMPLEMENTATION == "mcmpquic" ]]; then
    sudo perf record -e cycles -D 4000 --cpu=0 -F 999 --max-size=4M --call-graph dwarf -p $pid -o ${LOG_DIR}/perf.data &
    perf_pid=$!
else
    sudo perf record -e cycles -D 4000 -F 999 --max-size=4M --call-graph dwarf -p $pid -o ${LOG_DIR}/perf.data &
    perf_pid=$!
fi

if [[ $perf_pid -ne 0 ]]; then
    sleep 1
    sudo kill -SIGINT $perf_pid
fi
