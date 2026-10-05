#!/bin/bash
# Rillaboom with only 100%-accurate moves (Fake Out, Grassy Glide, Wood Hammer, Stomping Tantrum; 2026-10-03): in Indeedee-F's slot (rilla2)
# and in Incineroar's slot (rillaX: two Fake Out users instead of three). Same method as cand_run.sh; workers from cand_workers.
cd "$(dirname "$0")"; set -e
W() { cat cand_workers; }
export EG_SEEDS=2 EG_VALUE=egvalue2.json EG_KMIX=1 TW_UNDER_TR=zero
(cd ../mxtr && for tr in 1 0; do GRID_MONS=Rillaboom GRID_TAG=_cand_Rillaboom TR=$tr NPROC=$(cat ../pssim/cand_workers) nice -n 10 ../.venv/bin/python3 tr_grid.py > /dev/null; done
 python3 -c "
import json, shutil
for tr in ('tr', 'notr'):
    d = json.load(open(f'gx_cells_{tr}_inc.json')); c = json.load(open(f'gx_cells_{tr}_cand_Rillaboom.json'))
    d.update({k: v for k, v in c.items() if k.split('|')[1] == 'Rillaboom'}); json.dump(d, open(f'grid_rilla/gx_cells_{tr}_inc.json', 'w'))")
idx() { python3 -c "import json,sys; J=json.load(open('eg_jobs_final.json')); print(','.join(str(i) for i,j in enumerate(J) if sys.argv[1] in j['mine']))" "$1"; }
JOBS=$(idx Indeedee-F) GRID_DIR=../mxtr/grid_rilla MYTEAM=myteam_x_rilla2.json ./eg_run_native.sh eg_jobs_final.json results/sp_rilla2 8 $(W)
JOBS=$(idx Incineroar) GRID_DIR=../mxtr/grid_rilla MYTEAM=myteam_x_rillaX.json ./eg_run_native.sh eg_jobs_final.json results/sp_rillaX 8 $(W)
echo "$(date +%H:%M:%S) RILLA2 PART 1 DONE"
for v in rilla2:Indeedee-F:jobs_s1_ind.json rillaX:Incineroar:jobs_s1_inc81.json; do
  t=${v%%:*}; rest=${v#*:}; mon=${rest%%:*}; jf=${rest#*:}
  MYTEAM=myteam_x_$t.json node tr_speeds.js jobs_inc1.json tr_speeds_$t.json | head -1
  MYTEAM=myteam_x_$t.json ./run_jobs.sh $jf results/s1_$t 1 $(W)
  rm -rf results/s1m_$t; mkdir -p results/s1m_$t
  python3 -c "
import json,glob,os
for f in glob.glob('results/inc1/*.json'):
    if '$mon' not in json.load(open(f))['myLead']: os.symlink(os.path.abspath(f), 'results/s1m_$t/a_'+os.path.basename(f))
for f in glob.glob('results/s1_$t/*.json'): os.symlink(os.path.abspath(f), 'results/s1m_$t/b_'+os.path.basename(f))"
  TR_SPEEDS=tr_speeds_$t.json READER_W=0.75 TRMULT_FILE=trmult_final.json EXCLUDE_MOVES="switch -> $mon" ../.venv/bin/python3 tr_select.py 0.05 5 --write --res results/s1m_$t --jobs jobs_inc1.json --out sp_sel_$t | tail -1
done
MON=Indeedee-F python3 sp_refine_jobs2.py jobs_sp_ri2 sp_sel72 sp_sel_rilla2
MON=Incineroar python3 sp_refine_jobs2.py jobs_sp_rx sp_sel72 sp_sel_rillaX
for t in ri2_base:jobs_sp_ri2:myteam_c_incin ri2_rilla2:jobs_sp_ri2:myteam_x_rilla2 rx_base:jobs_sp_rx:myteam_c_incin rx_rillaX:jobs_sp_rx:myteam_x_rillaX; do
  out=${t%%:*}; rest=${t#*:}; jf=${rest%%:*}; export MYTEAM=${rest#*:}.json
  ./run_jobs.sh $jf.json results/sp_$out 12 $(W)
  ITEM_OVERRIDE=Indeedee-F=colburberry ./run_jobs.sh ${jf}_items.json results/sp_${out}_colburberry 12 $(W)
  ITEM_OVERRIDE=Indeedee-F=psychicseed ./run_jobs.sh ${jf}_items.json results/sp_${out}_psychicseed 12 $(W)
done
echo "$(date +%H:%M:%S) RILLA2 ALL DONE"
