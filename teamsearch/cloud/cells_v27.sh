#!/bin/bash
# On the box, before the v27 climb: one-on-one cells (the bring model's features) for every set in the 40 starts and the swap pool
# that has none yet (cells_v27.txt, written on the Mac). Log: round_cells.log. About a minute per set per mode on one core.
cd ~/champions-sims/teamsearch/mx
mapfile -t ids < <(grep -v "^$" ../cells_v27.txt)                  # one set per line: ids can contain spaces (M-Raichu X#3)
for t in 0 1; do TR=$t NPROC=${1:-90} ../../.venv/bin/python3 grid_pool.py "${ids[@]}" >> ../round_cells.log 2>&1; done
echo "$(date -u +%H:%M) UTC: cells done" >> ../round_cells.log
