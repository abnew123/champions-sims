#!/bin/bash
cd "$(dirname "$0")"
for w in 0 1; do setsid -f nohup node worker.js jobs_miss.json $w 2 results/miss1 1 1 >> results/miss1_w$w.log 2>&1 < /dev/null; done
