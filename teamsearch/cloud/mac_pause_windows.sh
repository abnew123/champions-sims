#!/bin/bash
# Pause the Mac's background team-search climb (cloud/mac_lowelo.sh) during other threads' busy windows (Stream watcher, 2026-10-16:
# the Nice stream on Sat 10/17 3:00 am - 1:00 pm and Sun 10/18 2:40 am - 12:30 pm, Mac local time): SIGSTOP the climb's processes
# (teamsearch-py / -battle-v* / -node; not the bash scripts) when a window opens, SIGCONT when it closes. A stopped battle resumes
# where it was. Logs to round_lowelo.log.
cd "$(dirname "$0")/.."
WINDOWS=("2026-10-17 03:00|2026-10-17 13:00" "2026-10-18 02:40|2026-10-18 12:30")
sig() { [ -n "$DRY" ] && { echo "would send $1"; return; }; for p in $(pgrep -f "teamsearch/bin/teamsearch-(py|battle-v[0-9]+|node)"); do kill -$1 $p 2>/dev/null; done; }
for w in "${WINDOWS[@]}"; do
  a=$(date -j -f "%Y-%m-%d %H:%M" "${w%%|*}" +%s 2>/dev/null); b=$(date -j -f "%Y-%m-%d %H:%M" "${w##*|}" +%s 2>/dev/null); now=$(date +%s)
  if [ -z "$a" ] || [ -z "$b" ]; then echo "$(date '+%m-%d %I:%M %p'): pause window '$w' unreadable; skipped" >> round_lowelo.log; continue; fi
  [ -n "$DRY" ] && { echo "window $(date -r $a '+%a %m-%d %I:%M %p') to $(date -r $b '+%I:%M %p')"; continue; }
  [ $now -ge $b ] && continue
  [ $a -gt $now ] && sleep $(( a - now ))
  sig STOP; echo "$(date '+%m-%d %I:%M %p'): paused for another thread's busy window until $(date -r $b '+%I:%M %p')" >> round_lowelo.log
  while [ $(date +%s) -lt $b ]; do sleep 60; sig STOP; done          # also catches processes started just before the window
  sig CONT; echo "$(date '+%m-%d %I:%M %p'): resumed" >> round_lowelo.log
done
