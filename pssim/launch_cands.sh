#!/bin/bash
# First-pass lead screen (1 sample per cell) for three sixth-slot candidates, back to back on two workers.
cd "$(dirname "$0")"
export TW_UNDER_TR=zero
for w in 0 1; do
  setsid -f bash -c "for tag in incin arma sylv; do MYTEAM=myteam_c_\$tag.json node worker.js jobs_c_\$tag.json $w 2 results/c_\$tag 1 1 >> results/c_\${tag}_w$w.log 2>&1; done; echo ALLDONE >> results/cands_w$w.log" < /dev/null > /dev/null 2>&1
done
