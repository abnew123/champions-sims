#!/bin/bash
# Lead values with more weight on the reader number: 0.5 check, then 0.75 and 1.0 for the current team and Incineroar.
cd "$(dirname "$0")"
READER_W=0.5 python3 tr_final.py results/r_incin chk_incin_r50.json > results/rw.log 2>&1
for rw in 75 100; do
  for d in v7:tr_final_v7 r_incin:tr_final_c_incin; do src=${d%%:*}; out=${d##*:}
    READER_W=$(python3 -c "print($rw/100)") python3 tr_final.py results/$src ${out}_r$rw.json >> results/rw.log 2>&1
    [ $rw = 75 ] && READER_W=$(python3 -c "print($rw/100)") TRMULT=2 python3 tr_final.py results/$src ${out}_r${rw}_x2.json >> results/rw.log 2>&1
  done
done
echo RWDONE >> results/rw.log
