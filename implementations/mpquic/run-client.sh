#!/bin/bash
# Interop runner runscript for a quiche client
# Currently supports the goodput test only

# Parse client environment variables:
# - SSLKEYLOGFILE
# - QLOGDIR
# - LOGS
# - TESTCASE
# - DOWNLOADS

MAX_DATA=$(jq -er '.MAX_DATA // empty'  /tmp/interop-variables.json)
MAX_WINDOW=$(jq -er '.MAX_WINDOW // empty'  /tmp/interop-variables.json)
MAX_STREAM_DATA=$(jq -er '.MAX_STREAM_DATA // empty'  /tmp/interop-variables.json)
MAX_STREAM_WINDOW=$(jq -er '.MAX_STREAM_WINDOW // empty'  /tmp/interop-variables.json)

if [[ $? != 0 ]]; then
    MAX_DATA=100000000
    MAX_WINDOW=100000000
    MAX_STREAM_DATA=100000000
    MAX_STREAM_WINDOW=100000000
fi

get_unused_port(){
    local port
    port=$(shuf -i 2000-65000 -n 1)
    while netstat -atn | grep -q ":$port "; do
        port=$(shuf -i 2000-65000 -n 1)
    done
    echo "$port"
}

if [[ $TESTCASE == "goodput" ]] || [[ $TESTCASE == "throughput" ]] ; then
    client_port_1=$(get_unused_port)
    client_port_2=$(get_unused_port)
    start=$(date +%s%N)
    RUST_LOG=info ./mpquic-client \
        --no-verify \
        --cc-algorithm cubic \
        --wire-version 00000001 \
        --max-data $MAX_DATA \
        --max-window $MAX_WINDOW \
        --max-stream-data $MAX_STREAM_DATA \
        --max-stream-window $MAX_STREAM_WINDOW \
        -A "10.10.1.2:${client_port_1}" \
        -A "10.10.2.2:${client_port_2}" \
        --connect-to "10.10.1.1:4433" \
        --server-address "10.10.2.1:3344" \
        --multipath \
        1>/dev/null 2>${LOGS:-.}/client.log
    retVal=$?
    end=$(date +%s%N)
    echo {\"start\": $start, \"end\": $end} > ${LOGS:-.}/time.json

    if [ $retVal -ne 0 ]; then
        exit 1
    fi
else
    # Exit on unknown test with code 127
    echo "exited with code 127"
    exit 127
fi
