#!/bin/bash

configs_dir="./configs"
for config in $(ls "${configs_dir}" | grep throu | sort); do
    basename_config=$(basename "$config")
    echo "Running throughput test for $basename_config"
    error=0
    cd ./runner && python3 run.py -t cloudlab.json -c ${basename_config}; error=$?; cd ..
    if [ $error -ne 0 ]; then
        echo "Error running throughput test for $basename_config"
        exit 1
    fi
done
