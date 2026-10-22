#!/bin/bash
# Pack what one team's kit runs need on a fresh Linux box into sheetkit/cloud/bundle.tar.gz (run on the Mac, from anywhere; git-ignored).
# Leaves out node_modules (setup.sh reinstalls Showdown and applies this project's Champions fixes), results and the Mac binaries.
#   usage: sheetkit/cloud/bundle.sh <team>     then: scp it to the box, and there: mkdir champions-sims && tar xzf bundle.tar.gz -C champions-sims
#          && cd champions-sims && sheetkit/cloud/setup_box.sh
set -e; cd "$(dirname "$0")/../.."
TEAM=${1:?team}; OUT=sheetkit/cloud/bundle.tar.gz
SETUP=$(python3 sheetkit/cloud/setup_of.py $TEAM)                 # SHEET_SETUP, else the sheet's pinned 'setup', else current
read BIN VALUE DATA EXTRA <<< "$SETUP"; V=$(basename $BIN); SRC=native/champ/src_${V#champ-}.tar.gz; SRC=${SRC//-/_}
WORK=$(ls -d sheets/$TEAM/work/grid sheets/$TEAM/work/*/jobs*.json sheets/$TEAM/work/*/sixes.json sheets/$TEAM/work/*/res sheets/$TEAM/work/*/res.run.json 2>/dev/null || true)
COPYFILE_DISABLE=1 tar --no-xattrs -czf "$OUT" --exclude '__pycache__' --exclude 'fixtures' --exclude 'bundle.tar.gz' --exclude '*.err' \
  setup.sh foes.json sheetkit sheets/$TEAM/*.json $WORK regionals/smogon_mc_sets.json \
  pssim/package.json pssim/package-lock.json pssim/engine_patch pssim/t1sim.js pssim/seedmix.js pssim/worker.js pssim/run_jobs.sh \
  pssim/tr_speeds.js pssim/analyze.py pssim/trlib.py pssim/tr_final.py pssim/cond_shares.txt pssim/trmult_final.json \
  pssim/opp_model_a.json pssim/opp_model_b.json pssim/myteam_c_incin.json $VALUE \
  native/battle_starts.js native/export_state.js native/champions_data.json $DATA $EXTRA "$SRC" native/champ/bin/$V.sha256
echo "$OUT: $(du -h "$OUT" | cut -f1) ($TEAM, battle source $SRC)"
