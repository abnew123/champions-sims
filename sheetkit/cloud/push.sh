#!/bin/bash
# Put what a team's kit runs need on a cloud box that already has the repo bundle set up (teamsearch/cloud/README.md steps 2-3:
# ~/champions-sims with Showdown's engine installed). Run on the Mac, from anywhere.
#   usage: sheetkit/cloud/push.sh <host> <key file> <team>
# The kit, the team folder and the sheet thread's own simulator files (t1sim.js, run_jobs.sh, the turn-one solver) are synced as they
# are here. Other shared files are only added where the box has none, so a run someone else has going there keeps the files it started
# with. The current sim setup's battle source and checksums go along; sheetkit/cloud/build.sh builds the binary there.
set -e; cd "$(dirname "$0")/../.."
HOST=${1:?host}; KEY=${2:?key file}; TEAM=${3:?team}
SSH="ssh -i $KEY -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new"
SETUP=$(python3 -c "import json; d=json.load(open('sheetkit/sim.json')); s=d['setups'][d['current']]; print(s['binary'], s['value'], s['engine_data'])")
read BIN VALUE DATA <<< "$SETUP"; V=$(basename $BIN); SRC=native/champ/src_${V#champ-}.tar.gz; SRC=${SRC//-/_}
DONE=$(ls -d sheets/$TEAM/work/*/res sheets/$TEAM/work/*/res.run.json sheets/$TEAM/work/*/jobs*.json sheets/$TEAM/work/*/sixes.json \
             sheets/$TEAM/work/optimal*/screen_* sheets/$TEAM/work/optimal*/matrix* 2>/dev/null || true)
rsync -azR -e "$SSH" --exclude '__pycache__' --exclude 'fixtures' --exclude '*.starts' --exclude '*.err' sheetkit \
  sheets/$TEAM/*.json sheets/$TEAM/work/grid/gx_cells_*.json $DONE \
  pssim/t1sim.js pssim/worker.js pssim/run_jobs.sh pssim/tr_speeds.js pssim/analyze.py pssim/trlib.py pssim/tr_final.py \
  pssim/cond_shares.txt pssim/trmult_final.json ubuntu@$HOST:champions-sims/
rsync -azR -e "$SSH" --ignore-existing foes.json $VALUE $DATA "$SRC" native/champ/bin/$V.sha256 \
  pssim/seedmix.js pssim/opp_model_a.json pssim/opp_model_b.json native/battle_starts.js native/export_state.js native/champions_data.json \
  ubuntu@$HOST:champions-sims/
echo "pushed sheetkit/ and sheets/$TEAM/ to $HOST (setup needs $V; build it there with sheetkit/cloud/build.sh if missing)"
