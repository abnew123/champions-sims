#!/bin/bash
# Copy a team's kit results back from the cloud box: result folders, run logs, and picks.json / t1.json if they were made there.
# Leaves out the starting-position files. Run on the Mac, from anywhere; safe to repeat while a run is going.
#   usage: sheetkit/cloud/pull.sh <host> <key file> <team>
set -e; cd "$(dirname "$0")/../.."
HOST=${1:?host}; KEY=${2:?key file}; TEAM=${3:?team}
SSH="ssh -i $KEY -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new"
rsync -az -e "$SSH" --exclude '*.starts.jsonl' --exclude '*.parts' --exclude 'grid/' --exclude 'smoke/' \
  ubuntu@$HOST:champions-sims/sheets/$TEAM/work/ sheets/$TEAM/work/
rsync -az -e "$SSH" "ubuntu@$HOST:champions-sims/pssim/kit_${TEAM}_*.log" pssim/ 2>/dev/null || true
echo "$(date '+%-I:%M %p') pulled: matrix $(ls sheets/$TEAM/work/matrix/res 2>/dev/null | wc -l | tr -d ' ') results, confirm $(ls sheets/$TEAM/work/confirm/res 2>/dev/null | wc -l | tr -d ' ')"
