#!/bin/bash
# Double-Protect ban test (2026-10-04, champ-battle-v5): the sheet's fours vs all archetypes' 6 leads, 16 games each (first game index 4000),
# played three ways on the same seeds: as is, with my side unable to Protect twice in a row (EG_NO_DOUBLE_PROTECT=0), and with their side
# unable to (=1). Per-turn state log on. 5 threads, arms one after another (after the planning-seed test's 2-seed arm ends).
# Analysis: dp_test_report.py
cd "$(dirname "$0")"; : > dp_test.log
until grep -q "done ns=2" ns_test.log; do sleep 15; done
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_dp_test.json dp_test_starts.jsonl 16 4000 >> dp_test.log
for arm in base ban0 ban1; do
  case $arm in base) E="";; ban0) E="EG_NO_DOUBLE_PROTECT=0";; ban1) E="EG_NO_DOUBLE_PROTECT=1";; esac
  echo "$(date +%H:%M:%S) start $arm" >> dp_test.log
  env $E BATTLE_TURNS=1 BATTLE_ANTICIPATE=1 EG_VALUE=egvalue5.json GRID_DIR=../mxtr_t22 nice -n 10 ../native/champ/bin/champ-battle-v5 battle \
    ../native/engine_data_spot.json dp_test_starts.jsonl results/dp_test_$arm 5 2>> dp_test_$arm.err
  echo "$(date +%H:%M:%S) done $arm $(ls results/dp_test_$arm | wc -l)" >> dp_test.log
done
rm -f dp_test_starts.jsonl; echo "$(date +%H:%M:%S) ALL DONE" >> dp_test.log
