#!/bin/bash
# Copy the cloud run's results back to the Mac every 15 minutes, into teamsearch/<dest> (default cloud_results; the v12 rerun
# uses cloud_results/v12 so the first AWS climb's tracked results aren't overwritten). Kept apart from the local runs/. Skips the big starts files. Keeps the Mac awake (idle sleep only) while
# it runs; stops once the instance has been unreachable for 30 minutes (the watchdog powered it off) or after PULL_MAX_H hours
# (default 30; it was a fixed 10 until 2026-10-15, when the v33 climb's pulls stopped at 4:42 am and the box died unwatched at 6:39).
# usage: teamsearch/cloud/pull_loop.sh <host> <key file> [dest = cloud_results]
cd "$(dirname "$0")/.."
HOST=${1:?host}; KEY=${2:?key file}; DEST=${3:-cloud_results}
mkdir -p bin                                          # run as teamsearch-<program> so top shows whose these are (user, 2026-10-06)
for p in bash rsync ssh caffeinate; do [ -e bin/teamsearch-$p ] || ln -sf "$(command -v $p)" bin/teamsearch-$p; done
[ "$(basename "$BASH")" = teamsearch-bash ] || exec bin/teamsearch-bash cloud/pull_loop.sh "$@"
bin/teamsearch-caffeinate -i -w $$ &
SSH="ssh -n -i $KEY -o ConnectTimeout=20 -o ServerAliveInterval=30"
mkdir -p "$DEST"; fails=0; start=$(date +%s)
while [ $(( $(date +%s) - start )) -lt $(( ${PULL_MAX_H:-30} * 3600 )) ]; do
  bin/teamsearch-rsync -az -e "$PWD/bin/teamsearch-ssh -i $KEY -o ConnectTimeout=20" --exclude 'starts_*.jsonl' --exclude 'grid/' \
       "ubuntu@$HOST:champions-sims/teamsearch/climb_*" "ubuntu@$HOST:champions-sims/teamsearch/round*.log" \
       "ubuntu@$HOST:champions-sims/teamsearch/runs" "$DEST/" 2>/dev/null; rc=$?
  if [ $rc -eq 0 ] || [ $rc -eq 23 ] || [ $rc -eq 24 ]; then          # 23/24: some files vanished or changed mid-copy (battles finishing): fine
    fails=0; echo "$(date '+%-I:%M %p') pulled: $(tail -qn1 "$DEST"/round*.log 2>/dev/null | tr '\n' '|')" >> "$DEST/pull.log"
  else
    fails=$((fails + 1)); echo "$(date '+%-I:%M %p') unreachable ($fails, rsync $rc)" >> "$DEST/pull.log"
    [ $fails -ge 2 ] && { echo "$(date '+%-I:%M %p') instance gone: stopping" >> "$DEST/pull.log"; exit 0; }
  fi
  sleep 900
done
