#!/bin/bash
# On the cloud box, from ~/champions-sims: replay a team's flagged results on another setup that shares their folders, then every
# step after them, then both-sides-pick rounds until there is nothing left to search. Log: sheets/<team>/work/replay.log ("REPLAY DONE").
#   usage: (SHEET_SETUP=<setup> setsid nohup sheetkit/cloud/replay.sh <team> <threads> [moves] > /dev/null 2>&1 < /dev/null &)
#   moves: also replay results where either four carries one of these (e.g. healingwish,memento for v20 -> v23)
cd "$(dirname "$0")/../.."; T=${1:?team}; N=${2:?threads}; M=${3:-}; W=sheets/$T/work; L=$W/replay.log
: "${SHEET_SETUP:?set SHEET_SETUP to the setup to replay on}"
say() { echo "$(date -u '+%H:%M UTC') $*" >> $L; }
say "replay of $T on $SHEET_SETUP${M:+ (also results with $M)}"
python3 sheetkit/kit.py $T flagged --write ${M:+--moves $M} >> $L 2>&1 || { say "FAILED: flagged"; exit 1; }
for f in all more; do [ -f $W/$f.log ] && mv $W/$f.log $W/$f.before_replay_$(date +%s).log; done
sheetkit/cloud/all.sh $T $N; grep -q "ALL DONE" $W/all.log || { say "FAILED in all.sh (see all.log)"; exit 1; }
for r in 1 2 3 4; do
  sheetkit/cloud/more.sh $T $N; grep -q "MORE DONE" $W/more.log || { say "FAILED in more.sh (see more.log)"; exit 1; }
  grep -q "nothing to do" $W/more.log && break
  mv $W/more.log $W/more_replay_r$r.log; say "both-sides-pick round $r done"
done
say "REPLAY DONE"
