#!/bin/bash
cd "$(dirname "$0")"
run() { tag=$1; shift; for tr in 1 0; do env "$@" GRID_MONS=Hatterene GRID_TAG="_it_Hatterene_$tag" TR=$tr python3 tr_grid.py > "it_Hatterene_${tag}_tr$tr.log" 2>&1
  echo "Hatterene $tag TR=$tr: $(grep -h 'Counter' it_Hatterene_${tag}_tr$tr.log | tail -1)" >> run_items3.out; done; }
run Babiri HT_ITEM=Babiri
run LifeOrb_terrain HT_ITEM="Life Orb" MY_TERRAIN_MON=Hatterene
run FairyFeather_terrain HT_ITEM="Fairy Feather" MY_TERRAIN_MON=Hatterene
run FocusSash_terrain HT_ITEM="Focus Sash" MY_TERRAIN_MON=Hatterene
echo DONE >> run_items3.out
