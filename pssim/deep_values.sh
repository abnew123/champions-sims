#!/bin/zsh
# Does the anytime search's depth predict real results better? (2026-10-14, after the endgame playouts were flat: on 200 endgames depth 3
# changed a side's top choice in 144 and the log loss against the real results went 0.2995 -> 0.2780, -0.022 +- 0.034.) The same search
# with and without depth, at the same budget, on (1) the 600 endgame starts (depth 3, 20,000 leaf evaluations) and (2) the 1,503 held-out
# positions (depth 2, each its staged search's own budget: EVAL_BUDGET=spec; hold4_*: 4x that). Scored by deep_values.py. T threads (4),
# one run at a time unless PAR=1; RUNS picks the runs; each run shows on the progress page.
#   SP=<scratch dir: battlesim-champ-deep, deepend/eg600.pos.jsonl, hold_sub_b.pos.jsonl> ./deep_values.sh
ME=${0:A}; cd "$(dirname $ME)"
SP=${SP:?scratch dir}; T=${T:-4}; B=${BIN:-$SP/battlesim-champ-deep}; ED=../native/engine_data_full.json
F=(RACE_TIES=avg RACE=1 TRSYM=1 EG_VALUE=egvalue9_sym2.json EG_MEGA_TIE=0 GRID_DIR=$SP/grid CALC_DATA=../native/champions_data_full.json
   RACE_PRIO=1 FEATS22=1 EVAL_SEEDS=32 EG_VNET=$PWD/../bot/value/vnet_h64_search_acc.json EVAL_TOP=200)
run() {   # run <tag> <positions> <budget env> <depth>
  local tag=$1 pos=$2 bud=$3 d=$4 out=$SP/deepval_$1.eval.jsonl
  python3 -c "import json,os,time,sys; d='../evalbar/out/battlesim'; os.makedirs(d,exist_ok=True); json.dump({'title': 'Battle sim: depth vs none, real results ($tag)', 'out': os.path.relpath('$out', os.path.abspath('../evalbar/out')), 'total': sum(1 for _ in open('$pos')), 'done0': 0, 'started': time.time(), 'threads': $T}, open(os.path.join(d, 'deepval_$tag.run.json'),'w'))"
  echo "$(date '+%I:%M %p') $tag"
  env $F ${=bud} EVAL_DEPTH=$d nice -n 10 $B evalpos $ED $pos $out $T > /dev/null 2>&1
}
one() {   # the named runs (RUNS picks them; PAR=1 runs them side by side, T threads each)
  case $1 in
    eg_d0) run eg_d0 $SP/deepend/eg600.pos.jsonl "EVAL_BUDGET=20000" 0;;
    eg_d3) run eg_d3 $SP/deepend/eg600.pos.jsonl "EVAL_BUDGET=20000" 3;;
    hold_d0) run hold_d0 $SP/hold_sub_b.pos.jsonl "EVAL_BUDGET=spec" 0;;
    hold_d2) run hold_d2 $SP/hold_sub_b.pos.jsonl "EVAL_BUDGET=spec" 2;;
    hold4_d0) run hold4_d0 $SP/hold_sub_b.pos.jsonl "EVAL_BUDGET=spec EVAL_BUDGET_MULT=4" 0;;
    hold4_d2) run hold4_d2 $SP/hold_sub_b.pos.jsonl "EVAL_BUDGET=spec EVAL_BUDGET_MULT=4" 2;;
    holdall_d0) run holdall_d0 $SP/hold_all.pos.jsonl "EVAL_BUDGET=20000" 0;;                     # all 3,968 held-out positions
    holdall_d2k2) run holdall_d2k2 $SP/hold_all.pos.jsonl "EVAL_BUDGET=20000 EVAL_DEEP_K0=2" 2;;
  esac
}
for r in ${=RUNS:-eg_d0 eg_d3 hold_d0 hold_d2}; do if [ -n "$PAR" ]; then one $r & else one $r; fi; done; wait
echo "$(date '+%I:%M %p') done"
