#!/bin/bash
# Strategy-guide data (2026-10-04): the v12 sheet's plans (jobs_battle_guide.json: each archetype's main lead + back row vs its six
# likeliest opposing leads), 64 games per opposing lead in 4 chunks of 16 (fresh seeds from 200), champ-battle-v4 with the per-turn state
# log (BATTLE_TURNS), egvalue5, anticipated switches. Workers from cand_workers, read per chunk.
cd "$(dirname "$0")"; set -e
: > battle_guide.log
for c in 1 2 3 4; do
  G0=$((200 + 16 * (c - 1))); T=$(cat cand_workers)
  MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_battle_guide.json battle_guide_starts.jsonl 16 $G0 > /dev/null
  echo "$(date +%H:%M:%S) jobs_battle_guide.json -> results/battle_guide_c$c, 16 games, $T threads (full battles)" >> battle_guide.log
  BATTLE_TURNS=1 BATTLE_ANTICIPATE=1 EG_VALUE=egvalue5.json GRID_DIR=../mxtr nice -n 10 ../native/champ/bin/champ-battle-v4 battle ../native/engine_data_spot.json \
    battle_guide_starts.jsonl results/battle_guide_c$c $T 2>> battle_guide.err
  echo "$(date +%H:%M:%S) done: $(ls results/battle_guide_c$c | wc -l | tr -d ' ') result files in results/battle_guide_c$c" >> battle_guide.log
done
echo "$(date +%H:%M:%S) GUIDE DONE" >> battle_guide.log
