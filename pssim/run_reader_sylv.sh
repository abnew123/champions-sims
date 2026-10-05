#!/bin/bash
cd "$(dirname "$0")"
while ! grep -qs SYLVDONE results/cands_resume.log; do sleep 15; done
READER_W=0.75 python3 tr_final.py results/r_sylv tr_final_c_sylv_r75.json > results/rw_sylv.log 2>&1
READER_W=0.75 TRMULT=2 python3 tr_final.py results/r_sylv tr_final_c_sylv_r75_x2.json >> results/rw_sylv.log 2>&1
READER_W=1.0 python3 tr_final.py results/r_sylv tr_final_c_sylv_r100.json >> results/rw_sylv.log 2>&1
echo RWSDONE >> results/rw_sylv.log
