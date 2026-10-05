#!/bin/bash
# On the cloud box: stop the climb (tmux session "climb") and its battles, drop half-written results, relaunch the current round
# with P teams x T threads. Finished battles are reused. usage: ~/champions-sims/teamsearch/cloud/relaunch.sh <P> <T> [mode]
# (Run it as a script: pkill -f patterns typed on an ssh command line can match that command's own shell.)
# The climb has its own tmux server (-L climb): on a shared server, any side's pkill -f can match the server's title (the
# command of whichever session created it) and take every session down (Oct 5: TR sheet's stop killed the climb that way).
cd "$(dirname "$0")/.."
. cloud/run_env.sh
P=${1:?parallel}; T=${2:?threads}; MODE=${3:-thorough}
tmux -L climb kill-session -t climb 2>/dev/null; sleep 1
pkill -f "[c]limb.py round"; pkill -f "[c]hamp-battle-v[0-9]* battle .*teamsearch/runs"; pkill -f "[b]attle_starts.js .*teamsearch/runs"; sleep 3
../.venv/bin/python3 - <<'PY'
import glob, json, os
bad = []
for f in glob.glob('runs/*/out_*/*.json'):
    try: json.load(open(f))
    except Exception: bad.append(f)
bad += glob.glob('runs/*/*.tmp')
for f in bad: os.remove(f)
print('removed', len(bad), 'partial files')
PY
echo "--- relaunched $(date -u +%H:%M) UTC at ${P}x${T}" >> round.log
tmux -L climb new -d -s climb ". cloud/run_env.sh && TS_PARALLEL=$P TS_THREADS=$T TS_PREFILTER_PROCS=$((P * T > 96 ? 96 : P * T)) ../.venv/bin/python3 climb.py round $MODE 2>&1 | tee -a round.log"
echo "relaunched at ${P}x${T}"
