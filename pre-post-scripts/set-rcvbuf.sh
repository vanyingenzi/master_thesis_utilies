#!/bin/bash

SIZE=$(jq -r .rmem_value /tmp/interop-variables.json)

sysctl -w net.core.rmem_max=$SIZE
sysctl -w net.core.rmem_default=$SIZE
sysctl -w net.core.wmem_max=$SIZE
sysctl -w net.core.wmem_default=$SIZE