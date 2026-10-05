"""Opposing pairs for the autopilot 2v2: drawn from real teams (Reg M-C regional team lists + last week's ladder sixes), two members of the same
team. Half "common" (teams at their natural frequency), half "unusual" (at least one member on under 2% of teams, with a real teammate).
Sets: the Pokemon's most common regional set (open team sheets), else the ladder model's set, else its Smogon Reg M-C set, else skipped. Spreads follow the nature (default).
usage: python3 auto_pairs.py <n_per_half> <out.json>"""
import json, sys, random, collections, re
random.seed(31)
N = int(sys.argv[1]); outf = sys.argv[2]
REG = '../regionals/'
teams = json.load(open(REG + 'regional_teams.json')); sets = json.load(open(REG + 'regional_sets.json'))
ladder = json.load(open('endpairs.json'))['rows']
O = {**json.load(open('opp_model_a.json')), **json.load(open('opp_model_b.json'))}
def sd(name):                                          # regional display name -> Showdown species
    fix = {'Female Indeedee': 'Indeedee-F', 'Male Indeedee': 'Indeedee', 'Eternal Flower Floette': 'Floette-Eternal', 'Female Meowstic': 'Meowstic-F',
           'Male Meowstic': 'Meowstic', 'Maushold': 'Maushold'}
    if name in fix: return fix[name]
    m = re.match(r'(Alolan|Galarian|Hisuian|Paldean) (.+)', name)
    if m: return f"{m.group(2)}-{ {'Alolan': 'Alola', 'Galarian': 'Galar', 'Hisuian': 'Hisui', 'Paldean': 'Paldea'}[m.group(1)] }"
    return name
# most common regional set per species
cnt = collections.defaultdict(collections.Counter); full = {}
for k, S in sets.items():
    for s in S:
        sp = sd(s['species']); key = (s['item'], s['ability'], s['nature'], tuple(sorted(s['moves'])))
        cnt[sp][key] += 1; full[(sp, key)] = s
regset = {sp: dict(full[(sp, c.most_common(1)[0][0])], species=sp) for sp, c in cnt.items()}
def ladder_set(sp):
    for d in O.values():
        if sp in d['sets']:
            it, ab, nat, mv = re.sub(r' \(.*\)$', '', d['sets'][sp]).split('|'); return {'species': sp, 'item': it, 'ability': ab, 'nature': nat, 'moves': mv.split('/')}
    return None
SM = json.load(open(REG + 'smogon_mc_sets.json'))           # Smogon Reg M-C moveset stats (Sept 2026): everything used on ladder
def smogon_set(sp):
    k = sp if sp in SM else next((x for x in SM if x.startswith(sp + '-Mega')), None)
    if not k: return None
    s = dict(SM[k]); s['species'] = sp
    if '-Mega' in k: s['ability'] = ''                       # pre-Mega ability: filled from the dex by the engine side
    return s
setfor = lambda sp: regset.get(sp) or ladder_set(sp) or smogon_set(sp)
pool = [[sd(x.replace('-', ' ').title()) if False else x for x in t['six']] for t in teams]          # regional sixes (already Showdown-style names)
pool += [r['six'] for r in ladder]
use = collections.Counter(m for six in pool for m in set(six)); common = {m for m, c in use.items() if c / len(pool) >= 0.02}   # unusual: on under 2% of teams
def draw(unusual):
    for _ in range(1000):
        six = random.choice(pool); six = [m for m in six if setfor(m)]
        if len(six) < 2: continue
        if unusual:
            rare = [m for m in six if m not in common]
            if not rare: continue
            a = random.choice(rare); b = random.choice([m for m in six if m != a])
        else:
            a, b = random.sample(six, 2)
        return sorted([a, b])
out = []
for half, unusual in (('common', False), ('unusual', True)):
    seen = set()
    while sum(1 for o in out if o['half'] == half) < N:
        p = draw(unusual)
        if tuple(p) in seen: continue
        seen.add(tuple(p)); out.append({'half': half, 'theirs': p, 'sets': [setfor(m) for m in p]})
json.dump(out, open(outf, 'w'), indent=1)
print(len(out), 'pairs;', 'unusual examples:', [o['theirs'] for o in out if o['half'] == 'unusual'][:12])
print('common examples:', [o['theirs'] for o in out if o['half'] == 'common'][:8])
