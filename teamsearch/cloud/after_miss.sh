#!/bin/bash
# On the box: once the miss climb is finished (its round launcher and session gone), run stage 1 refinement (refine.py) on its 5 best
# teams plus the user's core, under the miss climb's setup, if every start is at a local max and >= 75 minutes remain before the cap.
# Output: climb_refine/ (state, log, progress; pulled home by pull_loop's climb_* pattern) and round_refine.log.
cd ~/champions-sims/teamsearch
CAP=$(( $(cat ~/climb_start_epoch) + 12 * 3600 )); LOGF=round_refine.log
miss_running() {
  for p in $(pgrep -f "auto_rounds.sh"); do tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -q '^RUN_ENV=cloud/run_env_poolmiss.sh$' && return 0; done
  tmux -L climb has-session -t "=climb_poolmiss" 2>/dev/null
}
while miss_running; do sleep 60; done
left=$(( CAP - $(date +%s) ))
active=$(../.venv/bin/python3 -c "import json; s=json.load(open('climb_poolmiss_state.json')); print(sum(1 for t in s['teams'].values() if not t['done']))")
echo "$(date -u +%H:%M) UTC: miss climb finished; $active starts still climbing; $((left / 60)) min before the cap" >> $LOGF
if [ "$active" -ne 0 ] || [ $left -lt 4500 ]; then echo "not refining tonight" >> $LOGF; exit 0; fi
. cloud/run_env_poolmiss.sh
tmux -L climb has-session -t "=climb_pool" 2>/dev/null && P=30 || P=60
mkdir -p climb_refine
NPROC=32 ../.venv/bin/python3 refine.py cells . climb_poolmiss 5 >> $LOGF 2>&1
TS_REFINE_DIR=climb_refine TS_PARALLEL=$P TS_THREADS=3 ../.venv/bin/python3 refine.py run . climb_poolmiss 5 >> $LOGF 2>&1
echo "$(date -u +%H:%M) UTC: refine done" >> $LOGF
