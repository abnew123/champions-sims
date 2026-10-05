#!/bin/bash
# Full 4v4 battles of the sheet's plans (2026-10-03, first version): each archetype's main lead + back row vs its six likeliest opposing
# leads (t1sim's replay model), 8 games each, the user's real sets (myteam_real.json). Waits for the Rillaboom study; workers from
# cand_workers. Writes a start line to battle_sheet.log so the progress page shows it.
cd "$(dirname "$0")"; set -e
# (no wait: started directly)
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_battle_sheet.json battle_sheet_starts.jsonl 8 > /dev/null
echo "$(date +%H:%M:%S) jobs_battle_sheet.json -> results/battle_sheet, 8 games, $(cat cand_workers) threads (full battles)" > battle_sheet.log
BATTLE_LOG=1 EG_VALUE=egvalue2.json GRID_DIR=../mxtr nice -n 10 ../native/champ/target_spot/release/champ battle ../native/engine_data_spot.json \
  battle_sheet_starts.jsonl results/battle_sheet $(cat cand_workers) 2> battle_sheet.err
echo "$(date +%H:%M:%S) done: $(ls results/battle_sheet | wc -l | tr -d ' ') result files in results/battle_sheet" >> battle_sheet.log
echo "$(date +%H:%M:%S) BATTLE DONE" >> battle_sheet.log
