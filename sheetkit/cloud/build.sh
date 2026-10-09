#!/bin/bash
# On the cloud box, from ~/champions-sims: build the current sim setup's battle binary from its source tarball after checking the
# checksum, unless it is already there. Uses half the cores so a run in progress keeps going.
set -e; cd "$(dirname "$0")/../.."
BIN=$(python3 -c "import json, os; d=json.load(open('sheetkit/sim.json')); print(d['setups'][os.environ.get('SHEET_SETUP') or d['current']]['binary'])"); V=$(basename $BIN)
[ -x "$BIN" ] && { echo "$V already built"; exit 0; }
SRC=src_${V#champ-}.tar.gz; SRC=${SRC//-/_}
want=$(grep " $SRC\$" native/champ/bin/$V.sha256 | cut -d' ' -f1); have=$(sha256sum native/champ/$SRC | cut -d' ' -f1)
if [ -z "$want" ]; then echo "no source checksum recorded for $SRC (some builds record only the binary's): building the source as pushed"
else [ "$want" = "$have" ] || { echo "source checksum mismatch: $have vs $want"; exit 1; }; fi
source "$HOME/.cargo/env"; rm -rf ~/build_$V && mkdir ~/build_$V && tar xzf native/champ/$SRC -C ~/build_$V
(cd ~/build_$V && nice -n 5 cargo build --release -q -j $(( $(nproc) / 2 )))
b=$(find ~/build_$V/target/release -maxdepth 1 -type f -perm -u+x -name 'champ*' | head -1)
cp "$b" $BIN.tmp && mv $BIN.tmp $BIN && echo "built $BIN"
