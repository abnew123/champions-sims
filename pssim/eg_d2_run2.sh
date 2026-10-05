#!/bin/bash
# usage: ./eg_d2_run2.sh <jobs.json> <outDir> <valueFile> [K=5]
cd "$(dirname "$0")"; jobs=$1; out=$2; val=$3; k=${4:-5}; mkdir -p $out; echo "$(date +%H:%M:%S) $jobs -> $out, two-turn check, K=$k"
for ((w=0; w<13; w++)); do MYTEAM=myteam_c_incin.json EG_SEEDS=2 EG_VALUE=$val node eg_depth2.js $jobs $w 13 $out $k >> $out.w$w.log 2>&1 & done
wait; echo "$(date +%H:%M:%S) done: $(ls $out | wc -l | tr -d ' ') files"
