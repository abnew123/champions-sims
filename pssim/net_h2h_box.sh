#!/bin/bash
# Value net against value net on the shared AWS box (2026-10-15, the user: train the net on deeper search values). In the tree of
# value_box.sh (~/battlesim/vb), after `tar xzf net_bundle.tar.gz` there:
#   THREADS=64 bash pssim/net_h2h_box.sh            (PAIRS="new:old ..." picks head-to-heads; default all below, in this order)
# Builds native/champ/src_battle_v35.tar.gz (EG_VNET_B: side 1 on its own net) as h2h_results/battlesim-champ-v35, then plays each pair on
# the 800 pool starts both ways with the bot's search (BATTLE_EVAL, 20,000 leaf evaluations a decision, no depth, sym2 + the net at the
# leaves): arm B the first net on side 0, arm C on side 1, the same starts and luck. deep_endgames.py report prints the first net's gain
# ("the deep side"). Nets in nets/<name>.json:
#   d4    fitted on the depth-at-4x search values (value_box.sh d4)
#   x1    fitted on the one-turn search values at the bot's budget (value_box.sh x1), the same data and settings otherwise
#   acc   the deployed net (bot/value/vnet_h64_search_acc.json)
set -e
cd "$(dirname "$0")/.."
T=${THREADS:-$(nproc)}; SP=$PWD/h2h_results; mkdir -p $SP/grid $SP/deepend
command -v zsh > /dev/null || { sudo apt-get update -qq && sudo apt-get install -y -qq zsh; }
if [ ! -x $SP/battlesim-champ-v35 ]; then
  BD=${BUILD_DIR:-/tmp/bsv35}; rm -rf $BD && mkdir -p $BD && tar xzf native/champ/src_battle_v35.tar.gz -C $BD
  (cd $BD && cargo build --release -q) && cp $BD/target/release/champ $SP/battlesim-champ-v35
  (sha256sum $SP/battlesim-champ-v35 2>/dev/null || shasum -a 256 $SP/battlesim-champ-v35) > $SP/battlesim-champ-v35.sha256
fi
N=$PWD/nets
for pair in ${PAIRS:-d4:acc d4:x1 x1:acc}; do
  a=${pair%:*}; b=${pair#*:}; job=h2h_${a}_$b; [ -f $SP/$job.done ] && { echo "$job: done before"; continue; }
  echo "$(date -u +%H:%M) $job"
  SP=$SP STARTS=$SP/inputs/mid_starts BIN=$SP/battlesim-champ-v35 TAG=$job BUDGET=20000 DEPTH=0 T=$(( T / 2 )) PY=python3 \
    ARM_B="EG_VNET=$N/$a.json EG_VNET_B=$N/$b.json" ARM_C="EG_VNET=$N/$b.json EG_VNET_B=$N/$a.json" \
    zsh pssim/deep_endgames.sh > $SP/$job.report.txt 2>&1 && touch $SP/$job.done
done
echo "$(date -u +%H:%M) all jobs done"; touch $SP/ALL_DONE
