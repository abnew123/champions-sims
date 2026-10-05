#!/bin/bash
# Pack what the hill climb needs on a Linux box into teamsearch/cloud/bundle.tar.gz (run on the Mac, from anywhere).
# Leaves out node_modules (setup.sh reinstalls Showdown), old results, the Mac binaries and teamsearch/runs (battle outputs).
# usage: teamsearch/cloud/pack.sh [battle source tarball, default src_battle_v3.tar.gz]
set -e
cd "$(dirname "$0")/../.."                      # project root
SRC=${1:-src_battle_v3.tar.gz}
OUT=teamsearch/cloud/bundle.tar.gz
EGV=$(ls pssim/egvalue2.json pssim/egvalue[45]*.json 2>/dev/null || true)
COPYFILE_DISABLE=1 tar --no-xattrs -czf "$OUT" \
  --exclude 'teamsearch/runs' --exclude 'teamsearch/cloud/bundle.tar.gz' --exclude '__pycache__' --exclude '*.log' \
  setup.sh foes.json \
  pssim/package.json pssim/package-lock.json pssim/engine_patch pssim/t1sim.js pssim/seedmix.js \
  pssim/opp_model_a.json pssim/opp_model_b.json pssim/myteam_c_incin.json $EGV \
  native/battle_starts.js native/export_state.js native/engine_data_spot.json native/champions_data.json \
  "native/champ/$SRC" native/champ/bin/*.sha256 \
  regionals/regional_teams.json regionals/regional_sets.json regionals/smogon_mc_sets.json regionals/smogon_mc_2026-09_moveset.txt \
  teamsearch
echo "$OUT: $(du -h "$OUT" | cut -f1)  (battle source: $SRC; value files: $EGV)"
