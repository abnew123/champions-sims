#!/bin/bash
# One-on-one grid, one column at a time, for each item worth checking (plus each column's current item as a baseline).
cd "$(dirname "$0")"
run() { mon=$1; var=$2; item=$3; shift 3
  for tr in 1 0; do
    env "$var=$item" GRID_MONS=$mon GRID_TAG="_it_${mon}_$(echo "$item" | tr -d ' ')" TR=$tr python3 tr_grid.py > "it_${mon}_$(echo "$item" | tr -d ' ')_tr$tr.log" 2>&1
    echo "$mon $item TR=$tr: $(grep -h 'Counter' it_${mon}_$(echo "$item" | tr -d ' ')_tr$tr.log | tail -1)"
  done; }
run Torkoal TK_ITEM Charcoal; run Torkoal TK_ITEM "Life Orb"; run Torkoal TK_ITEM Leftovers
run Hatterene HT_ITEM "Life Orb"; run Hatterene HT_ITEM "Fairy Feather"; run Hatterene HT_ITEM "Focus Sash"; run Hatterene HT_ITEM Sitrus
run Farigiraf FG_ITEM Sitrus; run Farigiraf FG_ITEM Colbur
run Kingambit KG_ITEM "Black Glasses"; run Kingambit KG_ITEM "Life Orb"; run Kingambit KG_ITEM Occa
