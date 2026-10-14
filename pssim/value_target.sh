#!/bin/zsh
# Which target the position net should learn (2026-10-14, the user chose "fix the value": the bot's own top plays do about 2 points
# worse than its value says and it over-charges human Protect / setup, bot/planner_issues.md "Where the strength gap is"). The deployed
# net (bot/value/vnet_h64_search_acc.json) distills the one-turn search, so it inherits the search's blind spots; here the same data
# (fit + new: ~130k real positions / ~18k games, v28 features, the _fc,_acc search layers) is fitted on the games' results ("outcome")
# or on both ("mix": result log loss + MIX_W x squared error to the search's log-odds), scored on the 560 held-out games' results.
# One single-threaded fit per job, 4 at a time; each job's report goes to results/value/vtarget_<tag>.txt; a progress card counts jobs.
cd "$(dirname $0)"
R=results/value; P=${P:-4}; DONE=$R/vtarget_done.txt
run() {
  local kind=$1 cfg=$2 w=$3 tag=$4
  env VALUE_SUFFIX=_acc VALUE_EVAL_SUFFIXES=_fc,_acc MIX_W=$w OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 \
    PYTHONPATH=../.venv/lib/python3.14/site-packages nice -n 10 ../native/champ/bin/battlesim-py value_fit.py compare $kind fit,new $cfg \
    > $R/vtarget_$tag.txt 2>&1 || { echo "$(date '+%I:%M %p') FAILED $tag (see $R/vtarget_$tag.txt)"; return 1; }   # a failed fit is not done
  echo $tag >> $DONE; echo "$(date '+%I:%M %p') done $tag: $(grep -E 'on (outcome|mix|search)' $R/vtarget_$tag.txt | sed 's/  */ /g')"
}
if [ "$1" = one ]; then run ${@:2}; exit; fi
: > $DONE
JOBS=(
  "search 64:1e-3 0 search_h64"
  "outcome 0:1e-4 0 outcome_lin"
  "outcome 32:3e-3 0 outcome_h32"
  "outcome 64:3e-3 0 outcome_h64_3e-3"
  "outcome 64:1e-2 0 outcome_h64_1e-2"
  "mix 64:1e-3 0.1 mix_h64_w0.1"
  "mix 64:1e-3 0.3 mix_h64_w0.3"
  "mix 64:1e-3 1.0 mix_h64_w1"
)
python3 -c "import json,os,time,sys; d='../evalbar/out/battlesim'; os.makedirs(d,exist_ok=True); json.dump({'title': 'Battle sim: value net targets (outcome / mix / search fits)', 'out': os.path.relpath(os.path.abspath('$DONE'), os.path.abspath('../evalbar/out')), 'total': ${#JOBS}, 'done0': 0, 'started': time.time(), 'threads': $P}, open(os.path.join(d, 'vtarget.run.json'),'w'))"
echo "$(date '+%I:%M %p') ${#JOBS} fits, $P at a time"
printf '%s\n' $JOBS | xargs -P $P -L 1 zsh $0 one; st=$?   # one fit per line, P at a time; xargs exits non-zero if any fit failed
echo "$(date '+%I:%M %p') all done"; grep -h -E 'current static|one-turn search|on (outcome|mix|search)' $R/vtarget_*.txt | sort -u
exit $st
