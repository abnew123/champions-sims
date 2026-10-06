#!/bin/bash
# On the cloud box: power it off (billing stops) once no sims have run for IDLE_MIN minutes, or MAX_H hours after START
# (epoch, first argument; MAX_H = second argument, default 8) regardless. Touch ~/KEEP_ALIVE to suspend the idle rule; the hard cap still applies.
# Busy = the climb, any champ battle/plan/spot binary (champ-battle-vN or a cargo-built champ), position builders, lead-sim workers.
IDLE_MIN=45; MAX_H=${2:-8}; start=${1:-$(date +%s)}; idle=0
BUSY='climb.py round|champ(-battle-v[0-9]+)? (battle|plan|spot)|teamsearch-battle-v[0-9]+ battle|battle_starts|run_jobs|node .*worker'
while true; do
  sleep 300
  if pgrep -f "$BUSY" >/dev/null; then idle=0; else idle=$((idle + 5)); fi
  [ -e /home/ubuntu/KEEP_ALIVE ] && idle=0
  echo "$(date -u +%H:%M) idle=${idle}m" >> /home/ubuntu/watchdog.log
  if [ $idle -ge $IDLE_MIN ] || [ $(( $(date +%s) - start )) -ge $((MAX_H * 3600)) ]; then
    echo "$(date -u +%H:%M) shutting down" >> /home/ubuntu/watchdog.log; sudo shutdown -h now; exit 0
  fi
done
