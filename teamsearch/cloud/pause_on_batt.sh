#!/bin/bash
# Freeze a run's process tree while the Mac is on battery below a charge floor, and thaw it on AC (SIGSTOP/SIGCONT:
# nothing is lost). Exits when the run ends.   cloud/pause_on_batt.sh <runner pid> <log> [floor %, default 100: any battery]
cd "$(dirname "$0")/.."
ROOT=${1:?runner pid}; LOG=${2:?log}; FLOOR=${3:-100}
tree() { local p=$1; echo $p; for c in $(pgrep -P $p); do tree $c; done; }
low() { local b=$(pmset -g batt); echo "$b" | head -1 | grep -q "Battery Power" &&
        [ $(echo "$b" | grep -o '[0-9]*%' | head -1 | tr -d %) -lt $FLOOR ]; }
onac() { pmset -g batt | head -1 | grep -q "AC Power"; }
frozen=0
while kill -0 $ROOT 2>/dev/null; do
  if low && [ $frozen = 0 ]; then
    kill -STOP $(tree $ROOT); sleep 1; kill -STOP $(tree $ROOT)      # again: a battle spawned meanwhile
    echo "$(date '+%I:%M %p') paused (battery below $FLOOR%; frozen, nothing lost), resumes on AC power" >> $LOG; frozen=1
  elif onac && [ $frozen = 1 ]; then
    kill -CONT $(tree $ROOT); echo "$(date '+%I:%M %p') resumed (AC power)" >> $LOG; frozen=0
  fi
  sleep 30
done
