#!/bin/bash
# Battle sim's depth tests on the shared AWS box (2026-10-14, the user: share Team search's box tonight). From the project root on the box,
# after Team search's remote_setup.sh (Rust, Node and the repo layout in place) and `tar xzf battlesim_bundle.tar.gz` there:
#   THREADS=192 bash pssim/battlesim_box.sh            (JOBS="mid_d2k2 ..." picks jobs; default all, in this order)
# Builds the current engine (native/champ/src_battle_deep.tar.gz) as battlesim_results/battlesim-champ-deep2, then runs each job on all
# THREADS, one after another (each job writes battlesim_results/<job>.done when complete and is skipped on a rerun). Results stay in
# battlesim_results/ (deepend/<tag>_B|C job files, deepval_*.eval.jsonl, *.log); Battle sim scores them on the Mac
# (deep_endgames.py report, deep_values.py).
#   mid_d2k2     800 pool starts both ways, depth 2 (k0 2) vs none, 20,000 leaf evaluations a decision     ~37 core-hours
#   acc          the 3,968 held-out positions, depth 2 (k0 2) vs none at 20,000                            ~9
#   mid4_d2k2    the same head-to-head at 80,000 a decision for both sides                                 ~150
#   mid4_ctrl    no depth, 80,000 vs 20,000 a decision (does more search win games at all?)                ~90
#   mid_d2k4     depth 2 with k0 4 vs none, 20,000                                                         ~37
#   mid_d3k2     depth 3 with k0 2 vs none, 20,000                                                         ~37
set -e
cd "$(dirname "$0")/.."
T=${THREADS:-$(nproc)}; SP=$PWD/battlesim_results; mkdir -p $SP/grid $SP/deepend
command -v zsh > /dev/null || { sudo apt-get update -qq && sudo apt-get install -y -qq zsh; }
if [ ! -x $SP/battlesim-champ-deep2 ]; then
  BD=${BUILD_DIR:-/tmp/bsdeep}; rm -rf $BD && mkdir -p $BD && tar xzf native/champ/src_battle_deep.tar.gz -C $BD
  (cd $BD && cargo build --release -q) && cp $BD/target/release/champ $SP/battlesim-champ-deep2
  ln -sf battlesim-champ-deep2 $SP/battlesim-champ-deep
  (sha256sum $SP/battlesim-champ-deep2 2>/dev/null || shasum -a 256 $SP/battlesim-champ-deep2) > $SP/battlesim-champ-deep2.sha256
fi
H=$(( T / 2 ))   # threads per arm (the two arms of a head-to-head run side by side)
head2head() {   # head2head <job> <budget> <depth> <extra settings> [ARM_B ARM_C]
  local job=$1; [ -f $SP/$job.done ] && { echo "$job: done before"; return; }
  echo "$(date -u +%H:%M) $job"
  SP=$SP STARTS=$SP/inputs/mid_starts BIN=$SP/battlesim-champ-deep2 TAG=$job BUDGET=$2 DEPTH=$3 EXTRA="$4" ARM_B="$5" ARM_C="$6" T=$H PY=python3 \
    zsh pssim/deep_endgames.sh > $SP/$job.report.txt 2>&1 && touch $SP/$job.done
}
for job in ${JOBS:-mid_d2k2 acc mid4_ctrl mid4_d2k2 mid_d2k4 mid_d3k2}; do
  case $job in
    mid_d2k2)  head2head mid_d2k2 20000 2 "EVAL_DEEP_K0=2";;
    mid4_d2k2) head2head mid4_d2k2 80000 2 "EVAL_DEEP_K0=2";;
    mid4_ctrl) head2head mid4_ctrl 20000 0 "" "BATTLE_EVAL_BUDGET_0=80000" "BATTLE_EVAL_BUDGET_1=80000";;
    mid_d2k4)  head2head mid_d2k4 20000 2 "EVAL_DEEP_K0=4";;
    mid_d3k2)  head2head mid_d3k2 20000 3 "EVAL_DEEP_K0=2";;
    acc) [ -f $SP/acc.done ] && { echo "acc: done before"; continue; }
         echo "$(date -u +%H:%M) acc"
         cp $SP/inputs/hold_all.pos.jsonl $SP/hold_all.pos.jsonl
         SP=$SP BIN=$SP/battlesim-champ-deep2 RUNS="holdall_d0 holdall_d2k2" T=$T zsh pssim/deep_values.sh > $SP/acc.log 2>&1 && touch $SP/acc.done;;
  esac
done
echo "$(date -u +%H:%M) all jobs done"; touch $SP/ALL_DONE
