#!/bin/bash
# On the cloud box, from ~/champions-sims, after all.sh: one more both-sides-pick round for the tabs whose pick changed (their new pick's
# own strongest answers), then the steps that follow from the picks again. Log: sheets/<team>/work/more.log
#   usage: (setsid nohup sheetkit/cloud/more.sh <team> <threads> > /dev/null 2>&1 < /dev/null &)
cd "$(dirname "$0")/../.."; T=${1:?team}; N=${2:?threads}; L=sheets/$T/work/more.log
k() { echo "$(date -u '+%H:%M UTC') kit.py $T $*" >> $L; python3 sheetkit/kit.py $T "$@" >> $L 2>&1 || { echo "$(date -u '+%H:%M UTC') FAILED: $*" >> $L; exit 1; }; }
k optimal run --threads $N --only more; k optimal report; k optimal adopt
k t1 jobs; k t1 run --workers $N; k t1 solve; k guide run --threads $N; k guide report
echo "$(date -u '+%H:%M UTC') MORE DONE" >> $L
