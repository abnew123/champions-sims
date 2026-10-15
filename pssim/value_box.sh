#!/bin/bash
# Search targets for the value net from the rebuilt data (2026-10-15, the user: train the net on deeper search values; depth 2 at 4x the
# bot's budget won +3.9 +- 1.1 in self-play). On the shared AWS box, in its own tree (~/battlesim/vb), after
# `tar xzf value_bundle.tar.gz` there:
#   THREADS=32 bash pssim/value_box.sh            (JOBS picks runs; default all, in this order)
# Builds the engine (native/champ/src_battle_v34.tar.gz) as vb_results/battlesim-champ-v34, then for each part (hold, val, fit_sub: the
# rebuilt positions, fit_sub = every other turn of the training games) two searches with the bot's settings and the h64 net at the leaves:
#   x1   EVAL_BUDGET=20000 EVAL_DEPTH=0                      (the one-turn search at about the bot's budget)
#   d4   EVAL_BUDGET=80000 EVAL_DEPTH=2 EVAL_DEEP_K0=2       (depth at 4x)
# evalpos resumes by name, so a rerun continues; <part>_<run>.done marks a finished run. Results in vb_results/; scored on the Mac.
set -e
cd "$(dirname "$0")/.."
T=${THREADS:-$(nproc)}; SP=$PWD/vb_results; mkdir -p $SP/grid
if [ ! -x $SP/battlesim-champ-v34 ]; then
  BD=${BUILD_DIR:-/tmp/bsv34}; rm -rf $BD && mkdir -p $BD && tar xzf native/champ/src_battle_v34.tar.gz -C $BD
  (cd $BD && cargo build --release -q) && cp $BD/target/release/champ $SP/battlesim-champ-v34
  (sha256sum $SP/battlesim-champ-v34 2>/dev/null || shasum -a 256 $SP/battlesim-champ-v34) > $SP/battlesim-champ-v34.sha256
fi
F=(RACE_TIES=avg RACE=1 TRSYM=1 EG_VALUE=egvalue9_sym2.json EG_MEGA_TIE=0 GRID_DIR=$SP/grid CALC_DATA=../native/champions_data_full.json
   RACE_PRIO=1 FEATS22=1 EVAL_SEEDS=32 EG_VNET=$PWD/bot/value/vnet_h64_search_acc.json)
for job in ${JOBS:-hold_x1 hold_d4 val_x1 val_d4 fit_sub_x1 fit_sub_d4}; do
  part=${job%_*}; run=${job##*_}; [ -f $SP/$job.done ] && { echo "$job: done before"; continue; }
  case $run in x1) X=(EVAL_BUDGET=20000 EVAL_DEPTH=0);; d4) X=(EVAL_BUDGET=80000 EVAL_DEPTH=2 EVAL_DEEP_K0=2);; esac
  echo "$(date -u +%H:%M) $job ($(wc -l < $SP/inputs/real_$part.pos.jsonl) positions)"
  (cd pssim && env "${F[@]}" "${X[@]}" nice -n 10 $SP/battlesim-champ-v34 evalpos ../native/engine_data_full.json $SP/inputs/real_$part.pos.jsonl $SP/real_${part}_$run.eval.jsonl $T > $SP/$job.log 2>&1) && touch $SP/$job.done
done
echo "$(date -u +%H:%M) all jobs done"; touch $SP/ALL_DONE
