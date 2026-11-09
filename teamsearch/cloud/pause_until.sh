#!/bin/bash
# Pause a running Mac job and resume it at a set time (the user, 2026-11-08: pause the synergy check, start back up at 2 am).
# SIGSTOP the runner and its whole process tree (nothing is lost or replayed), then SIGCONT at the time. Checks the wall clock every
# minute, so a Mac that slept through the time resumes on waking. The log gets a "paused ..., resumes ..." line (the progress card
# shows it as waiting) and a "resumed" line (the card restarts its rate there, since the stage's minutes now include the pause).
# usage: teamsearch/bin/teamsearch-bash teamsearch/cloud/pause_until.sh <runner pid> "<YYYY-mm-dd HH:MM>" <log>
cd "$(dirname "$0")/.."
ROOT=${1:?runner pid}; AT=${2:?resume time}; LOG=${3:?log}
tree() { local p=$1; echo $p; for c in $(pgrep -P $p); do tree $c; done; }
kill -0 $ROOT 2>/dev/null || { echo "no process $ROOT"; exit 1; }
target=$(date -j -f "%Y-%m-%d %H:%M" "$AT" +%s) || exit 1
kill -STOP $(tree $ROOT); sleep 1; kill -STOP $(tree $ROOT)            # again: a battle spawned meanwhile
echo "$(date '+%I:%M %p') paused (frozen, nothing lost), resumes $(date -j -r $target '+%-I:%M %p')" >> $LOG
until [ $(date +%s) -ge $target ]; do sleep 60; done
kill -CONT $(tree $ROOT)
echo "$(date '+%I:%M %p') resumed" >> $LOG
bin/teamsearch-caffeinate -i -w $ROOT
