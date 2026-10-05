#!/bin/bash
# Turn-one refinement for two decider contenders without turn-one plans (Balance: Farigiraf+Blastoise, Snow: Incineroar+Farigiraf),
# after the decider; then merged into results/v11plus for the sheet build. 3 workers.
cd "$(dirname "$0")"; set -e
until grep -q "PICK DONE" battle_pick.log 2>/dev/null; do sleep 20; done
MYTEAM=myteam_c_incin.json TW_UNDER_TR=zero nice -n 10 ./run_jobs.sh jobs_v11c.json results/v11c 12 3
for f in results/v11c/*.json; do ln -sf "$(pwd)/$f" results/v11plus/v11c_$(basename "$f"); done
echo "V11C DONE $(date +%H:%M:%S)"
