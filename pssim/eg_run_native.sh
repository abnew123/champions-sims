#!/bin/bash
# 2v2 planner run on the native engine: same games as eg_run2.sh + endgame2.js (starting positions and seeds from JS, the rest in
# Rust; results match the JS planner game for game), about 8x faster per core. Writes <outdir>/<job>.json as each job finishes.
# usage: ./eg_run_native.sh <jobs.json> <outdir> <games> [threads=3]   (MYTEAM, EG_KMIX, EG_SEEDS, EG_VALUE, EG_AUTOPILOT, JOBS pass through)
cd "$(dirname "$0")"; jobs=$1; out=$2; g=${3:-4}; nt=${4:-3}
mkdir -p "$out"; tmp=$(mktemp -d)
echo "$(date +%H:%M:%S) $jobs -> $out, $g games, $nt threads (native)"
node ../native/eg_starts.js "$jobs" "$tmp/starts.jsonl" "$g" || exit 1
GRID_DIR=${GRID_DIR:-../mxtr} ../native/champ/target/release/champ plan ../native/engine_data.json "$tmp/starts.jsonl" "$out" "$nt" 2> "$tmp/plan.log" || { tail -5 "$tmp/plan.log"; exit 1; }
rm -rf "$tmp"; echo "$(date +%H:%M:%S) done: $(ls "$out" | wc -l | tr -d ' ') files in $out"
