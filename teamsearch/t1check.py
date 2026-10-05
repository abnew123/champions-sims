"""Do the sim's opponents open like real players? For every modelled lead pair, compare the opponent's turn-1 clicks in existing
battle outputs (the other thread's runs: pssim/results/battle_guide_c*/ 'states' and battle_sheet*/ 'log'; our side = the Trick Room
six) with the replay model's turn-1 click rates for that pair (pssim/opp_model_{a,b}.json 'pairs[].t1', ~5,000 ladder replays).
Analysis only, no battles. Caveat: replay rates are against everyone, the sim's against the Trick Room six.
  python3 t1check.py
"""
import json, os, glob, re, collections
PS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pssim')
OPP = {**json.load(open(os.path.join(PS, 'opp_model_a.json'))), **json.load(open(os.path.join(PS, 'opp_model_b.json')))}

def parse_side(label):
    """'Gengar: Sludge Bomb -> Raichu (Mega) | Incineroar: Fake Out -> Raichu' -> {mon: move or '(switch)'}"""
    out = {}
    for part in label.split(' | '):
        m = re.match(r'\s*(?:T\d+ )?([^:]+): (.*)', part)
        if not m: continue
        mon, act = m.group(1).strip().split('-Mega')[0], m.group(2).strip()
        out[mon] = '(switch)' if act.startswith('switch to') else re.sub(r'\s*(->.*|\(Mega\))$', '', act).strip()
    return out

sim = collections.defaultdict(collections.Counter)            # (arch, pair, mon) -> move counts on turn 1
for d in glob.glob(os.path.join(PS, 'results', 'battle_guide_c*')) + glob.glob(os.path.join(PS, 'results', 'battle_sheet*')):
    for f in glob.glob(os.path.join(d, '*.json')):
        r = json.load(open(f))
        for x in r['rows']:
            t1 = None
            if x.get('states'): t1 = x['states'][0].get('b')
            elif x.get('log'): t1 = x['log'][0].split(' || ')[1].split('  [')[0] if ' || ' in x['log'][0] else None
            if not t1: continue
            for mon, mv in parse_side(t1).items(): sim[(r['arch'], r['pair'], mon)][mv] += 1

def real_t1(arch, pair, mon):
    for p in OPP[arch]['pairs']:
        if p['pair'] == pair and mon in p.get('t1', {}):
            return {k.strip(): float(v) for k, v in (x.rsplit(':', 1) for x in p['t1'][mon].split(', '))}
    return None

rows = []
for (arch, pair, mon), c in sim.items():
    rt = real_t1(arch, pair, mon)
    if not rt: continue
    n = sum(c.values()); st = {k: v / n for k, v in c.items()}
    keys = set(rt) | set(st); tv = 0.5 * sum(abs(st.get(k, 0) - rt.get(k, 0)) for k in keys)
    gaps = sorted(((st.get(k, 0) - rt.get(k, 0), k) for k in keys), key=lambda t: -abs(t[0]))[:3]
    rows.append((tv, arch, pair, mon, n, gaps))
print(f"{len(rows)} (lead pair, Pokemon) cells with both sim and replay turn-1 data; mean difference (total variation) "
      f"{sum(r[0] for r in rows) / len(rows):.2f}\n")
key_moves = ('Tailwind', 'Trick Room', 'Protect', '(switch)', 'Fake Out', 'Perish Song', 'Follow Me', 'Rage Powder', 'Icy Wind', 'Aurora Veil')
agg = collections.defaultdict(lambda: [0.0, 0.0, 0])
for tv, arch, pair, mon, n, gaps in rows:
    rt = real_t1(arch, pair, mon); c = sim[(arch, pair, mon)]; tot = sum(c.values())
    for k in key_moves:
        if k in rt or k in c:
            a = agg[k]; a[0] += rt.get(k, 0); a[1] += c.get(k, 0) / tot; a[2] += 1
print('turn-1 click rate of key moves, averaged over the lead Pokemon that have them (real ladder vs sim opponents):')
for k, (r_, s_, m) in sorted(agg.items(), key=lambda kv: -kv[1][2]):
    print(f"  {k:12s} real {100 * r_ / m:5.1f}%   sim {100 * s_ / m:5.1f}%   ({m} lead Pokemon)")
print('\nbiggest per-Pokemon differences (sim minus real, top 3 moves):')
for tv, arch, pair, mon, n, gaps in sorted(rows, key=lambda r: -r[0])[:18]:
    print(f"  {tv:.2f}  {arch[:22]:22s} {pair:28s} {mon:12s} n={n:4d}  " + ', '.join(f"{k} {100 * g:+.0f}" for g, k in gaps))
