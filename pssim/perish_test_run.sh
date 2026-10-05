#!/bin/bash
# Perish trap value test (2026-10-05, champ-battle-v11): the sheet's four vs the Perish archetype's 6 leads (jobs_perish_test.json),
# 16 games each (first game index 8000), settled sets (32 HP Torkoal) and the generic grid, DP2=1 RACE=1 egvalue7, with the old Perish
# adjustment (base) and with PERISH2=1 (trapped + counted = doomed). Same seeds for both. 1 thread each, side by side.
# Analysis: python3 perish_report.py results/perish_base results/perish_p2
cd "$(dirname "$0")"; : > perish_test.log
MYTEAM=myteam_real_tork32.json node ../native/battle_starts.js jobs_perish_test.json perish_test_starts.jsonl 16 8000 >> perish_test.log
for arm in base p2; do
  ( E=""; [ $arm = p2 ] && E="PERISH2=1"
    echo "$(date +%H:%M:%S) jobs_perish_test.json -> results/perish_$arm, 16 games, 1 threads (full battles, Perish value test)" >> perish_test.log
    env $E DP2=1 RACE=1 CALC_DATA=../native/champions_data.json BATTLE_TURNS=1 BATTLE_LOG=1 BATTLE_ANTICIPATE=1 EG_VALUE=egvalue7.json GRID_DIR=../sheets/trick-room-six/work/grid nice -n 10 \
      ../native/champ/bin/champ-battle-v11 battle ../native/engine_data_spot.json perish_test_starts.jsonl results/perish_$arm 1 2>> perish_$arm.err
    echo "$(date +%H:%M:%S) done $arm $(ls results/perish_$arm | wc -l)" >> perish_test.log ) &
done
wait; rm -f perish_test_starts.jsonl; echo "$(date +%H:%M:%S) ALL DONE" >> perish_test.log
