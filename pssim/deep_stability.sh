#!/bin/zsh
# Steadying the anytime search's depth (2026-10-14, the user chose to make live depth stable before testing it in self-play): with depth
# the top choice moved between budgets in about half the positions (deep_values.sh). Each setting runs twice on the same positions with
# different luck (EVAL_KEY_SALT 1 and 2); deep_stability.py scores how far its answer moves with the luck alone, and its log loss against
# the real results. Positions: every 5th of the 1,503 held-out ones (about 300), at each position's staged budget (EVAL_BUDGET=spec).
# PAR runs at a time (3), T threads each (2); each shows on the progress page.
#   SP=<scratch dir: battlesim-champ-deep2, hold_sub_b.pos.jsonl> ./deep_stability.sh
ME=${0:A}; cd "$(dirname $ME)"
SP=${SP:?scratch dir}; T=${T:-2}; B=$SP/battlesim-champ-deep2; ED=../native/engine_data_full.json; POS=$SP/stab300.pos.jsonl
awk 'NR % 5 == 1' $SP/hold_sub_b.pos.jsonl > $POS
F=(RACE_TIES=avg RACE=1 TRSYM=1 EG_VALUE=egvalue9_sym2.json EG_MEGA_TIE=0 GRID_DIR=$SP/grid CALC_DATA=../native/champions_data_full.json
   RACE_PRIO=1 FEATS22=1 EVAL_SEEDS=32 EG_VNET=$PWD/../bot/value/vnet_h64_search_acc.json EVAL_TOP=200 EVAL_BUDGET=spec)
CONFIGS=(
  "d0 EVAL_DEPTH=0"
  "d2 EVAL_DEPTH=2"
  "d2k2 EVAL_DEPTH=2 EVAL_DEEP_K0=2"
  "d2k4 EVAL_DEPTH=2 EVAL_DEEP_K0=4"
  "d2k2c2 EVAL_DEPTH=2 EVAL_DEEP_K0=2 EVAL_CHILD_BASE=2"
)
run() {   # run <tag> <salt> <settings...>
  local tag=$1 salt=$2; shift 2; local out=$SP/stab_${tag}_s$salt.eval.jsonl
  python3 -c "import json,os,time; d='../evalbar/out/battlesim'; os.makedirs(d,exist_ok=True); json.dump({'title': 'Battle sim: steadying depth ($tag, luck $salt)', 'out': os.path.relpath('$out', os.path.abspath('../evalbar/out')), 'total': sum(1 for _ in open('$POS')), 'done0': 0, 'started': time.time(), 'threads': $T}, open(os.path.join(d, 'stab_${tag}_s$salt.run.json'),'w'))"
  rm -f $out; env $F $@ EVAL_KEY_SALT=$salt nice -n 10 $B evalpos $ED $POS $out $T > /dev/null 2>&1
  echo "$(date '+%I:%M %p') done $tag luck $salt"
}
todo=(); for c in $CONFIGS; do for salt in 1 2; do todo+=("$salt ${c}"); done; done
for j in $todo; do
  set -- ${=j}; salt=$1; tag=$2; shift 2
  while [ $(pgrep -f "battlesim-champ-deep2 evalpos" | wc -l) -ge ${PAR:-3} ]; do sleep 5; done
  run $tag $salt $@ &
  sleep 2
done
wait
../.venv/bin/python3 deep_stability.py $SP
