#!/bin/zsh
# The v28 net's checks (2026-10-13): self-play arms on the 800 pool starts (A: sym2 both sides; B / C: the refitted net on side 0 / 1,
# sym2 on the other; as value_fc.sh), and the real-pairings style bias (replay_pairs.py) with the net and with sym2 alone. Two lanes of
# 4 threads; each run's start line goes into a pssim/*.log so the progress page shows it.
cd "$(dirname $0)"
SP=${SP:?scratch dir}; B=../native/champ/bin/battlesim-champ-v28; ED=../native/engine_data_full.json
NET=$PWD/results/value/vnet_h64_search_fit+new_acc.json; GRID=$SP/grid; mkdir -p $GRID
run() {   # run <name> <starts.jsonl> <jobs.json> <outdir> <net side: none | both | 0 | 1>
  local name=$1 starts=$2 jobs=$3 out=$4 side=$5
  rm -rf $out; echo "$(date +%H:%M:%S) $jobs -> $out, 4 threads (v28 checks: $name)" > v28_$name.log
  local extra=()
  case $side in both) extra=(EG_VNET=$NET);; 0|1) extra=(EG_VNET=$NET EG_VNET_SIDE=$side);; esac
  env RACE_TIES=avg RACE=1 TRSYM=1 EG_VALUE=egvalue9_sym2.json EG_MEGA_TIE=0 GRID_DIR=$GRID CALC_DATA=../native/champions_data_full.json \
      RACE_PRIO=1 FEATS22=1 DP2=1 BATTLE_ANTICIPATE=1 $extra nice -n 10 $B battle $ED $starts $out 4 >> v28_$name.log 2>&1
  echo "$(date +%H:%M:%S) done: $name" >> v28_$name.log
}
case ${1:?lane} in
  selfplay) for arm in A B C; do case $arm in A) s=none;; B) s=0;; C) s=1;; esac; run selfplay_$arm $SP/h2big_800.jsonl $SP/h2big_800.jobs.json $SP/v28sp_$arm $s; done
            ../.venv/bin/python3 h2test.py report $SP/v28sp_A $SP/v28sp_B $SP/v28sp_C | grep -v "^ *side 0";;
  bias)     run bias_n $SP/bias/pairs_starts.jsonl $SP/bias/pairs.json $SP/bias/v28n both
            run bias_s $SP/bias/pairs_starts.jsonl $SP/bias/pairs.json $SP/bias/v28s none
            PAIRS=$SP/bias/pairs.json PAIRS_ITEMS="Raichunite Y" ../.venv/bin/python3 replay_pairs.py report $SP/bias/v28s $SP/bias/v28n;;
esac
echo "$(date '+%I:%M %p') lane $1 done"
