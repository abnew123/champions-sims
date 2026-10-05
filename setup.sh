#!/bin/bash
# One-time setup for the Trick Room Six sims on a Mac (or Linux). Run from this folder: ./setup.sh
#   - installs Showdown's engine (pokemon-showdown 0.11.11) into pssim/ and applies this project's Champions data fixes
#   - makes a Python virtual environment in .venv with numpy and scipy
#   - unpacks champions-sims-results.tar.xz (if it sits next to this folder or inside it) and rebuilds the derived result folders
set -e
cd "$(dirname "$0")"
command -v node >/dev/null || { echo "Node.js 18 or newer is needed (e.g. brew install node)."; exit 1; }
command -v python3 >/dev/null || { echo "python3 is needed."; exit 1; }
echo "node $(node --version), $(python3 --version)"

echo "== engine"
(cd pssim && npm install --no-audit --no-fund)
E=pssim/node_modules/pokemon-showdown/dist/data
grep -q '"version": "0.11.11"' pssim/node_modules/pokemon-showdown/package.json || { echo "expected pokemon-showdown 0.11.11"; exit 1; }
cp pssim/engine_patch/dist/data/mods/champions/abilities.js pssim/engine_patch/dist/data/mods/champions/items.js \
   pssim/engine_patch/dist/data/mods/champions/moves.js "$E/mods/champions/"
cp pssim/engine_patch/dist/data/pokedex.js "$E/"
echo "Champions data fixes applied (see pssim/engine_patch/champions-data.diff)"

echo "== python"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet numpy scipy
echo "use it with: source .venv/bin/activate"

echo "== results"
R=""
for f in champions-sims-results.tar.xz ../champions-sims-results.tar.xz; do [ -f "$f" ] && R="$f" && break; done
if [ -n "$R" ]; then
  tar xJf "$R" -C pssim
  (cd pssim && ../.venv/bin/python3 make_inc_team.py)
else
  echo "champions-sims-results.tar.xz not found; skipping (new runs still work, comparisons with old runs won't)"
fi

echo "== smoke test"
(cd pssim && MYTEAM=myteam_c_incin.json node -e "const T=require('./t1sim.js'); console.log('engine ok:', Object.keys(T.MY).join(', '), '|', Object.keys(T.OPP).length, 'archetypes')")
echo "setup done"
