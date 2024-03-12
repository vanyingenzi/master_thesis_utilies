#!/bin/bash

# Variables

QUICHE_REPO=https://github.com/cloudflare/quiche.git
QUICHE_COMMIT=e71c51b8cd9aa3b78749fa7cb82f35699d23e7bf
RUST_PLATFORM=x86_64-unknown-linux-gnu

# Version
git rev-parse HEAD > VERSION

# Rust
curl --proto '=https' --tlsv1.2 -sSf -o /tmp/rustup-init.sh https://sh.rustup.rs
chmod +x /tmp/rustup-init.sh
/tmp/rustup-init.sh -q -y --default-host $RUST_PLATFORM --default-toolchain stable --profile default
source $HOME/.cargo/env

# Quiche
git clone --recursive $QUICHE_REPO
cd quiche
git checkout $QUICHE_COMMIT
RUSTFLAGS='-C target-cpu=native' cargo build --release
cd ..

# Export as archive
cp quiche/target/release/quiche-client quic-client
cp quiche/target/release/quiche-server quic-server
zip artifact.zip \
    VERSION \
    setup-env.sh run-client.sh run-server.sh \
    quic-client \
    quic-server