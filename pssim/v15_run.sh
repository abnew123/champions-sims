#!/bin/bash
# Version 15 (2026-10-04): turn-one lines for the other nine tabs' picks re-run with the real sets (myteam_real.json: Brave Kingambit,
# Torkoal 12/0/0/32/22/0) and each tab's planned back row; opposing Indeedee-F item variants; merged into tr_final_v15plus.json. 3 workers.
cd "$(dirname "$0")"; set -e
MYTEAM=myteam_real.json TW_UNDER_TR=zero nice -n 10 ./run_jobs.sh jobs_v15.json results/v15 12 3
for it in colburberry psychicseed; do
  MYTEAM=myteam_real.json TW_UNDER_TR=zero ITEM_OVERRIDE=Indeedee-F=$it nice -n 10 ./run_jobs.sh jobs_v15_items.json results/v15_$it 12 3
done
MYTEAM=myteam_real.json node tr_speeds.js jobs_v15.json tr_speeds_v15new.json | head -1
python3 v15_merge.py
TR_SPEEDS=tr_speeds_v15.json READER_W=0.75 TRMULT_FILE=trmult_final.json nice -n 10 ../.venv/bin/python3 tr_final.py results/v15plus tr_final_v15plus.json > tr_final_v15plus.log 2>&1
echo "V15 DONE $(date +%H:%M:%S)"
