#!/bin/bash
# Item variants for the setters, run back to back on two workers: Indeedee with Rocky Helmet, then Farigiraf with Colbur Berry.
cd "$(dirname "$0")"
export TW_UNDER_TR=zero
for w in 0 1; do
  setsid -f bash -c "
    for tag in rh fcol; do
      MYTEAM=myteam_tr_\$tag.json node worker.js jobs_\$tag.json $w 2 results/\$tag 1 12 >> results/\${tag}_w$w.log 2>&1
      for it in colburberry psychicseed; do MYTEAM=myteam_tr_\$tag.json ITEM_OVERRIDE=Indeedee-F=\$it node worker.js jobs_\${tag}_items.json $w 2 results/\${tag}_\$it 1 12 >> results/\${tag}_w$w.log 2>&1; done
      echo ALLDONE >> results/\${tag}_w$w.log
    done" < /dev/null > /dev/null 2>&1
done
