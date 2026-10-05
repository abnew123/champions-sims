#!/bin/bash
# Full-battle lead picks, stage 2 (2026-10-03): each archetype's top 4 leads from stage one (results/battle_train2) plus the sheet's lead,
# each with its 3 strongest back pairs by 2v2 (plus the sheet's own back row), 8 games per opposing lead; champ-battle-v2, egvalue5,
# anticipated switches, the user's real sets. Workers from cand_workers.
cd "$(dirname "$0")"; set -e
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_battle_leads2.json battle_leads2_starts.jsonl 8 > /dev/null
T=$(cat cand_workers)
echo "$(date +%H:%M:%S) jobs_battle_leads2.json -> results/battle_leads2, 8 games, $T threads (full battles)" > battle_leads2.log
BATTLE_ANTICIPATE=1 EG_VALUE=egvalue5.json GRID_DIR=../mxtr nice -n 10 ../native/champ/bin/champ-battle-v2 battle ../native/engine_data_spot.json \
  battle_leads2_starts.jsonl results/battle_leads2 $T 2> battle_leads2.err
echo "$(date +%H:%M:%S) done: $(ls results/battle_leads2 | wc -l | tr -d ' ') result files in results/battle_leads2" >> battle_leads2.log
