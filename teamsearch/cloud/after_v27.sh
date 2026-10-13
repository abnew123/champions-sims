#!/bin/bash
# On the box: once the v27 climb is finished (its round launcher and session gone), (1) verify every start's final team against the
# start on fresh opponents (archverify.py; runs/archverify.json), then (2) the sure-hit pass on each archetype's best 2 verified teams
# (accrefine.py: cells, rounds, final check; runs/accrefine.json). Logs: round_archverify.log, round_accrefine.log (pull_loop copies them).
cd ~/champions-sims/teamsearch
running() {
  for p in $(pgrep -f "auto_rounds.sh"); do tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -q '^RUN_ENV=cloud/run_env_v27.sh$' && return 0; done
  tmux -L climb has-session -t "=climb_v27" 2>/dev/null
}
while running; do sleep 60; done
. cloud/run_env_v27.sh
read P T PF < cloud/threads_climb_v27.txt 2>/dev/null || { P=30; T=3; }
TS_PARALLEL=$P TS_THREADS=$T ../.venv/bin/python3 archverify.py 4 > round_archverify.log 2>&1
echo "$(date -u +%H:%M) UTC: verification done" >> round_archverify.log
NPROC=90 ../.venv/bin/python3 accrefine.py cells > round_accrefine.log 2>&1
TS_PARALLEL=$P TS_THREADS=$T ../.venv/bin/python3 accrefine.py run 4 >> round_accrefine.log 2>&1
echo "$(date -u +%H:%M) UTC: accuracy refinement done" >> round_accrefine.log
