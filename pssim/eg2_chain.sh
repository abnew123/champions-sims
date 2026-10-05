#!/bin/bash
cd "$(dirname "$0")"; export EG_SEEDS=2
MYTEAM=myteam_c_incin.json ./eg_run.sh eg_jobs_tc.json results/eg2_tc 6 13
MYTEAM=myteam_c_lariat.json ./eg_run.sh eg_jobs_lar.json results/eg2_lar 6 13
python3 -c "
import json, shutil, os
idx = json.load(open('eg_jobs_tc_idx.json'))
for k, i in enumerate(idx):
    s = f'results/eg2_tc/{k}.json'
    if os.path.exists(s) and not os.path.exists(f'results/eg2/{i}.json'): shutil.copy(s, f'results/eg2/{i}.json')
"
MYTEAM=myteam_c_incin.json ./eg_run.sh eg_jobs1.json results/eg2 6 13
MYTEAM=myteam_7.json ./eg_run.sh eg_jobs_hat.json results/eg2_hat 6 13
