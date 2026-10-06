#!/bin/bash
# One-time setup on a fresh Ubuntu x86_64 box, from the unpacked bundle's root (sheetkit/cloud/bundle.sh): Node, Python and Rust;
# Showdown's engine with this project's Champions fixes and a Python venv (setup.sh); the current sim setup's battle binary, built from
# its checksum-checked source (build.sh). About 10 minutes.
set -e; cd "$(dirname "$0")/../.."
sudo apt-get update -qq
sudo apt-get install -y -qq build-essential curl python3-venv nodejs npm rsync >/dev/null
node --version | grep -qE '^v(1[89]|[2-9][0-9])' || { echo "need Node 18+, got $(node --version)"; exit 1; }
command -v cargo >/dev/null || [ -x "$HOME/.cargo/bin/cargo" ] || { curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal >/dev/null; }
./setup.sh
sheetkit/cloud/build.sh
echo "box ready: $(nproc) cores"
