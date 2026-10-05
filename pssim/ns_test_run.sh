#!/bin/bash
# Double-Protect mechanism test (2026-10-04): the sheet's fours vs all archetypes' 6 leads, 4 games each (first game index 3000), played
# with 2 planning seeds per turn (the default) and with 8, same starts. Per-turn state log on. 5 threads (2 + 3). Analysis: protect_sim.py
cd "$(dirname "$0")"; : > ns_test.log
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_ns_test.json ns_test_starts.jsonl 4 3000 >> ns_test.log
for ns in 2 8; do
  th=$([ $ns = 2 ] && echo 2 || echo 3)
  ( BATTLE_NS=$ns BATTLE_TURNS=1 BATTLE_ANTICIPATE=1 EG_VALUE=egvalue5.json GRID_DIR=../mxtr_t22 nice -n 10 ../native/champ/bin/champ-battle-v4 battle \
      ../native/engine_data_spot.json ns_test_starts.jsonl results/ns_test_$ns $th 2>> ns_test_$ns.err
    echo "$(date +%H:%M:%S) done ns=$ns $(ls results/ns_test_$ns | wc -l)" >> ns_test.log ) &
done
wait; rm -f ns_test_starts.jsonl; echo "$(date +%H:%M:%S) ALL DONE" >> ns_test.log
