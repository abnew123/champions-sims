#!/bin/bash
# usage: launch.sh <jobs.json> <outDir> <seedStart> <nSeeds> <logPrefix>
cd "$(dirname "$0")"
for w in 0 1; do setsid -f nohup node worker.js "$1" $w 2 "$2" "$3" "$4" >> "$5_w$w.log" 2>&1 < /dev/null; done
