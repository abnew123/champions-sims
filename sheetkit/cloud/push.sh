#!/bin/bash
# Put what a team's kit runs need on a cloud box that already has the repo bundle set up (teamsearch/cloud/README.md steps 2-3:
# ~/champions-sims with Showdown's engine installed and the battle binary built). Run on the Mac, from anywhere.
#   usage: sheetkit/cloud/push.sh <host> <key file> <team>
# The kit and the team folder are synced as they are here. Shared simulator files are only added where the box has none, so a
# run someone else has going there keeps the files it started with.
set -e; cd "$(dirname "$0")/../.."
HOST=${1:?host}; KEY=${2:?key file}; TEAM=${3:?team}
SSH="ssh -i $KEY -o ConnectTimeout=20"
VALUES=$(python3 -c "import json; print(' '.join(sorted({s['value'] for s in json.load(open('sheetkit/sim.json'))['setups'].values()})))")
# results already here go too (with the record of the run they belong to), so a run on a fresh box resumes instead of starting over
DONE=$(ls -d sheets/$TEAM/work/matrix/res sheets/$TEAM/work/matrix/res.run.json sheets/$TEAM/work/confirm/jobs.json \
             sheets/$TEAM/work/confirm/res sheets/$TEAM/work/confirm/res.run.json 2>/dev/null || true)
rsync -azR -e "$SSH" --exclude '__pycache__' --exclude 'fixtures' sheetkit \
  sheets/$TEAM/*.json sheets/$TEAM/work/grid/gx_cells_*.json sheets/$TEAM/work/matrix/jobs.json $DONE ubuntu@$HOST:champions-sims/
rsync -azR -e "$SSH" --ignore-existing foes.json $VALUES \
  pssim/t1sim.js pssim/seedmix.js pssim/opp_model_a.json pssim/opp_model_b.json pssim/worker.js pssim/run_jobs.sh pssim/tr_speeds.js \
  pssim/analyze.py pssim/trlib.py pssim/tr_final.py pssim/cond_shares.txt pssim/trmult_final.json \
  native/battle_starts.js native/export_state.js native/engine_data_spot.json native/champions_data.json \
  ubuntu@$HOST:champions-sims/
echo "pushed sheetkit/ and sheets/$TEAM/ to $HOST"
