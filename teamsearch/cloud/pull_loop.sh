#!/bin/bash
# Copy the cloud run's results back to the Mac every 15 minutes, into teamsearch/<dest> (default cloud_results; the v12 rerun
# uses cloud_results/v12 so the first AWS climb's tracked results aren't overwritten). Kept apart from the local runs/. Skips the big starts files. Keeps the Mac awake (idle sleep only) while
# it runs; stops once the instance has been unreachable for 30 minutes (the watchdog powered it off) or after 10 hours.
# usage: teamsearch/cloud/pull_loop.sh <host> <key file> [dest = cloud_results]
cd "$(dirname "$0")/.."
HOST=${1:?host}; KEY=${2:?key file}; DEST=${3:-cloud_results}
caffeinate -i -w $$ &
SSH="ssh -n -i $KEY -o ConnectTimeout=20 -o ServerAliveInterval=30"
mkdir -p "$DEST"; fails=0; start=$(date +%s)
while [ $(( $(date +%s) - start )) -lt 36000 ]; do
  if rsync -az -e "ssh -i $KEY -o ConnectTimeout=20" --exclude 'starts_*.jsonl' --exclude 'grid/' \
       "ubuntu@$HOST:champions-sims/teamsearch/climb_*" "ubuntu@$HOST:champions-sims/teamsearch/round*.log" \
       "ubuntu@$HOST:champions-sims/teamsearch/runs" "$DEST/" 2>/dev/null; then
    fails=0; echo "$(date '+%-I:%M %p') pulled: $(tail -1 "$DEST/round.log" 2>/dev/null)" >> "$DEST/pull.log"
  else
    fails=$((fails + 1)); echo "$(date '+%-I:%M %p') unreachable ($fails)" >> "$DEST/pull.log"
    [ $fails -ge 2 ] && { echo "$(date '+%-I:%M %p') instance gone: stopping" >> "$DEST/pull.log"; exit 0; }
  fi
  sleep 900
done
