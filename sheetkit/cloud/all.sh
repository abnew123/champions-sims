#!/bin/bash
# On the cloud box, from ~/champions-sims: every step after the bring-matrix jobs, in order, for one team, with N threads.
# Each step resumes where it stopped, so after an interruption run the same command again. Log: sheets/<team>/work/all.log
#   usage: (setsid nohup sheetkit/cloud/all.sh <team> <threads> > /dev/null 2>&1 < /dev/null &)
cd "$(dirname "$0")/../.."; T=${1:?team}; N=${2:?threads}; L=sheets/$T/work/all.log
k() { echo "$(date -u '+%H:%M UTC') kit.py $T $*" >> $L; python3 sheetkit/kit.py $T "$@" >> $L 2>&1 || { echo "$(date -u '+%H:%M UTC') FAILED: $*" >> $L; exit 1; }; }
k matrix run --threads $N; k matrix report; k confirm jobs; k confirm run --threads $N; k confirm decide --write
k optimal run --threads $N; k optimal report; k optimal adopt
k t1 jobs; k t1 run --workers $N; k t1 solve; k guide run --threads $N; k guide report
echo "$(date -u '+%H:%M UTC') ALL DONE" >> $L
