#!/bin/bash

# Turn off hyperthreading
echo off | sudo tee /sys/devices/system/cpu/smt/control