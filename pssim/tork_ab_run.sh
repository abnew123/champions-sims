#!/bin/bash
# Torkoal spread A/B in full battles (2026-10-04): the sheet's four (bringcf_picks.json) on every tab that brings Torkoal, against the
# archetype's 6 opposing leads, 64 games each (first game index 2000). Seeds are keyed on the opponent, so both spreads play the same
# games. Each spread is planned with its own matchup grid (old 32 HP / 2 SpD: ../mxtr; new 12 HP / 22 SpD: ../mxtr_t22).
# 10 threads in total (5 per spread). Analysis: python3 tork_ab_report.py
cd "$(dirname "$0")"; : > tork_ab.log
for arm in old new; do
  if [ $arm = old ]; then T=myteam_real_tork32.json; G=../mxtr; else T=myteam_real.json; G=../mxtr_t22; fi
  ( MYTEAM=$T node ../native/battle_starts.js jobs_tork_ab.json tork_ab_starts_$arm.jsonl 64 2000 >> tork_ab.log
    echo "$(date +%H:%M:%S) start $arm" >> tork_ab.log
    BATTLE_ANTICIPATE=1 EG_VALUE=egvalue5.json GRID_DIR=$G nice -n 10 ../native/champ/bin/champ-battle-v4 battle ../native/engine_data_spot.json \
      tork_ab_starts_$arm.jsonl results/tork_ab_$arm 5 2>> tork_ab_$arm.err
    rm -f tork_ab_starts_$arm.jsonl; echo "$(date +%H:%M:%S) done $arm $(ls results/tork_ab_$arm | wc -l)" >> tork_ab.log ) &
done
wait; echo "$(date +%H:%M:%S) ALL DONE" >> tork_ab.log
