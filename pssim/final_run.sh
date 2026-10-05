#!/bin/bash
# Final 2v2 run (v11): fixed engine (Fake Out, 2 planning seeds, Choice/Protect), fitted score egvalue2.json + Perish terms,
# turn-3 opposing pairs, Trick Room 2/3/3/4, move audit. 8 low-priority workers.
cd "$(dirname "$0")"
export EG_ENGINE=./endgame2.js EG_SEEDS=2 EG_VALUE=egvalue2.json EG_KMIX=1 EG_AUDIT=1
MYTEAM=myteam_c_incin.json ./eg_run2.sh eg_jobs_final.json results/eg_final 4 8
MYTEAM=myteam_7.json ./eg_run2.sh eg_jobs_final_hat.json results/eg_final_hat 4 8
