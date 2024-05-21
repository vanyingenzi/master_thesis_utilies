#!/bin/bash 

sudo apt-get install inotify-tools -y

# Setup the RFS (Receive Flow Steering) for the NICs

echo 0 | sudo tee /proc/sys/net/core/rps_sock_flow_entries
INTERFACES=$(jq -r '.interfaces[]' /tmp/interop-variables.json)

for INTERFACE in $INTERFACES; do
    sudo ethtool -N $INTERFACE rx-flow-hash udp4 sdfn
    for RX in ls /sys/class/net/$INTERFACE/queues/rx-*/rps_flow_cnt; do
        sudo bash -c "echo 0 > $RX"
    done
done