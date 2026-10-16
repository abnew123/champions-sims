#!/bin/bash
# On the box: one-on-one cells (the bring model's features) for the set ids listed in a file, one per line (ids can contain spaces).
# usage: cloud/cells.sh <ids file, relative to teamsearch/> [procs=90]        Log: round_cells.log
cd ~/champions-sims/teamsearch/mx
mapfile -t ids < <(grep -v "^$" ../${1:?ids file})
for t in 0 1; do TR=$t NPROC=${2:-90} ../../.venv/bin/python3 grid_pool.py "${ids[@]}" >> ../round_cells.log 2>&1; done
echo "$(date -u +%H:%M) UTC: cells done" >> ../round_cells.log
