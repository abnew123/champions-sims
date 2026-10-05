#!/bin/bash
# Head-to-head decider for the sheet's picks (2026-10-04): each close archetype's top 2-3 (lead, back) combos, 32 games per opposing lead
# in 4 chunks of 8, champ-battle-v4 (seeds keyed on the opponent: common random numbers across combos), egvalue5, anticipated switches.
# Workers from cand_workers, read per chunk.
cd "$(dirname "$0")"; set -e
: > battle_pick.log
for c in 1 2 3 4; do
  G0=$((400 + 8 * (c - 1))); T=$(cat cand_workers)
  MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_battle_pick.json battle_pick_starts.jsonl 8 $G0 > /dev/null
  echo "$(date +%H:%M:%S) jobs_battle_pick.json -> results/battle_pick_c$c, 8 games, $T threads (full battles)" >> battle_pick.log
  BATTLE_ANTICIPATE=1 EG_VALUE=egvalue5.json GRID_DIR=../mxtr nice -n 10 ../native/champ/bin/champ-battle-v4 battle ../native/engine_data_spot.json \
    battle_pick_starts.jsonl results/battle_pick_c$c $T 2>> battle_pick.err
  echo "$(date +%H:%M:%S) done: $(ls results/battle_pick_c$c | wc -l | tr -d ' ') result files in results/battle_pick_c$c" >> battle_pick.log
done
echo "$(date +%H:%M:%S) PICK DONE" >> battle_pick.log
