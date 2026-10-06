#!/bin/bash
# Pack what the hill climb needs on a Linux box into teamsearch/cloud/bundle.tar.gz (run on the Mac, from anywhere).
# Leaves out node_modules (setup.sh reinstalls Showdown), old results, the Mac binaries, teamsearch/runs (battle outputs),
# the first AWS climb's results and any local climb state or pre-filter caches (so a new climb on the box starts fresh), and
# regmatch/ and bring/previews.json (names; the climb needs neither: perish_stock.json and the fitted bring models cover them).
# usage: teamsearch/cloud/pack.sh [battle source tarball, default src_battle_v16.tar.gz]
set -e
cd "$(dirname "$0")/../.."                      # project root
SRC=${1:-src_battle_v16.tar.gz}
OUT=teamsearch/cloud/bundle.tar.gz
EGV=$(ls pssim/egvalue*.json 2>/dev/null || true)            # all value files (small); TS_SIM picks one
COPYFILE_DISABLE=1 tar --no-xattrs -czf "$OUT" \
  --exclude 'teamsearch/runs' --exclude 'teamsearch/cloud/bundle.tar.gz' --exclude 'teamsearch/cloud_results' \
  --exclude 'teamsearch/regmatch' --exclude 'teamsearch/bring/previews.json' --exclude 'teamsearch/climb_*' --exclude 'teamsearch/decomp_threads.txt' --exclude '__pycache__' --exclude '*.log' \
  setup.sh foes.json \
  pssim/package.json pssim/package-lock.json pssim/engine_patch pssim/t1sim.js pssim/seedmix.js pssim/pro_replays.py \
  pssim/opp_model_a.json pssim/opp_model_b.json pssim/myteam_c_incin.json $EGV \
  native/battle_starts.js native/export_state.js native/engine_data_spot.json native/champions_data.json \
  "native/champ/$SRC" native/champ/bin/*.sha256 \
  regionals/regional_teams.json regionals/regional_sets.json regionals/smogon_mc_sets.json regionals/smogon_mc_2026-09_moveset.txt \
  teamsearch
echo "$OUT: $(du -h "$OUT" | cut -f1)  (battle source: $SRC; value files: $EGV)"
