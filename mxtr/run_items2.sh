#!/bin/bash
cd "$(dirname "$0")"
run() { mon=$1; var=$2; item=$3; shift 3; for tr in "$@"; do
    env "$var=$item" GRID_MONS=$mon GRID_TAG="_it_${mon}_$(echo "$item" | tr -d ' ')" TR=$tr python3 tr_grid.py > "it_${mon}_$(echo "$item" | tr -d ' ')_tr$tr.log" 2>&1
    echo "$mon $item TR=$tr: $(grep -h 'Counter' it_${mon}_$(echo "$item" | tr -d ' ')_tr$tr.log | tail -1)" >> run_items2.out; done; }
run Kingambit KG_ITEM "Life Orb" 0; run Kingambit KG_ITEM Occa 1 0
echo DONE >> run_items2.out
