#!/bin/bash
cd "$(dirname "$0")"
for c in Sylveon Incineroar Armarouge Sinistcha Grimmsnarl Milotic Archaludon M-Gardevoir; do for tr in 1 0; do
  GRID_MONS=$c GRID_TAG="_cand_$c" TR=$tr python3 tr_grid.py > "cand_${c}_tr$tr.log" 2>&1
  echo "$c TR=$tr: $(grep -h 'Counter' cand_${c}_tr$tr.log | tail -1)" >> run_cands.out
done; done; echo DONE >> run_cands.out
