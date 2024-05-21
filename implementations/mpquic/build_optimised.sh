#!/bin/bash

# Variables

QUICHE_REPO=https://github.com/vanyingenzi/quiche.git
QUICHE_COMMIT=e4cce145db5267187018a026e2b54ee0db98f46b
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
cp quiche/target/release/quiche-client ./mpquic-client
cp quiche/target/release/quiche-server ./mpquic-server
zip artifact.zip \
    VERSION \
    setup-env.sh run-client.sh run-server.sh \
    mpquic-server \
    mpquic-client