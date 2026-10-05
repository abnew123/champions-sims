#!/bin/bash
# Our Indeedee with Psychic Seed instead of Colbur Berry: every refined job that leads with Indeedee, plus the opposing Indeedee-F item variants.
cd "$(dirname "$0")"
export MYTEAM=myteam_tr_seed.json TW_UNDER_TR=zero
for w in 0 1; do
  setsid -f bash -c "node worker.js jobs_seed.json $w 2 results/seed 1 12 >> results/seed_w$w.log 2>&1; for it in colburberry psychicseed; do ITEM_OVERRIDE=Indeedee-F=\$it node worker.js jobs_seed_items.json $w 2 results/seed_\$it 1 12 >> results/seed_w$w.log 2>&1; done; echo ALLDONE >> results/seed_w$w.log" < /dev/null > /dev/null 2>&1
done
