#!/bin/bash
cd "$(dirname "$0")"
while pgrep -f "eg_worker.js eg_jobs1.json" >/dev/null; do sleep 10; done
MYTEAM=myteam_7.json ./eg_run.sh eg_jobs_hat.json results/eg_hat 6 13
