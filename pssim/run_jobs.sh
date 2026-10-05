#!/bin/bash
# Run a jobs file on N parallel workers (default: all cores but one) and wait for them. Works on macOS and Linux.
#   usage: ./run_jobs.sh <jobs.json> <outdir> <samples> [workers]
#   stage one: 1 sample per cell; refinement: 12. Environment passes through (MYTEAM, TW_UNDER_TR, ITEM_OVERRIDE).
#   Workers skip jobs whose result file already exists, so an interrupted run resumes where it stopped.
#   For long runs start it in the background:  nohup ./run_jobs.sh ... > run.log 2>&1 &
cd "$(dirname "$0")"
jobs=$1; out=$2; ns=${3:-1}
nw=${4:-$(( $(getconf _NPROCESSORS_ONLN) - 1 ))}
[ -z "$jobs" ] || [ -z "$out" ] && { echo "usage: $0 <jobs.json> <outdir> <samples> [workers]"; exit 1; }
mkdir -p "$out"
echo "$(date +%H:%M:%S) $jobs -> $out, $ns sample(s) per cell, $nw workers"
for ((w=0; w<nw; w++)); do node worker.js "$jobs" $w $nw "$out" 1 $ns >> "$out.w$w.log" 2>&1 & done
wait
echo "$(date +%H:%M:%S) done: $(ls "$out" | wc -l | tr -d ' ') result files in $out"
