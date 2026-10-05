#!/bin/bash
# 12-sample refinement of a sixth-slot candidate's best leads, then the opposing Indeedee-F item variants. Usage: launch_rcand.sh <tag>
cd "$(dirname "$0")"; tag=$1
export MYTEAM=myteam_c_$tag.json TW_UNDER_TR=zero
for w in 0 1; do
  setsid -f bash -c "node worker.js jobs_r_$tag.json $w 2 results/r_$tag 1 12 >> results/r_${tag}_w$w.log 2>&1; for it in colburberry psychicseed; do ITEM_OVERRIDE=Indeedee-F=\$it node worker.js jobs_r_${tag}_items.json $w 2 results/r_${tag}_\$it 1 12 >> results/r_${tag}_w$w.log 2>&1; done; echo ALLDONE >> results/r_${tag}_w$w.log" < /dev/null > /dev/null 2>&1
done
