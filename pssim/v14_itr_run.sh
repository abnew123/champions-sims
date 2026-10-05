#!/bin/bash
# Turn-one refinement for the Version 14 Indeedee TR pick (Farigiraf+Kingambit lead, Blastoise+Incineroar back; bring matrix + fresh
# confirmation, 2026-10-04) with the real sets (myteam_real.json: Brave Kingambit, Torkoal 12/0/0/32/22/0). 3 workers.
cd "$(dirname "$0")"; set -e
MYTEAM=myteam_real.json TW_UNDER_TR=zero nice -n 10 ./run_jobs.sh jobs_v14_itr.json results/v14_itr 12 3
echo "V14 ITR DONE $(date +%H:%M:%S)"
