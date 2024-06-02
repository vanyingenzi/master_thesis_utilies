#!/bin/bash
# Interop runner runscript for a quiche server
# Currently supports the goodput test only

# Parse server environment variables:
# - SSLKEYLOGFILE
# - QLOGDIR
# - LOGS
# - TESTCASE
# - WWW
# - CERTS
# - IP
# - PORT

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

SERVER_ADDRESSES=$(jq -r '.extra_server_addrs[]' /tmp/interop-variables.json)

function kill_children() {
    local pid child_pid

    pid=$$
    for child_pid in $(pgrep -P "$pid"); do
        kill -TERM "$child_pid"
        wait "$child_pid" 2>/dev/null
    done
}

function run_server {
    SERVER_ADDR=$1
    SERVER_SUFFIX=$2
    DURATION=$3
    RUST_LOG=info ./shardmpquic-server \
        --cc-algorithm cubic \
        --name "quiche-interop" \
        --listen ${SERVER_ADDR} \
        --no-retry \
        --cert $CERTS/cert.pem \
        --key $CERTS/priv.key \
        --max-data $MAX_DATA \
        --transfer-time $DURATION \
        --max-window $MAX_WINDOW \
        --max-stream-data $MAX_STREAM_DATA \
        --max-stream-window $MAX_STREAM_WINDOW \
        --multipath \
        2> ${LOGS:-.}/server-${SERVER_SUFFIX}.log 1>/dev/null
}

if [[ $TESTCASE == "throughput" ]]; then
    TRANSFER_TIME=$(jq -er '.duration // empty'  /tmp/interop-variables.json)
    if [[ -z "$TRANSFER_TIME" ]]; then
        echo "transfer time is empty"
        exit 127
    fi
    
    echo "Server Address $IP:$PORT" >> ${LOGS}/initiated-servers.log
    run_server "$IP:$PORT" 0 $TRANSFER_TIME &
    id=1
    for addr in $SERVER_ADDRESSES; do
        echo "Server Address $addr" >> ${LOGS}/initiated-servers.log
        run_server $addr $id $TRANSFER_TIME &
        id=$((id+1))
    done
    trap kill_children SIGINT
    wait
else
    # Exit on unknown test with code 127
    echo "exited with code 127"
    exit 127
fi
