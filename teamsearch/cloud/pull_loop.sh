#!/bin/bash
# Copy the cloud run's results back to the Mac every 15 minutes, into teamsearch/cloud_results/ (kept apart from the local
# runs/: same folder names, different battle binary). Skips the big starts files. Keeps the Mac awake (idle sleep only) while
# it runs; stops once the instance has been unreachable for 30 minutes (the watchdog powered it off) or after 10 hours.
# usage: teamsearch/cloud/pull_loop.sh <host> <key file>
cd "$(dirname "$0")/.."
HOST=${1:?host}; KEY=${2:?key file}
caffeinate -i -w $$ &
SSH="ssh -n -i $KEY -o ConnectTimeout=20 -o ServerAliveInterval=30"
mkdir -p cloud_results; fails=0; start=$(date +%s)
while [ $(( $(date +%s) - start )) -lt 36000 ]; do
  if rsync -az -e "ssh -i $KEY -o ConnectTimeout=20" --exclude 'starts_*.jsonl' --exclude 'grid/' \
       "ubuntu@$HOST:champions-sims/teamsearch/climb_*" "ubuntu@$HOST:champions-sims/teamsearch/round*.log" \
       "ubuntu@$HOST:champions-sims/teamsearch/runs" cloud_results/ 2>/dev/null; then
    fails=0; echo "$(date '+%-I:%M %p') pulled: $(tail -1 cloud_results/round.log 2>/dev/null)" >> cloud_results/pull.log
  else
    fails=$((fails + 1)); echo "$(date '+%-I:%M %p') unreachable ($fails)" >> cloud_results/pull.log
    [ $fails -ge 2 ] && { echo "$(date '+%-I:%M %p') instance gone: stopping" >> cloud_results/pull.log; exit 0; }
  fi
  sleep 900
done
