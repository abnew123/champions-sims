#!/bin/bash
# When Armarouge's first pass is done: pause Sylveon's first pass, refine Armarouge's best leads, then resume Sylveon.
cd "$(dirname "$0")"
while [ $(ls results/c_arma | wc -l) -lt 300 ]; do sleep 15; done
sleep 8; pkill -STOP -f "^node worker.js jobs_c_sylv"
python3 make_cand_refine.py arma 0.03 > results/refine_arma.txt 2>&1
./launch_rcand.sh arma; sleep 30
while ! (grep -qs ALLDONE results/r_arma_w0.log && grep -qs ALLDONE results/r_arma_w1.log); do sleep 20; done
pkill -CONT -f "^node worker.js jobs_c_sylv"; echo resumed_sylv >> results/cands_resume.log
