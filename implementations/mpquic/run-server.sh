#!/bin/bash
# Interop runner runscript for a quiche server
# Currently supports the goodput test only

# Parse server environment variables:
# - SSLKEYLOGFILE
# - QLOGDIR
# - LOGS
# - TESTCASE
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
SERVER_ADDR_ARGS=""
CIDS=1 # connect-to address
for addr in $SERVER_ADDRESSES; do
    SERVER_ADDR_ARGS="$SERVER_ADDR_ARGS --server-address $addr"
    CIDS=$((CIDS+1))
done

if [[ $TESTCASE == "goodput" ]]; then
    TRANSFER_SIZE=$(jq -er '.filesize // empty'  /tmp/interop-variables.json)
    
    if [[ -z "$TRANSFER_SIZE" ]]; then
        echo "transfer size is empty"
        exit 127
    fi

    RUST_LOG=info ./mpquic-server \
        --cc-algorithm cubic \
        --name "quiche-interop" \
        --listen "${IP}:${PORT}" \
        --no-retry \
        --cert $CERTS/cert.pem \
        --key $CERTS/priv.key \
        --transfer-size $TRANSFER_SIZE \
        --max-data $MAX_DATA \
        --max-active-cids ${CIDS} \
        --max-window $MAX_WINDOW \
        --max-stream-data $MAX_STREAM_DATA \
        --max-stream-window $MAX_STREAM_WINDOW \
        ${SERVER_ADDR_ARGS} \
        --multipath 2>${LOGS:-.}/server.log 1>/dev/null
        
elif [[ $TESTCASE == "throughput" ]]; then
    TRANSFER_TIME=$(jq -er '.duration // empty'  /tmp/interop-variables.json)
    
    if [[ -z "$TRANSFER_TIME" ]]; then
        echo "transfer time is empty"
        exit 127
    fi

    # IP and PORT are set in the environment are normally [10.10.1.1:4433]
    RUST_LOG=info ./mpquic-server \
        --cc-algorithm cubic \
        --name "quiche-interop" \
        --listen "${IP}:${PORT}" \
        --no-retry \
        --cert $CERTS/cert.pem \
        --key $CERTS/priv.key \
        --transfer-time $TRANSFER_TIME \
        --max-data $MAX_DATA \
        --max-active-cids 16 \
        --max-window $MAX_WINDOW \
        --max-stream-data $MAX_STREAM_DATA \
        --max-stream-window $MAX_STREAM_WINDOW \
        ${SERVER_ADDR_ARGS} \
        --multipath 2>${LOGS:-.}/server.log 1>/dev/null
    
else
    # Exit on unknown test with code 127
    echo "exited with code 127"
    exit 127
fi