#!/bin/zsh
# Before the live bot moves to depth at 4x (2026-10-16, the user): self-play of the new search (deep.rs: 80,000 leaf evaluations a
# decision, depth 2, k0 2) against the bot's exact current one (evalpos's staged search, EVAL_ADAPT with 32 seeds a cell, through
# battle4's BATTLE_ADAPT_SIDE), 800 pool starts both ways on the same luck, with the bot's own rules on both sides (no pointless
# last-Pokemon Protect, no Protect twice running) and its value (sym2 + the h64 net). deep_endgames.py report prints the new search's gain
# ("the deep side"). T threads an arm; each arm shows on the progress page.
#   SP=<scratch dir with deepmid/starts.*> BIN=<champ with BATTLE_ADAPT_SIDE> T=2 ./depth_confirm.sh
ME=${0:A}; cd "$(dirname $ME)"
SP=${SP:?scratch dir} TAG=${TAG:-confirm4x} BUDGET=80000 DEPTH=2 STARTS=${STARTS:-${SP:?}/deepmid/starts} \
  EXTRA="EVAL_DEEP_K0=2 EVAL_ADAPT=1 BATTLE_ADAPT_SEEDS=32 EG_LAST_PROTECT=both EG_NO_DOUBLE_PROTECT=both" \
  ARM_B="BATTLE_EVAL_DEPTH_0=2 BATTLE_ADAPT_SIDE=1" ARM_C="BATTLE_EVAL_DEPTH_1=2 BATTLE_ADAPT_SIDE=0" zsh deep_endgames.sh
