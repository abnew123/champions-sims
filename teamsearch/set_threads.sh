#!/bin/bash
# Change the running climb round's thread count: stop it (and its battles), drop half-written results, relaunch with
# TS_PARALLEL=$1 teams at a time x TS_THREADS=$2 threads each. Finished battles and the round's pre-filter are reused.
# usage: teamsearch/set_threads.sh <parallel> <threads> [mode=thorough]
cd "$(dirname "$0")"
P=${1:?parallel}; T=${2:?threads}; MODE=${3:-thorough}
pkill -f "climb.py round"; sleep 1
pkill -f "champ-battle-v[0-9]* battle .*teamsearch/runs"; pkill -f "battle_starts.js .*teamsearch/runs"; sleep 3
../.venv/bin/python3 - <<'EOF'
import glob, json, os
bad = []
for f in glob.glob('runs/*/out_*/*.json'):
    try: json.load(open(f))
    except Exception: bad.append(f)
bad += glob.glob('runs/*/*.tmp')
for f in bad: os.remove(f)
print('removed', len(bad), 'partial files')
EOF
echo "--- relaunched $(date '+%-I:%M %p') at ${P}x${T} threads" >> round1.log
TS_PARALLEL=$P TS_THREADS=$T TS_PREFILTER_PROCS=$((P * T)) nohup ../.venv/bin/python3 climb.py round "$MODE" >> round1.log 2>&1 &
pid=$!; nohup caffeinate -i -w $pid >/dev/null 2>&1 &
echo "climb relaunched (pid $pid) at ${P}x${T} threads"
