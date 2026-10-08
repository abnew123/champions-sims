#!/bin/bash
# On the box: once the per-archetype climb is finished (its round launcher and session gone), verify every start's final team against
# the start on fresh opponents (archverify.py). Log: round_archverify.log; results runs/archverify.json (pull_loop copies both).
cd ~/champions-sims/teamsearch
running() {
  for p in $(pgrep -f "auto_rounds.sh"); do tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -q '^RUN_ENV=cloud/run_env_arch.sh$' && return 0; done
  tmux -L climb has-session -t "=climb_arch" 2>/dev/null
}
while running; do sleep 60; done
. cloud/run_env_arch.sh
read P T PF < cloud/threads_climb_arch.txt 2>/dev/null || { P=30; T=3; }
TS_PARALLEL=$P TS_THREADS=$T ../.venv/bin/python3 archverify.py 4 > round_archverify.log 2>&1
echo "$(date -u +%H:%M) UTC: verification done" >> round_archverify.log
