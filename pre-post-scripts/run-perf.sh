#!/bin/bash

IMPLEMENTATION=$(jq -r .implementation /tmp/interop-variables.json)
ROLE=$(jq -r .role /tmp/interop-variables.json)
LOG_DIR=$(jq -r .log_dir /tmp/interop-variables.json)

if [[ -z "$LOG_DIR" ]]; then
    echo "transfer size is empty"
    exit 127
fi

if [[ -z "$IMPLEMENTATION" ]]; then
    echo "Implementation is empty" > ${LOG_DIR}/strace.txt
    exit 127
fi

if [[ -z "$ROLE" ]]; then
    echo "role is empty" > ${LOG_DIR}/trace.txt
    exit 127
fi

# Wait for a process entitle role
while [ -z "$(pgrep -f $IMPLEMENTATION-$ROLE)" ]; do
    sleep 0.1
done

pid=$(pgrep -f $IMPLEMENTATION-$ROLE)
if [[ $IMPLEMENTATION == "mcmpquic" ]]; then
    sudo perf record -e cycles --cpu=0 -D 2000 -F 999 -g --call-graph dwarf -p $pid -o ${LOG_DIR}/perf.data
else
    sudo perf record -e cycles -a -D 2000 -F 999 -g --call-graph dwarf -p $pid -o ${LOG_DIR}/perf.data
fi