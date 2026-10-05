#!/bin/bash
cd "$(dirname "$0")"
for w in 0 1; do
  setsid -f bash -c "node worker.js jobs_sal2.json $w 2 results/sal2 1 12 >> results/sal2_w$w.log 2>&1; for it in colburberry psychicseed; do ITEM_OVERRIDE=Indeedee-F=\$it node worker.js jobs_sal2_items.json $w 2 results/sal2_\$it 1 12 >> results/sal2_w$w.log 2>&1; done" < /dev/null > /dev/null 2>&1
done
