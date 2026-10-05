#!/bin/bash
# On the cloud box: after the current round (tmux session "climb") ends, keep running thorough rounds while starts are still
# climbing AND the next round can finish before the hard power-off at CAP (epoch, first arg). Estimate: ~3 min per climbing
# start at 180 cores (round 2: 29 starts, ~96k games), plus 10 min margin. usage: setsid nohup cloud/auto_rounds.sh <CAP> &
cd "$(dirname "$0")/.."
CAP=${1:?cap epoch}
while tmux has-session -t climb 2>/dev/null; do sleep 60; done
while true; do
  active=$(../.venv/bin/python3 -c "import json; s=json.load(open('climb_state.json')); print(sum(1 for t in s['teams'].values() if not t['done']))")
  if [ "$active" -eq 0 ]; then echo "$(date -u +%H:%M) UTC: every start is at a local max; no more rounds" >> round.log; break; fi
  left=$(( CAP - $(date +%s) )); need=$(( active * 180 + 600 ))
  if [ $left -lt $need ]; then echo "$(date -u +%H:%M) UTC: $active starts still climbing, but a round needs ~$((need / 60)) min and the box powers off in $((left / 60)) min; stopping" >> round.log; break; fi
  echo "--- auto round, $(date -u +%H:%M) UTC, $active starts" >> round.log
  tmux new -d -s climb "TS_BATTLE_BIN=$PWD/../native/champ/bin/champ-battle-v3 TS_PARALLEL=60 TS_THREADS=3 TS_PREFILTER_PROCS=96 ../.venv/bin/python3 climb.py round thorough 2>&1 | tee -a round.log"
  sleep 30; while tmux has-session -t climb 2>/dev/null; do sleep 60; done
done
