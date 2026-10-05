#!/bin/bash
cd "$(dirname "$0")"
for w in 0 1; do setsid -f nohup node worker.js jobs_sal.json $w 2 results/sal1 1 1 >> results/sal1_w$w.log 2>&1 < /dev/null; done
