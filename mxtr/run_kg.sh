#!/bin/bash
# Kingambit column only: {Adamant, Brave} x {Chople, Focus Sash} x {Trick Room up, no Trick Room}
cd "$(dirname "$0")"
for nat in Adamant Brave; do for item in Chople "Focus Sash"; do for tr in 1 0; do
  tagitem=$( [ "$item" = "Chople" ] && echo chople || echo sash )
  KG_NAT=$nat KG_ITEM="$item" GRID_MONS=Kingambit GRID_TAG="_kg_${nat}_${tagitem}" TR=$tr python3 tr_grid.py > "kg_${nat}_${tagitem}_tr$tr.log" 2>&1
  echo "$nat $item TR=$tr: $(tail -2 kg_${nat}_${tagitem}_tr$tr.log | head -1)"
done; done; done
