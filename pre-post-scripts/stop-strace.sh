#!/bin/bash

pkill -SIGINT -f 'perf trace'

sleep 3 # wait for perf to finish
