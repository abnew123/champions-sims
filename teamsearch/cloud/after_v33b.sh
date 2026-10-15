#!/bin/bash
# On the box (replaces after_v33.sh from 2026-10-14 night, pinning the checks to two seeds): once the v33 climb is finished (its round launcher and session gone), (1) verify every start's final team against the
# start on fresh opponents (archverify.py; runs/archverify.json), then (2) the sure-hit pass on each archetype's best 2 verified teams
# (accrefine.py: cells, rounds, final check; runs/accrefine.json). Logs: round_archverify.log, round_accrefine.log (pull_loop copies them).
# A failed step stops the chain and logs "<step> failed (exit n)"; "done" lines only follow success, and older result files are moved
# aside first, so a later step can never read an earlier run's results (outside review, 2026-10-14).
cd ~/champions-sims/teamsearch
running() {
  for p in $(pgrep -f "auto_rounds.sh"); do tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep -q '^RUN_ENV=cloud/run_env_v33.sh$' && return 0; done
  tmux -L climb has-session -t "=climb_v33" 2>/dev/null
}
while running; do sleep 60; done
TS_SIM=v33 . cloud/run_env_v33.sh                         # the finals and the sure-hit pass on two seeds per cell (rounds 2+ ran on one)
export TS_SIM=v33
read P T PF < cloud/threads_climb_v33.txt 2>/dev/null || { P=30; T=3; }
stamp=$(date -u +%Y%m%d%H%M%S)
for f in runs/archverify.json runs/accrefine.json; do [ -f $f ] && mv $f $f.old$stamp; done
step() {                                                     # step <log> <name> <command...>
  local log=$1 name=$2; shift 2
  "$@" >> $log 2>&1 || { rc=$?; echo "$(date -u +%H:%M) UTC: $name failed (exit $rc)" >> $log; exit $rc; }
}
: > round_archverify.log
step round_archverify.log verification env TS_PARALLEL=$P TS_THREADS=$T ../.venv/bin/python3 archverify.py 4
[ -s runs/archverify.json ] || { echo "$(date -u +%H:%M) UTC: verification failed (no runs/archverify.json)" >> round_archverify.log; exit 1; }
echo "$(date -u +%H:%M) UTC: verification done" >> round_archverify.log
: > round_accrefine.log
step round_accrefine.log "accuracy refinement cells" env NPROC=90 ../.venv/bin/python3 accrefine.py cells
step round_accrefine.log "accuracy refinement" env TS_PARALLEL=$P TS_THREADS=$T ../.venv/bin/python3 accrefine.py run 4
echo "$(date -u +%H:%M) UTC: accuracy refinement done" >> round_accrefine.log
