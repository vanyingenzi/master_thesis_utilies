#!/bin/bash
# Interop runner runscript for a quiche client
# Currently supports the goodput test only

# Parse client environment variables:
# - SSLKEYLOGFILE
# - QLOGDIR
# - LOGS
# - TESTCASE
# - DOWNLOADS
# - CLIENTSUFFIX

CLIENT_SUFFIX=$(jq -er '.CLIENT_SUFFIX // empty'  /tmp/interop-variables.json)
CONNECT_TO=$(jq -er '.CONNECT_TO // empty'  /tmp/interop-variables.json)
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

function kill_children() {
    local pid child_pid

    pid=$$
    for child_pid in $(pgrep -P "$pid"); do
        kill -TERM "$child_pid"
        wait "$child_pid" 2>/dev/null
    done
}

function run_client {
    SERVER_ADDR=$1
    CLIENT_ADDR=$2
    CLIENTSUFFIX=$3
    RUST_LOG=info ./shardmpquic-client \
        --no-verify \
        --cc-algorithm cubic \
        --wire-version 00000001 \
        --connect-to $SERVER_ADDR \
        --max-data $MAX_DATA \
        --max-window $MAX_WINDOW \
        --max-stream-data $MAX_STREAM_DATA \
        --max-stream-window $MAX_STREAM_WINDOW \
        --multipath \
        -A $CLIENT_ADDR \
        1>/dev/null 2>"${LOGS:-.}/client-${CLIENTSUFFIX}.log"
}

if [[ $TESTCASE == "goodput" ]] || [[ $TESTCASE == "throughput" ]] ; then

    CONNECT_TO=$(jq -r '.connect_to' /tmp/interop-variables.json)
    DURATION=$(jq -r '.duration' /tmp/interop-variables.json)

    start=$(date +%s%N)
    
    INIT_CLIENT_ADDR=$(jq -r '.client_addrs[0]' /tmp/interop-variables.json)
    echo "Server address : ${CONNECT_TO}, Client address ${INIT_CLIENT_ADDR}" >> ${LOGS:-.}/initiated-clients.log
    run_client $CONNECT_TO $INIT_CLIENT_ADDR 0 &
    
    mapfile -t OTHER_CLIENT_ADDRESSES < <(jq -r '.client_addrs[]' /tmp/interop-variables.json | tail -n +2)

    EXTRA_SERVER_ADDRESSES=$(jq -r '.extra_server_addrs[]' /tmp/interop-variables.json)

    i=0
    for server_address in $EXTRA_SERVER_ADDRESSES; do
        client_address="${OTHER_CLIENT_ADDRESSES[$i]}"
        id=$(($i+1))
        echo "Server address : ${server_address}, Client address ${client_address}" >> ${LOGS:-.}/initiated-clients.log
        run_client $server_address $client_address $id &
        i=$((i+1))
    done
    
    trap kill_children SIGINT

    wait

    end=$(date +%s%N)
    echo {\"start\": $start, \"end\": $end} > ${LOGS:-.}/time.json
    for pid in $(jobs -r); do
        exit_code=$?
        if [[ $exit_code -ne 0 ]]; then
            exit $exit_code
        fi
    done
else
    # Exit on unknown test with code 127
    echo "exited with code 127"
    exit 127
fi
