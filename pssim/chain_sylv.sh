#!/bin/bash
# When Sylveon's first pass is done: pick its best leads, refine them at 12 samples (+ opposing Indeedee-F items), then value them.
cd "$(dirname "$0")"
while [ $(ls results/c_sylv | wc -l) -lt 300 ]; do sleep 15; done
sleep 5
python3 stage1_cmp.py incin arma sylv > results/stage1_all.txt 2>&1
python3 make_cand_refine.py sylv 0.03 > results/refine_sylv.txt 2>&1
./launch_rcand.sh sylv; sleep 30
while ! (grep -qs ALLDONE results/r_sylv_w0.log && grep -qs ALLDONE results/r_sylv_w1.log); do sleep 20; done
python3 tr_final.py results/r_sylv tr_final_c_sylv.json > results/trf_sylv.log 2>&1
TRMULT=2 python3 tr_final.py results/r_sylv tr_final_c_sylv_x2.json > results/trf_sylv_x2.log 2>&1
echo SYLVDONE >> results/cands_resume.log
