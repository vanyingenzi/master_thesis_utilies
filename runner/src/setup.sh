#!/bin/bash 
# Update the package lists for upgrades and new package installations
sudo apt-get -y update

# Install dependecies
sudo apt-get install -y linux-tools-common linux-tools-generic linux-tools-`uname -r`
sudo apt-get install -y tcpdump iputils-ping traceroute jq iperf3 cmake zip ifstat python3-venv python3-pip