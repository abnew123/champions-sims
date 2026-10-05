#!/bin/bash
# Full-battle lead picks, confirmation (2026-10-03): each archetype's top 2 (lead, back) combos from stage two, replayed on fresh seeds
# (games 8-23, 16 per opposing lead), same settings. The sheet plan's games 8-23 are in results/b32_v5a (same seeds) for a paired comparison.
cd "$(dirname "$0")"; set -e
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_battle_leads3.json battle_leads3_starts.jsonl 16 8 > /dev/null
T=$(cat cand_workers)
echo "$(date +%H:%M:%S) jobs_battle_leads3.json -> results/battle_leads3, 16 games, $T threads (full battles)" > battle_leads3.log
BATTLE_ANTICIPATE=1 EG_VALUE=egvalue5.json GRID_DIR=../mxtr nice -n 10 ../native/champ/bin/champ-battle-v2 battle ../native/engine_data_spot.json \
  battle_leads3_starts.jsonl results/battle_leads3 $T 2> battle_leads3.err
echo "$(date +%H:%M:%S) done: $(ls results/battle_leads3 | wc -l | tr -d ' ') result files in results/battle_leads3" >> battle_leads3.log
