#!/bin/bash
# Torkoal with Life Orb (Hatterene moves to Fairy Feather for Item Clause), queued after the setter runs finish.
cd "$(dirname "$0")"
export TW_UNDER_TR=zero
until [ "$(grep -h -c ALLDONE results/fcol_w0.log results/fcol_w1.log 2>/dev/null | paste -sd+ | bc)" = "2" ]; do sleep 20; done
for w in 0 1; do
  setsid -f bash -c "MYTEAM=myteam_tr_tlo.json node worker.js jobs_tlo.json $w 2 results/tlo 1 12 >> results/tlo_w$w.log 2>&1; echo ALLDONE >> results/tlo_w$w.log" < /dev/null > /dev/null 2>&1
done
