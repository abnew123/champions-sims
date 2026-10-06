#!/bin/bash
# One-time setup on a fresh Ubuntu 24.04 or 26.04 x86_64 box (run there, from the unpacked bundle's root: ./teamsearch/cloud/remote_setup.sh).
# Installs Node, Python and Rust; installs Showdown's engine + this project's Champions fixes (setup.sh); builds the battle binary
# from the snapshot source after checking it against the checksum the other thread recorded.
set -e
cd "$(dirname "$0")/../.."
SRC=${1:-src_battle_v20.tar.gz}; NAME=${SRC#src_}; NAME=champ-${NAME%.tar.gz}; NAME=${NAME//_/-}   # src_battle_v3.tar.gz -> champ-battle-v3

echo "== packages"
sudo apt-get update -qq
sudo apt-get install -y -qq build-essential curl python3-venv nodejs npm xz-utils rsync tmux >/dev/null
node --version | grep -qE '^v(1[89]|[2-9][0-9])' || { echo "need Node 18+, got $(node --version)"; exit 1; }
command -v cargo >/dev/null || { curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal >/dev/null; }
source "$HOME/.cargo/env"

echo "== engine (setup.sh)"
./setup.sh

echo "== battle binary from $SRC"
want=$(grep " $SRC\$" native/champ/bin/${NAME}.sha256 | cut -d' ' -f1)
have=$(sha256sum native/champ/$SRC | cut -d' ' -f1)
[ "$want" = "$have" ] || { echo "source checksum mismatch: $have vs $want"; exit 1; }
rm -rf build_battle && mkdir build_battle && tar xzf native/champ/$SRC -C build_battle
(cd build_battle && cargo build --release -q)
bin=$(find build_battle/target/release -maxdepth 1 -type f -perm -u+x -name 'champ*' | head -1)
mkdir -p native/champ/bin && cp "$bin" native/champ/bin/$NAME
echo "built native/champ/bin/$NAME ($(nproc) cores here)"
echo "next: teamsearch/cloud/README.md step 5 (smoke test)"
