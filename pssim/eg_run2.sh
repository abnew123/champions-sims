#!/bin/bash
# usage: ./eg_run.sh <jobs.json> <outdir> <games> [workers]    (MYTEAM passes through)
cd "$(dirname "$0")"; jobs=$1; out=$2; g=${3:-6}; nw=${4:-$(( $(getconf _NPROCESSORS_ONLN) - 1 ))}
mkdir -p "$out"; echo "$(date +%H:%M:%S) $jobs -> $out, $g games, $nw workers"
for ((w=0; w<nw; w++)); do node eg_worker_v2.js "$jobs" $w $nw "$out" $g >> "$out.w$w.log" 2>&1 & done
wait; echo "$(date +%H:%M:%S) done: $(ls "$out" | wc -l | tr -d ' ') files in $out"
