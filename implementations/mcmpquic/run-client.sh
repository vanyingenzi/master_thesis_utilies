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

if [[ $TESTCASE == "goodput" ]] || [[ $TESTCASE == "throughput" ]] ; then
    CLIENT_ADDRESSES=$(jq -r '.client_addrs[]' /tmp/interop-variables.json)
    CONNECT_TO=$(jq -r '.connect_to' /tmp/interop-variables.json)
    SERVER_ADDRESSES=$(jq -r '.extra_server_addrs[]' /tmp/interop-variables.json)

    CIDS=0
    CLIENT_ADDR_ARGS=""
    for addr in $CLIENT_ADDRESSES; do
        CLIENT_ADDR_ARGS="$CLIENT_ADDR_ARGS -A $addr"
        CIDS=$((CIDS+1))
    done
    
    SERVER_ADDR_ARGS=""
    for addr in $SERVER_ADDRESSES; do
        SERVER_ADDR_ARGS="$SERVER_ADDR_ARGS --server-address $addr"
    done

    CPU_AFFINITY_ARGS=""
    CPU_AFFINITY=$(jq -er '.app_cpu_aff // empty'  /tmp/interop-variables.json)

    if [[ -n "$CPU_AFFINITY" ]]; then
        CPU_AFFINITY_ARGS="--cpu-affinity ${CPU_AFFINITY}"
    fi

    start=$(date +%s%N)
    RUST_LOG=info ./mcmpquic-client \
        --no-verify \
        --cc-algorithm cubic \
        --wire-version 00000001 \
        --max-data $MAX_DATA \
        --max-window $MAX_WINDOW \
        --max-stream-data $MAX_STREAM_DATA \
        --max-stream-window $MAX_STREAM_WINDOW \
        ${CLIENT_ADDR_ARGS} \
        --max-active-cids ${CIDS} \
        --connect-to ${CONNECT_TO} \
        ${SERVER_ADDR_ARGS} \
        --multicore \
        ${CPU_AFFINITY_ARGS} \
        --multipath \
        $REQUESTS 1>/dev/null 2>${LOGS:-.}/client.log
    retVal=$?
    end=$(date +%s%N)
    echo {\"start\": $start, \"end\": $end} > ${LOGS:-.}/time.json

    # on error the client exits on code 101, change to 1
    if [ $retVal -eq 101 ]; then
        exit 1
    fi
else
    # Exit on unknown test with code 127
    echo "exited with code 127"
    exit 127
fi
