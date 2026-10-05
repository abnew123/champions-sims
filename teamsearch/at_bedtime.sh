#!/bin/bash
# At 3:30 am (user, 2026-10-04: "kick off the threads at 3:30" unless they need the computer longer), raise the climb to
# 5 x 2 = 10 threads, unless teamsearch/HOLD_CPU exists (create it to keep 3 cores; delete it to allow the switch).
# Hard cap (user, 2026-10-04): at most 10 busy cores in total across both threads, even when away (battery drains above that).
# Split rule (user, via the other thread, 2026-10-04): when both threads need compute, split evenly, so if the other thread's
# battle run is going at 3:30, take 3 x 2 = 6 instead (its 3 + 6 = 9); it messages when it's done and the climb goes to 10 then.
cd "$(dirname "$0")"
target=$(date -j -f "%Y-%m-%d %H:%M" "$(date +%Y-%m-%d) 03:30" +%s)
now=$(date +%s); [ $now -ge $target ] && target=$((target + 86400))
caffeinate -i -t $((target - now + 60)) &
sleep $((target - now))
if [ -e HOLD_CPU ]; then echo "$(date '+%-I:%M %p') HOLD_CPU present: staying at 3 cores" >> round1.log; exit 0; fi
pgrep -f "climb.py round" >/dev/null || { echo "$(date '+%-I:%M %p') no climb running at bedtime: nothing to raise" >> round1.log; exit 0; }
if pgrep -f "battle_[a-z0-9_]*\.sh|champ-battle-v4 battle|pssim/results" >/dev/null || pgrep -f "champ-battle-v[0-9]* battle ../native" | xargs -I{} ps -o command= -p {} | grep -qv teamsearch; then
  ./set_threads.sh 3 2; echo "$(date '+%-I:%M %p') other thread busy: 6 threads (even split)" >> round1.log
else
  ./set_threads.sh 5 2
fi
