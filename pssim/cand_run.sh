#!/bin/bash
# Indeedee-slot study (2026-10-02): five candidates in Indeedee-F's slot (team files myteam_x_<tag>.json keep the key "Indeedee-F",
# so every job file, back row and Speed file applies unchanged). Waits for the game re-review. Worker count is read from cand_workers
# before each step (3 while the user plays; raise it when they're away).
#   indatk: Indeedee-F with Psychic instead of Healing Wish   indot: Indeedee-F with Own Tempo (no terrain), Rocky Helmet
#   sinis: Sinistcha (Rage Powder, Trick Room, Matcha Gotcha)  hatt: Hatterene (the old sixth)
#   rilla: Rillaboom (Grassy Surge: fights opposing Psychic/Electric Terrain; Fake Out, Grassy Glide, Wood Hammer, High Horsepower)
# Part 1: native 2v2 games on the slot's five pairs (same jobs and seeds as results/sp_base). Part 2: turn-one lead sims for the slot's
# leads (stage one per candidate, then the current team and all four refined on the same rows); sp_lead_cmp.py compares.
cd "$(dirname "$0")"; set -e
until grep -q "WHATIF DONE" ../recordings/whatif.log 2>/dev/null; do sleep 30; done
W() { cat cand_workers; }
export EG_SEEDS=2 EG_VALUE=egvalue2.json EG_KMIX=1 TW_UNDER_TR=zero
# Rillaboom's one-on-one matchup cells (the planner's value features), merged into its own grid folder like Sinistcha's
(cd ../mxtr && for tr in 1 0; do GRID_MONS=Rillaboom GRID_TAG=_cand_Rillaboom TR=$tr NPROC=$(cat ../pssim/cand_workers) nice -n 10 ../.venv/bin/python3 tr_grid.py > /dev/null; done
 mkdir -p grid_rilla && python3 -c "
import json, shutil
for tr in ('tr', 'notr'):
    d = json.load(open(f'gx_cells_{tr}_inc.json')); c = json.load(open(f'gx_cells_{tr}_cand_Rillaboom.json'))
    d.update({k: v for k, v in c.items() if k.split('|')[1] == 'Rillaboom'}); json.dump(d, open(f'grid_rilla/gx_cells_{tr}_inc.json', 'w'))
    shutil.copy(f'gx_cells_{tr}_inc_ext.json', 'grid_rilla')")
echo "$(date +%H:%M:%S) RILLA GRID DONE"
IDX=$(python3 -c "import json; J=json.load(open('eg_jobs_final.json')); print(','.join(str(i) for i,j in enumerate(J) if 'Indeedee-F' in j['mine']))")
for v in indatk indot sinis hatt rilla; do
  G=../mxtr; [ $v = sinis ] && G=../mxtr/grid_sinis; [ $v = rilla ] && G=../mxtr/grid_rilla
  JOBS=$IDX GRID_DIR=$G MYTEAM=myteam_x_$v.json ./eg_run_native.sh eg_jobs_final.json results/sp_$v 8 $(W)
done
echo "$(date +%H:%M:%S) CAND PART 1 DONE"
python3 -c "import json; json.dump([j for j in json.load(open('jobs_inc1.json')) if 'Indeedee-F' in j['lead']], open('jobs_s1_ind.json','w'))"
for v in indatk indot sinis hatt rilla; do
  MYTEAM=myteam_x_$v.json node tr_speeds.js jobs_inc1.json tr_speeds_$v.json | head -1
  MYTEAM=myteam_x_$v.json ./run_jobs.sh jobs_s1_ind.json results/s1_$v 1 $(W)
  rm -rf results/s1m_$v; mkdir -p results/s1m_$v
  python3 -c "
import json,glob,os
for f in glob.glob('results/inc1/*.json'):
    if 'Indeedee-F' not in json.load(open(f))['myLead']: os.symlink(os.path.abspath(f), 'results/s1m_$v/a_'+os.path.basename(f))
for f in glob.glob('results/s1_$v/*.json'): os.symlink(os.path.abspath(f), 'results/s1m_$v/b_'+os.path.basename(f))"
  TR_SPEEDS=tr_speeds_$v.json READER_W=0.75 TRMULT_FILE=trmult_final.json ../.venv/bin/python3 tr_select.py 0.05 5 --write --res results/s1m_$v --jobs jobs_inc1.json --out sp_sel_$v | tail -1
done
MON=Indeedee-F python3 sp_refine_jobs2.py jobs_sp_ri sp_sel72 sp_sel_indatk sp_sel_indot sp_sel_sinis sp_sel_hatt sp_sel_rilla
for t in base:myteam_c_incin indatk:myteam_x_indatk indot:myteam_x_indot sinis:myteam_x_sinis hatt:myteam_x_hatt rilla:myteam_x_rilla; do
  export MYTEAM=${t#*:}.json
  ./run_jobs.sh jobs_sp_ri.json results/sp_ri_${t%%:*} 12 $(W)
  ITEM_OVERRIDE=Indeedee-F=colburberry ./run_jobs.sh jobs_sp_ri_items.json results/sp_ri_${t%%:*}_colburberry 12 $(W)
  ITEM_OVERRIDE=Indeedee-F=psychicseed ./run_jobs.sh jobs_sp_ri_items.json results/sp_ri_${t%%:*}_psychicseed 12 $(W)
done
echo "$(date +%H:%M:%S) CAND ALL DONE"
