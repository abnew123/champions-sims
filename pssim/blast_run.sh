#!/bin/bash
# Spread study, Blastoise Speed (2026-10-02): Modest 0 Spe (98) and Modest 2 HP / 32 Spe (130) vs the current Quiet (88), 3 cores.
# Waits for the batch-1 game review (which waits for sp_run.sh). Part 1: native 2v2 games on Blastoise's pairs (same jobs and seeds
# as results/sp_base). Part 2: turn-one lead sims for Blastoise leads: stage one per variant, then current + both variants refined on
# the same rows (v11's plus every stage one's picks).
cd "$(dirname "$0")"; set -e
until grep -q "REVIEW DONE" ../recordings/batch1/review.log 2>/dev/null; do sleep 30; done
export EG_SEEDS=2 EG_VALUE=egvalue2.json EG_KMIX=1 TW_UNDER_TR=zero
idx() { python3 -c "import json,sys; J=json.load(open('eg_jobs_final.json')); print(','.join(str(i) for i,j in enumerate(J) if eval(sys.argv[1])))" "$1"; }
JOBS=$(idx "j['mine']==['Blastoise','Indeedee-F']") MYTEAM=myteam_c_incin.json ./eg_run_native.sh eg_jobs_final.json results/sp_base 8 3
for v in b98 b130; do JOBS=$(idx "'Blastoise' in j['mine']") MYTEAM=myteam_s_$v.json ./eg_run_native.sh eg_jobs_final.json results/sp_$v 8 3; done
echo "$(date +%H:%M:%S) BLAST PART 1 DONE"
python3 -c "import json; json.dump([j for j in json.load(open('jobs_inc1.json')) if 'Blastoise' in j['lead']], open('jobs_s1_blast.json','w'))"
for v in b98 b130; do
  MYTEAM=myteam_s_$v.json ./run_jobs.sh jobs_s1_blast.json results/s1_$v 1 3
  rm -rf results/s1m_$v; mkdir -p results/s1m_$v
  python3 -c "
import json,glob,os
for f in glob.glob('results/inc1/*.json'):
    if 'Blastoise' not in json.load(open(f))['myLead']: os.symlink(os.path.abspath(f), 'results/s1m_$v/a_'+os.path.basename(f))
for f in glob.glob('results/s1_$v/*.json'): os.symlink(os.path.abspath(f), 'results/s1m_$v/b_'+os.path.basename(f))"
  TR_SPEEDS=tr_speeds_$v.json READER_W=0.75 TRMULT_FILE=trmult_final.json ../.venv/bin/python3 tr_select.py 0.05 5 --write --res results/s1m_$v --jobs jobs_inc1.json --out sp_sel_$v | tail -1
done
MON=Blastoise python3 sp_refine_jobs2.py jobs_sp_rb sp_sel72 sp_sel_b98 sp_sel_b130
for t in base:myteam_c_incin b98:myteam_s_b98 b130:myteam_s_b130; do
  export MYTEAM=${t#*:}.json
  ./run_jobs.sh jobs_sp_rb.json results/sp_rb_${t%%:*} 12 3
  ITEM_OVERRIDE=Indeedee-F=colburberry ./run_jobs.sh jobs_sp_rb_items.json results/sp_rb_${t%%:*}_colburberry 12 3
  ITEM_OVERRIDE=Indeedee-F=psychicseed ./run_jobs.sh jobs_sp_rb_items.json results/sp_rb_${t%%:*}_psychicseed 12 3
done
echo "$(date +%H:%M:%S) BLAST ALL DONE"
