#!/bin/bash
# What-if review (G2 T1 with the Zoroark disguised as Excadrill), after the re-review; the candidate study waits for this.
cd "$(dirname "$0")/../pssim"
until grep -q "REREVIEW DONE" ../recordings/rereview.log; do sleep 20; done
MYTEAM=myteam_c_incin.json node ../native/spot_starts.js ../recordings/whatif.json ../recordings/whatif.jsonl
EG_VALUE=egvalue2.json GRID_DIR=../mxtr nice -n 10 ../native/champ/target_spot/release/champ spot ../native/engine_data_spot.json \
  ../recordings/whatif.jsonl ../recordings/whatif_review.json 3 8
echo "WHATIF DONE $(date +%H:%M:%S)"
