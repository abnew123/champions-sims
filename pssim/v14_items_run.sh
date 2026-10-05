#!/bin/bash
# Version 14 Indeedee TR lead: opposing Indeedee-F item variants (Colbur Berry, Psychic Seed) for the turn-one mix, Trick Room speeds for the
# new lead, then the merged turn-one file tr_final_v14plus.json (v11plus + results/v14_itr). 3 workers.
cd "$(dirname "$0")"; set -e
until grep -q "V14 ITR DONE" v14_itr_run.log 2>/dev/null; do sleep 10; done
for it in colburberry psychicseed; do
  MYTEAM=myteam_real.json TW_UNDER_TR=zero ITEM_OVERRIDE=Indeedee-F=$it nice -n 10 ./run_jobs.sh jobs_v14_itr_items.json results/v14_itr_$it 12 3
done
MYTEAM=myteam_real.json node tr_speeds.js jobs_v14_itr.json tr_speeds_v14itr.json
python3 -c "import json; a=json.load(open('tr_speeds_inc2.json')); a.update(json.load(open('tr_speeds_v14itr.json'))); json.dump(a, open('tr_speeds_v14.json','w'))"
for s in "" _colburberry _psychicseed; do
  rm -rf results/v14plus$s; mkdir -p results/v14plus$s
  for f in results/v11plus$s/*.json; do ln -s "$(readlink -f "$f")" results/v14plus$s/$(basename "$f"); done
  for f in results/v14_itr$s/*.json; do ln -s "$(pwd)/$f" results/v14plus$s/v14_$(basename "$f"); done
done
TR_SPEEDS=tr_speeds_v14.json READER_W=0.75 TRMULT_FILE=trmult_final.json nice -n 10 ../.venv/bin/python3 tr_final.py results/v14plus tr_final_v14plus.json > tr_final_v14plus.log 2>&1
echo "V14 ITEMS DONE $(date +%H:%M:%S)"
