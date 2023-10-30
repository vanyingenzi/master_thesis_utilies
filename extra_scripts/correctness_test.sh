#!/bin/bash

# Code inspired by https://github.com/tumi8/quic-10g-paper

# Variables
QUICHE_REPO="https://github.com/qdeconinck/quiche.git"
QUICHE_COMMIT="d87332018d84fb7c429ad2ed34cbfdc6ee9477c8"
RUST_PLATFORM="x86_64-unknown-linux-gnu"
NB_RUNS=

RED='\033[0;31m'
RESET='\033[0m'

echo_red() {
    echo -e "${RED}$1${RESET}"
}

clone_mp_quiche() {
    if [ ! -d "quiche" ]; then
        git clone --recursive "$QUICHE_REPO"
        cd quiche || exit
        git checkout "$QUICHE_COMMIT"
        RUSTFLAGS='-C target-cpu=native' cargo build --release
        cd ..
    fi
    if [ ! -f "./quiche-client" ]; then
        cp "quiche/target/release/quiche-client" .
    fi
    if [ ! -f "./quiche-server" ]; then
        cp "quiche/target/release/quiche-server" .
    fi
}

setup_rust() {
    # Rust
    if ! rustc --version 1>/dev/null 2>&1; then
        curl --proto '=https' --tlsv1.2 -sSf -o /tmp/rustup-init.sh https://sh.rustup.rs
        chmod +x /tmp/rustup-init.sh
        /tmp/rustup-init.sh -q -y --default-host "$RUST_PLATFORM" --default-toolchain stable --profile default
        source "$HOME/.cargo/env"
    else 
        echo "Rust is already installed"
    fi
}

setup_environment() {
    mkdir -p "$(pwd)/www" "$(pwd)/responses" "$(pwd)/logs"
    fallocate -l 8G "$(pwd)/www/8gb_file"
}

iteration_loop() {
    local server_pid server_port
    for iter in $(seq 1 ${NB_RUNS}); do
        echo "Testing Multi-Path QUIC correctness - Iteration $iter"
        # Run server
        env RUST_LOG=debug ./quiche-server \
            --listen 127.0.0.1:6969 \
            --root "$(pwd)/www/" \
            --key "$(pwd)/quiche/apps/src/bin/cert.key" \
            --cert "$(pwd)/quiche/apps/src/bin/cert.crt" \
            --multipath \
            1>"$(pwd)/logs/server_${iter}.log" 2>&1 &
        server_pid=$!

        # Run client
        env RUST_LOG=debug ./quiche-client \
            --no-verify https://127.0.0.1:6969/8gb_file \
            --dump-responses "$(pwd)/responses/" \
            -A 127.0.0.1:7934 \
            -A 127.0.0.2:8123 \
            --multipath \
            1>"$(pwd)/logs/client_${iter}.log" 2>&1
        error_code=$?

        sleep 1
        
        kill -9 "$server_pid" 1>/dev/null 2>&1
        if [ $error_code -ne 0 ]; then
            echo_red "Error Client: $error_code"
            exit 1
        fi

        # Check if files are the same
        diff -q "$(pwd)/www/8gb_file" "$(pwd)/responses/8gb_file"
        if [ $? -ne 0 ]; then
            echo_red "Error: files are not the same"
            exit 1
        fi
    done
}

main() {
    # Version
    git rev-parse HEAD > VERSION
    setup_rust
    [ $? -ne 0 ] && { echo_red "Error setting up rust"; exit 1; }
    clone_mp_quiche
    [ $? -ne 0 ] && { echo_red "Error cloning quiche"; exit 1; }
    setup_environment
    [ $? -ne 0 ] && { echo_red "Error setting up environment"; exit 1; }
    iteration_loop
}

main
