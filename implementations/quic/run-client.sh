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

if [[ $TESTCASE == "goodput" ]] || [[ $TESTCASE == "throughput" ]] ; then
    start=$(date +%s%N)
    RUST_LOG=info ./quic-client \
        --no-verify \
        --cc-algorithm cubic \
        --wire-version 00000001 \
        --connect-to $CONNECT_TO \
        --max-data $MAX_DATA \
        --max-window $MAX_WINDOW \
        --max-stream-data $MAX_STREAM_DATA \
        --max-stream-window $MAX_STREAM_WINDOW \
        1>/dev/null 2>"${LOGS:-.}/client${CLIENTSUFFIX}.log"
    retVal=$?
    end=$(date +%s%N)
    echo {\"start\": $start, \"end\": $end} > "${LOGS:-.}/time${CLIENTSUFFIX}.json"
    if [ $retVal -ne 0 ]; then
        exit 1
    fi
else
    # Exit on unknown test with code 127
    echo "exited with code 127"
    exit 127
fi
