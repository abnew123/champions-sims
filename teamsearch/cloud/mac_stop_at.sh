#!/bin/bash
# Stop the Mac's background climb (cloud/mac_lowelo.sh) for good at a set time, with no resume (the user, relayed by Battle sim on
# 2026-10-16: a flight on Sat 10/17, nothing running on the Mac from noon until they say so; the stream window paused it from 3:00 am
# anyway, so it stops then). Ends the runner script first (no next step starts), then the climb's teamsearch-py / -battle-v* / -node
# processes (TERM, KILL after 20 s; stopped ones get CONT so the TERM lands). Finished games stay in the game cache and finished rounds
# in climb_lowelo_state.json: a relaunch (nohup teamsearch/bin/teamsearch-bash teamsearch/cloud/mac_lowelo.sh &) redoes the round in
# progress from the cache. Logs to round_lowelo.log.
#   usage, from the repo root: nohup teamsearch/bin/teamsearch-bash teamsearch/cloud/mac_stop_at.sh "2026-10-17 03:00" &
cd "$(dirname "$0")/.."
at=$(date -j -f "%Y-%m-%d %H:%M" "$1" +%s 2>/dev/null) || { echo "unreadable time '$1'"; exit 1; }
while [ $(date +%s) -lt $at ]; do sleep 60; done          # the wall clock each minute: a long sleep pauses while the Mac sleeps
for p in $(pgrep -f "teamsearch/cloud/mac_lowel[o].sh") $(pgrep -f "teamsearch/cloud/mac_pause_window[s].sh"); do kill -TERM $p 2>/dev/null; done
procs() { pgrep -f "teamsearch/bin/teamsearch-(py|battle-v[0-9]+|node)"; }
for p in $(procs); do kill -CONT $p 2>/dev/null; kill -TERM $p 2>/dev/null; done
sleep 20; for p in $(procs); do kill -KILL $p 2>/dev/null; done
echo "$(date '+%m-%d %I:%M %p'): stopped for the user's flight (no resume until the user says so); $(procs | wc -l | tr -d ' ') climb processes left" >> round_lowelo.log
