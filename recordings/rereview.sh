#!/bin/bash
# Re-review with the opponent's actual move always among the replies (after the Blastoise study; 3-core budget)
cd "$(dirname "$0")/../pssim"
until grep -q "BLAST ALL DONE" blast_run.log; do sleep 30; done
MYTEAM=myteam_c_incin.json node ../native/spot_starts.js ../recordings/spots.json ../recordings/spots.jsonl
EG_VALUE=egvalue2.json GRID_DIR=../mxtr nice -n 10 ../native/champ/target_spot/release/champ spot ../native/engine_data_spot.json \
  ../recordings/spots.jsonl ../recordings/review_v2.json 3 8
echo "REREVIEW DONE $(date +%H:%M:%S)"
