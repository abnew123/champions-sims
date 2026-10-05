#!/bin/bash
# Spread study (2026-10-02), 3 cores. Part 1: native 2v2 games, current team vs one changed spread at a time (same seeds, 8 games per
# job). Part 2: turn-one lead sims for Incineroar Brave 72 vs Adamant 81 (stage one for 81, then both refined on the same rows).
cd "$(dirname "$0")"; set -e
export EG_SEEDS=2 EG_VALUE=egvalue2.json EG_KMIX=1 TW_UNDER_TR=zero
idx() { python3 -c "import json,sys; J=json.load(open('eg_jobs_final.json')); m=sys.argv[1]
print(','.join(str(i) for i,j in enumerate(J) if (m in j['mine'] if m else j['mine']!=['Blastoise','Indeedee-F'])))" "$1"; }
JOBS=$(idx "") MYTEAM=myteam_c_incin.json ./eg_run_native.sh eg_jobs_final.json results/sp_base 8 3
for v in tork:Torkoal inc81:Incineroar gambit:Kingambit fari:Farigiraf; do
  JOBS=$(idx ${v#*:}) MYTEAM=myteam_s_${v%%:*}.json ./eg_run_native.sh eg_jobs_final.json results/sp_${v%%:*} 8 3
done
echo "$(date +%H:%M:%S) PART 1 DONE"
python3 -c "import json; json.dump([j for j in json.load(open('jobs_inc1.json')) if 'Incineroar' in j['lead']], open('jobs_s1_inc81.json','w'))"
MYTEAM=myteam_s_inc81.json ./run_jobs.sh jobs_s1_inc81.json results/s1_inc81 1 3
rm -rf results/s1m_inc81; mkdir -p results/s1m_inc81
python3 -c "
import json,glob,os
for f in glob.glob('results/inc1/*.json'):
    if 'Incineroar' not in json.load(open(f))['myLead']: os.symlink(os.path.abspath(f), 'results/s1m_inc81/a_'+os.path.basename(f))
for f in glob.glob('results/s1_inc81/*.json'): os.symlink(os.path.abspath(f), 'results/s1m_inc81/b_'+os.path.basename(f))"
TR_SPEEDS=tr_speeds_inc2.json READER_W=0.75 TRMULT_FILE=trmult_final.json ../.venv/bin/python3 tr_select.py 0.05 5 --write --res results/inc1 --jobs jobs_inc1.json --out sp_sel72 | tail -1
TR_SPEEDS=tr_speeds_inc81.json READER_W=0.75 TRMULT_FILE=trmult_final.json ../.venv/bin/python3 tr_select.py 0.05 5 --write --res results/s1m_inc81 --jobs jobs_inc1.json --out sp_sel81 | tail -1
python3 sp_refine_jobs.py sp_sel72 sp_sel81 jobs_sp_r
for t in 72:myteam_c_incin 81:myteam_s_inc81; do
  export MYTEAM=${t#*:}.json
  ./run_jobs.sh jobs_sp_r.json results/sp_r${t%%:*} 12 3
  ITEM_OVERRIDE=Indeedee-F=colburberry ./run_jobs.sh jobs_sp_r_items.json results/sp_r${t%%:*}_colburberry 12 3
  ITEM_OVERRIDE=Indeedee-F=psychicseed ./run_jobs.sh jobs_sp_r_items.json results/sp_r${t%%:*}_psychicseed 12 3
done
echo "$(date +%H:%M:%S) ALL DONE"
