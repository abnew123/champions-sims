#!/bin/bash
# M-B calibration sims (backtest/calib_mb.py) on 3 Mac cores: the games whose fours carry a v43 mechanic on v43n1, then the rest on
# v41n1. WAIT_AC=1: first wait for AC power (the Mac on battery), then resume the paused v2 backtest (process group V2_PGID) too.
cd "$(dirname "$0")/.."
export TS_MOVESET=backtest/smogon_mb_2026-08_moveset.txt TS_THREADS=3 PYTHONPATH=$(ls -d ../.venv/lib/python*/site-packages | head -1):$PWD
if [ "$WAIT_AC" = 1 ]; then
  until pmset -g batt | head -1 | grep -q 'AC Power'; do sleep 60; done
  if [ -n "$V2_PGID" ] && kill -CONT -"$V2_PGID" 2>/dev/null; then echo "$(date '+%I:%M %p') resumed on AC power" >> backtest/v2/selfplay.log; fi
fi
bin/teamsearch-py backtest/calib_mb.py v43 2500 6
bin/teamsearch-py backtest/calib_mb.py 2500 6
