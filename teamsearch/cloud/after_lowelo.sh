#!/bin/bash
# On the box: once the sanity-check climb is finished, verify every start's final team against the start on fresh games (archverify.py,
# one seed, 2 batches: fast). Stops at a failure with its exit status; "done" only after success. Log round_archverify.log.
cd ~/champions-sims/teamsearch
running() {
  for p in $(pgrep -f "auto_rounds.sh"); do tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -q '^RUN_ENV=cloud/run_env_lowelo.sh$' && return 0; done
  tmux -L climb has-session -t "=climb_lowelo" 2>/dev/null
}
while running; do sleep 60; done
. cloud/run_env_lowelo.sh
read P T PF < cloud/threads_climb_lowelo.txt 2>/dev/null || { P=30; T=3; }
[ -f runs/archverify.json ] && mv runs/archverify.json runs/archverify.json.old$(date -u +%Y%m%d%H%M%S)
: > round_archverify.log
TS_PARALLEL=$P TS_THREADS=$T ../.venv/bin/python3 archverify.py 2 >> round_archverify.log 2>&1 || { rc=$?; echo "$(date -u +%H:%M) UTC: verification failed (exit $rc)" >> round_archverify.log; exit $rc; }
[ -s runs/archverify.json ] || { echo "$(date -u +%H:%M) UTC: verification failed (no runs/archverify.json)" >> round_archverify.log; exit 1; }
echo "$(date -u +%H:%M) UTC: verification done" >> round_archverify.log
