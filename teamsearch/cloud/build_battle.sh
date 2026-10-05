#!/bin/bash
# On the box: build one battle binary from its source snapshot (checked against the recorded checksum), next to any others,
# without reinstalling packages (safe while other runs use pssim/node_modules). remote_setup.sh does this plus the full setup.
# usage (from ~/champions-sims): teamsearch/cloud/build_battle.sh src_battle_v13.tar.gz
set -e
cd "$(dirname "$0")/../.."
SRC=${1:?source tarball}; NAME=${SRC#src_}; NAME=champ-${NAME%.tar.gz}; NAME=${NAME//_/-}
source "$HOME/.cargo/env"
want=$(grep " $SRC\$" native/champ/bin/${NAME}.sha256 | cut -d' ' -f1)
have=$(sha256sum native/champ/$SRC | cut -d' ' -f1)
[ -n "$want" ] && [ "$want" = "$have" ] || { echo "source checksum mismatch: $have vs $want"; exit 1; }
B=build_${NAME//-/_}; rm -rf $B && mkdir $B && tar xzf native/champ/$SRC -C $B
(cd $B && cargo build --release -q)
bin=$(find $B/target/release -maxdepth 1 -type f -perm -u+x -name 'champ*' | head -1)
cp "$bin" native/champ/bin/$NAME.tmp && mv native/champ/bin/$NAME.tmp native/champ/bin/$NAME
echo "built native/champ/bin/$NAME"
