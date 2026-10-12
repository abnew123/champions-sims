#!/bin/zsh
# The learned value with the full damage calc data (2026-10-12): the race features and vfeats with native/champions_data_full.json
# (champions_data.json lacked 1,250 species incl. Basculegion-F); the one-turn search redone for the positions the old calc data could
# not compute; the h64 search net refitted; then the two tests against the bot's current setup (old calc data, old net). Low priority,
# 4 threads; each stage shows on the progress page (http://localhost:8766) as a Battle sim run.
cd "$(dirname $0)"
R=results/value; S=${SCRATCH:-/tmp}; T=4
PY=(env OPENBLAS_NUM_THREADS=1 PYTHONPATH=../.venv/lib/python3.14/site-packages ../native/champ/bin/battlesim-py)
B=../native/champ/bin/battlesim-champ-dev; ED=../native/engine_data_full.json
BASE=(RACE_TIES=avg RACE=1 TRSYM=1 EG_VALUE=egvalue9_sym2.json EG_MEGA_TIE=0 GRID_DIR=$PWD/$R/emptygrid CALC_DATA=../native/champions_data_full.json)
stamp() { python3 -c "import json,os,time,sys; n,out,title,tot=sys.argv[1:5]; d='../evalbar/out/battlesim'; os.makedirs(d,exist_ok=True); json.dump({'title': 'Battle sim: '+title, 'out': os.path.relpath(os.path.abspath(out), os.path.abspath('../evalbar/out')), 'total': int(tot), 'done0': 0, 'started': time.time(), 'threads': $T, 'seeds': 32, 'staged': True}, open(os.path.join(d, n+'.run.json'),'w'))" $1 $2 $3 $4; }
echo "$(date '+%I:%M %p') affected positions"
python3 - <<'PY'
import json, re
old = json.load(open('../native/champions_data.json')); toid = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
osp, omv = set(old['species']), set(old['moves'])
for part in ('fit', 'new', 'hold'):
    n = 0
    with open(f'results/value/real_{part}.pos.jsonl') as f, open(f'results/value/real_{part}_fc.pos.jsonl', 'w') as o:
        for l in f:
            st = json.loads(l)['state']
            if any(not p.get('fainted') and (toid(p['species']) not in osp or any(toid(m['id']) not in omv for m in p['moveSlots'])) for sd in st['sides'] for p in sd['pokemon']):
                o.write(l); n += 1
    print(part, n)
PY
echo "$(date '+%I:%M %p') features with the full calc data"
for part in hold fit new; do rm -f $R/real_$part.vfeats_fc.jsonl; env $BASE RACE_PRIO=1 FEATS22=1 nice -n 10 $B vfeats $ED $R/real_$part.pos.jsonl $R/real_$part.vfeats_fc.jsonl 2 > /dev/null 2>&1; done
for part in hold fit new; do
  n=$(wc -l < $R/real_${part}_fc.pos.jsonl); stamp fc_$part $R/real_${part}_fc.eval.jsonl "one-turn search, full calc data ($part)" $n
  echo "$(date '+%I:%M %p') search $part ($n positions)"; env $BASE EVAL_SEEDS=32 EVAL_ADAPT=1 nice -n 10 $B evalpos $ED $R/real_${part}_fc.pos.jsonl $R/real_${part}_fc.eval.jsonl $T > /dev/null 2>&1
done
echo "$(date '+%I:%M %p') refit"
env VALUE_SUFFIX=_fc OPENBLAS_NUM_THREADS=1 PYTHONPATH=../.venv/lib/python3.14/site-packages nice -n 10 ../native/champ/bin/battlesim-py value_fit.py export 64 1e-3 search fit,new 2>&1 | tail -2
NET=$PWD/$R/vnet_h64_search_fit+new_fc.json; OLD=$PWD/../bot/value/vnet_h64_search.json
echo "$(date '+%I:%M %p') held-out search: full calc + refitted net"
stamp fc_holdsub $S/hold_sub.fc.eval.jsonl "held-out search, refitted net" $(wc -l < $S/hold_sub.pos.jsonl)
rm -f $S/hold_sub.fc.eval.jsonl; env $BASE RACE_PRIO=1 FEATS22=1 EVAL_SEEDS=32 EVAL_ADAPT=1 EG_VNET=$NET nice -n 10 $B evalpos $ED $S/hold_sub.pos.jsonl $S/hold_sub.fc.eval.jsonl $T > /dev/null 2>&1
echo "$(date '+%I:%M %p') self-play"
python3 -c "import json; json.dump(list(range(800)), open('$S/h2big_800.jobs.json','w'))"
for arm in A B C; do
  case $arm in A) X=();; B) X=(EG_VNET=$NET EG_VNET_SIDE=0);; C) X=(EG_VNET=$NET EG_VNET_SIDE=1);; esac
  rm -rf $S/vfc_$arm; echo "$(date '+%H:%M:%S') $S/h2big_800.jobs.json -> $S/vfc_$arm, $T threads (learned value, full calc data, arm $arm)" >> value_fc.log
  env $BASE RACE_PRIO=1 FEATS22=1 DP2=1 BATTLE_ANTICIPATE=1 $X nice -n 10 $B battle $ED $S/h2big_800.jsonl $S/vfc_$arm $T > /dev/null 2>&1
  echo "$(date '+%H:%M:%S') done: arm $arm" >> value_fc.log
done
../.venv/bin/python3 h2test.py report $S/vfc_A $S/vfc_B $S/vfc_C | grep -v "^ *side 0"
echo "$(date '+%I:%M %p') all done"
