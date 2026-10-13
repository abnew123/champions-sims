#!/bin/zsh
# The learned value after the accuracy fix (champ-battle-v28, 2026-10-13; the user: a Bo1 game's Mega Raichu-Y Zap Cannon): the one-turn
# search redone for the positions where a living Pokemon brings an accuracy modifier into play (No Guard and its Mega stones, Thunder /
# Hurricane / Blizzard with weather possible, accuracy-changing moves, abilities and items, accuracy / evasion stages, Gravity:
# results/value/real_<part>_acc.pos.jsonl), on top of the full calc data's (_fc). Features (real_<part>.vfeats_acc.jsonl) are computed
# for every position before this. Each stage shows on the progress page.
cd "$(dirname $0)"
R=results/value; T=${T:-7}
B=../native/champ/bin/battlesim-champ-v28; ED=../native/engine_data_full.json
stamp() { python3 -c "import json,os,time,sys; n,out,title,tot=sys.argv[1:5]; d='../evalbar/out/battlesim'; os.makedirs(d,exist_ok=True); json.dump({'title': 'Battle sim: '+title, 'out': os.path.relpath(os.path.abspath(out), os.path.abspath('../evalbar/out')), 'total': int(tot), 'done0': 0, 'started': time.time(), 'threads': $T, 'seeds': 32, 'staged': True}, open(os.path.join(d, n+'.run.json'),'w'))" $1 $2 $3 $4; }
for part in ${=PARTS:-hold fit new}; do   # ${=...}: zsh splits it into words
  n=$(wc -l < $R/real_${part}_acc.pos.jsonl); stamp acc_$part $R/real_${part}_acc.eval.jsonl "one-turn search after the accuracy fix ($part)" $n
  echo "$(date '+%I:%M %p') search $part ($n positions)"
  env RACE_TIES=avg RACE=1 TRSYM=1 EG_VALUE=egvalue9_sym2.json EG_MEGA_TIE=0 GRID_DIR=$PWD/$R/emptygrid CALC_DATA=../native/champions_data_full.json EVAL_SEEDS=32 EVAL_ADAPT=1 nice -n 10 $B evalpos $ED $R/real_${part}_acc.pos.jsonl $R/real_${part}_acc.eval.jsonl $T > /dev/null 2>&1
done
echo "$(date '+%I:%M %p') searches done"
