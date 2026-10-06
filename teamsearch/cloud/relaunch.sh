#!/bin/bash
# On the cloud box: stop the climb (tmux session "climb") and its battles, drop half-written results, relaunch the current round
# with P teams x T threads. Finished battles are reused. usage: ~/champions-sims/teamsearch/cloud/relaunch.sh <P> <T> [mode]
# (Run it as a script: pkill -f patterns typed on an ssh command line can match that command's own shell.)
# The climb has its own tmux server (-L climb): on a shared server, any side's pkill -f can match the server's title (the
# command of whichever session created it) and take every session down (Oct 5: TR sheet's stop killed the climb that way).
cd "$(dirname "$0")/.."
RUN_ENV=${RUN_ENV:-cloud/run_env.sh}; . $RUN_ENV              # cloud/run_env_miss.sh for the miss-doubling climb
P=${1:?parallel}; T=${2:?threads}; MODE=${3:-thorough}
S=${CLIMB_SESSION:-climb}; LOGF=${CLIMB_LOG:-round.log}
tmux -L climb kill-session -t $S 2>/dev/null; sleep 1
if [ -n "$CLIMB_SESSION" ]; then                        # one of several climbs on the box: touch only this one
  pkill -f "[c]limb.py round [a-z]* $S\$"; pkill -f "[t]eamsearch-battle-v[0-9]* battle .*teamsearch/runs/p[a-z0-9]*_${TS_SIM}_"
  pkill -f "[b]attle_starts.js .*teamsearch/runs/p[a-z0-9]*_${TS_SIM}_"; GLOB="runs/p*_${TS_SIM}_*"
else
  pkill -f "[c]limb.py round"; pkill -f "[c]hamp-battle-v[0-9]* battle .*teamsearch/runs"; pkill -f "[t]eamsearch-battle-v[0-9]* battle .*teamsearch/runs"
  pkill -f "[b]attle_starts.js .*teamsearch/runs"; GLOB="runs/*"
fi; sleep 3
GLOB=$GLOB ../.venv/bin/python3 - <<'PY'
import glob, json, os
bad = []
for f in glob.glob(os.environ['GLOB'] + '/out_*/*.json'):
    try: json.load(open(f))
    except Exception: bad.append(f)
bad += glob.glob(os.environ['GLOB'] + '/*.tmp')
for f in bad: os.remove(f)
print('removed', len(bad), 'partial files')
PY
echo "--- relaunched $(date -u +%H:%M) UTC at ${P}x${T}" >> $LOGF
tmux -L climb new -d -s $S ". $RUN_ENV && TS_PARALLEL=$P TS_THREADS=$T TS_PREFILTER_PROCS=$((P * T > 96 ? 96 : P * T)) ../.venv/bin/python3 climb.py round $MODE $S 2>&1 | tee -a $LOGF"
echo "relaunched at ${P}x${T}"
