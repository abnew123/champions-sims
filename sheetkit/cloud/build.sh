#!/bin/bash
# On the cloud box, from ~/champions-sims: build a sim setup's battle binary from its source tarball after checking the checksum,
# unless it is already there. Uses half the cores so a run in progress keeps going.
#   usage: sheetkit/cloud/build.sh [team]    the team's setup (SHEET_SETUP, else its sheet.json 'setup', else current); with no team,
#                                            current's and every sheet's pinned setup on the box (sheetkit/cloud/setup_of.py --all)
set -e; cd "$(dirname "$0")/../.."
build() {
  BIN=$1; V=$(basename $BIN)
  [ -x "$BIN" ] && { echo "$V already built"; return 0; }
  SRC=src_${V#champ-}.tar.gz; SRC=${SRC//-/_}
  [ -f native/champ/$SRC ] || { [ -n "$2" ] && { echo "$V: no source here ($SRC), skipped"; return 0; }; echo "missing native/champ/$SRC"; exit 1; }
  want=$(grep " $SRC\$" native/champ/bin/$V.sha256 | cut -d' ' -f1); have=$(sha256sum native/champ/$SRC | cut -d' ' -f1)
  if [ -z "$want" ]; then echo "no source checksum recorded for $SRC (some builds record only the binary's): building the source as pushed"
  else [ "$want" = "$have" ] || { echo "source checksum mismatch: $have vs $want"; exit 1; }; fi
  source "$HOME/.cargo/env"; rm -rf ~/build_$V && mkdir ~/build_$V && tar xzf native/champ/$SRC -C ~/build_$V
  (cd ~/build_$V && nice -n 5 cargo build --release -q -j $(( $(nproc) / 2 )))
  b=$(find ~/build_$V/target/release -maxdepth 1 -type f -perm -u+x -name 'champ*' | head -1)
  cp "$b" $BIN.tmp && mv $BIN.tmp $BIN && echo "built $BIN"
}
if [ -n "$1" ]; then build $(python3 sheetkit/cloud/setup_of.py $1 | cut -d' ' -f1)
else for b in $(python3 sheetkit/cloud/setup_of.py --all); do build $b optional; done; fi
