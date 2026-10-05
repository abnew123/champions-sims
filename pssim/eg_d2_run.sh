#!/bin/bash
cd "$(dirname "$0")"; out=results/eg_d2; mkdir -p $out
for ((w=0; w<13; w++)); do MYTEAM=myteam_c_incin.json EG_SEEDS=2 EG_VALUE=egvalue.json node eg_depth2.js eg_jobs_d2.json $w 13 $out 5 >> $out.w$w.log 2>&1 & done
wait; echo "$(date +%H:%M:%S) done: $(ls $out | wc -l | tr -d ' ') files"
