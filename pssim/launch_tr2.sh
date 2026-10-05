#!/bin/bash
# Refinement for the Trick Room team: 12 samples per cell on the contender leads, then the opposing Indeedee-F item variants.
cd "$(dirname "$0")"
export MYTEAM=myteam_tr.json TW_UNDER_TR=zero
for w in 0 1; do
  setsid -f bash -c "node worker.js jobs_tr2.json $w 2 results/tr2 1 12 >> results/tr2_w$w.log 2>&1; for it in colburberry psychicseed; do ITEM_OVERRIDE=Indeedee-F=\$it node worker.js jobs_tr2_items.json $w 2 results/tr2_\$it 1 12 >> results/tr2_w$w.log 2>&1; done" < /dev/null > /dev/null 2>&1
done
