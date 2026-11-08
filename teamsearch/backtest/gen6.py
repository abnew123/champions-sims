"""Whole-six generator for the M-B to M-C backtest (the user, 2026-11-08: "Is there a way to generate entire 6s to try? rather than
purely iterating from existing teams. Like most teams have similar themes (type coverage, special and physical damage, one or two
megas, etc)"). M-B data only; fixed together with cover6.py's metric and committed before any coverage number on M-C was seen.
Disclosure: written after the Nov 8 diagnosis of v2 had shown two M-C facts (Indeedee-F is played with Mega Gardevoir; Mega Golisopod
on rain). The rules below are generic mechanics, nothing is special-cased; rain covering Fire-weak members (sun: Water-weak) is
standard knowledge but was added knowing the Golisopod fact, so cover6.py also reports the generator without it (NOGUARD).
Sets are described by what they do, not by species:
  - setters: Trick Room, Tailwind, Perish Song, each weather and terrain (abilities, a Mega's own ability, or the move);
  - beneficiaries: Trick Room, base Speed <= 60 with 2+ attacks; Tailwind, 60-110; weather / terrain, the boosted attack type (an -ate
    ability's Normal moves count as their new type), the abilities and moves it powers, members weak to the type it weakens (rain:
    Fire, sun: Water, Misty: Dragon), Rock in sand and Ice in snow; terrains only for grounded members; Perish, trappers;
  - roles: Fake Out, redirection (Follow Me, Rage Powder), Intimidate; Mega; physical or special (more attacks of that category).
A template is a real M-B sheet (Aug 26 - Sep 8, one vote per player, Sep 1-4 out-of-format games left out) read as a profile: its
plans (each setter kind on it, with its setter and beneficiary counts), Mega count, role counts, physical and special attackers.
A six is built from a template by filling those needs one by one with sets that meet them (weight: the forme's prior times the set's
share of the forme, times 1 + the other open needs it also meets), then any set, favouring ones that help the team's plans; kept if
its Megas match the template, physical / special attackers are within one, every plan has its setters and at most one beneficiary
short, and no attack type hits more members super-effectively than M-B's 95th percentile (types, Levitate and absorbing abilities).
Each plan keeps its kind with probability 1/2, otherwise takes a kind of its family drawn evenly (speed control: Trick Room or
Tailwind; field: the four weathers and four terrains; Perish), so mechanics M-B rarely played get templates too.
Anchored sixes (every other six): a new M-C forme, the anchors taking turns, placed first; one of its plans (setter or beneficiary)
picked evenly decides the template (one with a plan of that family, instantiated as the anchor's kind); with no plan, a template that
has one of its roles.
Prior per forme: half its M-B usage share, half even across the universe (new formes: the even half only). Sets: a forme's M-B sheet
sets (>= 10% of its sheets, at most 4) or, for new formes, the v2 blind sets (mb_blind_v2.json, equal shares). Item and species
clauses hold. Universes: A, the backtest catalog's 86 formes (mb_swap_pool_v2.json: what the sims can play now); B, every M-B forme on
>= 0.25% of players' sheets plus the new formes.
Variants: roles (no template members kept), keep (0-3 of the template's own members kept first, evenly), keep without the weather guard
rule (NOGUARD); baselines: random (prior-weighted legal sixes: clauses, <= 2 Megas) and mbtop (M-B's most common sixes).
Out: backtest/gen6/<variant>_<universe>.json (N_MAX sixes, any prefix has the anchored / free mix). Seed fixed.
  python3 backtest/gen6.py
"""
import json, os, sys, random, collections, datetime, bisect
HERE = os.path.dirname(os.path.abspath(__file__)); TS = os.path.dirname(HERE); OUT = os.path.join(HERE, 'gen6')
sys.path.insert(0, TS); sys.path.insert(0, HERE)
import sets_lib as L
from calib_fit import window_games
N_MAX, SEED, TRIES = 4000, 6, 40
FIELD = ('sun', 'rain', 'sand', 'snow', 'grassy', 'psychic', 'electric', 'misty'); SPEED = ('tr', 'tailwind')
FAMILY = {**{k: FIELD for k in FIELD}, **{k: SPEED for k in SPEED}, 'perish': ('perish',)}
TERRAIN = {'grassy', 'psychic', 'electric', 'misty'}
SETTER_AB = {'Drought': 'sun', 'Orichalcum Pulse': 'sun', 'Drizzle': 'rain', 'Sand Stream': 'sand', 'Snow Warning': 'snow',
             'Grassy Surge': 'grassy', 'Psychic Surge': 'psychic', 'Electric Surge': 'electric', 'Hadron Engine': 'electric', 'Misty Surge': 'misty'}
SETTER_MV = {'Sunny Day': 'sun', 'Rain Dance': 'rain', 'Sandstorm': 'sand', 'Snowscape': 'snow', 'Chilly Reception': 'snow',
             'Grassy Terrain': 'grassy', 'Psychic Terrain': 'psychic', 'Electric Terrain': 'electric', 'Misty Terrain': 'misty',
             'Trick Room': 'tr', 'Tailwind': 'tailwind', 'Perish Song': 'perish'}
BEN_AB = {'sun': {'Chlorophyll', 'Solar Power', 'Protosynthesis', 'Flower Gift', 'Harvest', 'Leaf Guard'}, 'rain': {'Swift Swim', 'Rain Dish', 'Hydration', 'Dry Skin'},
          'sand': {'Sand Rush', 'Sand Force', 'Sand Veil'}, 'snow': {'Slush Rush', 'Ice Body', 'Snow Cloak'}, 'electric': {'Surge Surfer', 'Quark Drive'},
          'perish': {'Shadow Tag', 'Arena Trap'}}
BEN_MV = {'sun': {'Solar Beam', 'Solar Blade', 'Weather Ball', 'Hydro Steam', 'Growth'}, 'rain': {'Thunder', 'Hurricane', 'Weather Ball', 'Electro Shot'},
          'sand': {'Weather Ball', 'Shore Up'}, 'snow': {'Blizzard', 'Aurora Veil', 'Weather Ball'}, 'grassy': {'Grassy Glide'},
          'psychic': {'Expanding Force'}, 'electric': {'Rising Voltage'}, 'perish': {'Mean Look', 'Block', 'Spirit Shackle', 'Anchor Shot', 'Jaw Lock'}}
BOOST = {'sun': 'Fire', 'rain': 'Water', 'grassy': 'Grass', 'psychic': 'Psychic', 'electric': 'Electric'}
GUARD = {'sun': 'Water', 'rain': 'Fire', 'misty': 'Dragon'}
STAT_TYPE = {'sand': 'Rock', 'snow': 'Ice'}
ATE = {'Aerilate': 'Flying', 'Pixilate': 'Fairy', 'Refrigerate': 'Ice', 'Galvanize': 'Electric'}
IMMUNE = {'Levitate': 'Ground', 'Earth Eater': 'Ground', 'Flash Fire': 'Fire', 'Well-Baked Body': 'Fire', 'Water Absorb': 'Water', 'Storm Drain': 'Water',
          'Dry Skin': 'Water', 'Volt Absorb': 'Electric', 'Lightning Rod': 'Electric', 'Motor Drive': 'Electric', 'Sap Sipper': 'Grass'}
ROLES = {'fakeout': {'Fake Out'}, 'redirect': {'Follow Me', 'Rage Powder'}}
ATYPES = [t for t in L.DEX['types'] if t != 'Stellar']
SLOW, FAST = 60, 110
GUARD_ON = True

def mult(types, atk, ab):
    if IMMUNE.get(ab) == atk: return 0
    m = 1.0
    for t in types: m *= {0: 1, 1: 2, 2: 0.5, 3: 0}[L.DEX['types'][t][atk]]
    return m

def tags(s):
    fm = L.battle_forme(s['species'], s.get('item')); d = L.DEX['species'].get(L.idf(fm)) or L.DEX['species'][L.idf(s['species'])]
    ab = next(iter(d['abilities'].values())) if d.get('isMega') else s.get('ability'); mv = set(s.get('moves') or [])
    atk = []
    for m in mv:
        x = L.DEX['moves'].get(L.idf(m))
        if x and x['category'] != 'Status': atk.append((ATE[ab] if ab in ATE and x['type'] == 'Normal' else x['type'], x['category']))
    types, spe = d['types'], d['stats']['spe']; grounded = 'Flying' not in types and ab != 'Levitate'
    weak = {a for a in ATYPES if mult(types, a, ab) >= 2}
    setter = ({SETTER_AB[ab]} if ab in SETTER_AB else set()) | {SETTER_MV[m] for m in mv if m in SETTER_MV}
    ben = set()
    for k in FIELD + ('perish',):
        if (ab in BEN_AB.get(k, ()) or mv & BEN_MV.get(k, set()) or any(t == BOOST.get(k) for t, _ in atk)
                or (GUARD_ON and GUARD.get(k) in weak) or STAT_TYPE.get(k) in types) and (k not in TERRAIN or grounded): ben.add(k)
    if len(atk) >= 2 and spe <= SLOW: ben.add('tr')
    if len(atk) >= 2 and SLOW < spe < FAST: ben.add('tailwind')
    phys = sum(c == 'Physical' for _, c in atk); spec = len(atk) - phys
    roles = {r for r, ms in ROLES.items() if mv & ms} | ({'intimidate'} if ab == 'Intimidate' else set())
    return dict(forme=fm, base=d.get('baseSpecies') or d.get('base') or d['name'], item=s.get('item'), mega=bool(d.get('isMega')),
                setter=setter, ben=ben, roles=roles, phys=phys > spec, spec=spec > phys, weak=weak)

def profile(ts):
    kinds = set().union(*(t['setter'] for t in ts))
    return dict(plans={k: dict(s=sum(k in t['setter'] for t in ts), b=sum(k in t['ben'] and k not in t['setter'] for t in ts)) for k in kinds},
                mega=sum(t['mega'] for t in ts), roles={r: sum(r in t['roles'] for t in ts) for r in ('fakeout', 'redirect', 'intimidate')},
                phys=sum(t['phys'] for t in ts), spec=sum(t['spec'] for t in ts))

def stack(ts): return max(sum(a in t['weak'] for t in ts) for a in ATYPES)

class Gen:
    def __init__(self, uni):
        P = json.load(open(os.path.join(HERE, 'mb_pool.json')))['entries']; W = window_games()
        last = max(e['day'] for e in P); first = (datetime.date.fromisoformat(last) - datetime.timedelta(days=13)).isoformat()
        E = [e for e in P if e['day'] >= first and e['id'] not in W]
        per = collections.Counter(e['player'] for e in E); npl = len(per)
        blind = json.load(open(os.path.join(HERE, 'mb_blind_v2.json')))['sets']
        self.new = {L.battle_forme(v['set']['species'], v['set'].get('item')) for v in blind.values()}
        use, sets = collections.Counter(), collections.defaultdict(collections.Counter); self.tpl = []
        for e in E:
            w = 1 / per[e['player']] / npl; six = [L.normalize(s) for s in e['six']]
            for s in six:
                f = L.battle_forme(s['species'], s.get('item'))
                if f in self.new: continue
                use[f] += w; sets[f][json.dumps(dict({k: s.get(k) for k in ('species', 'item', 'ability', 'nature')}, moves=sorted(s.get('moves') or [])), sort_keys=True)] += w
            ts = [tags(s) for s in six]
            self.tpl.append(dict(w=w, prof=profile(ts), sets=six, ts=ts, stack=stack(ts)))
        order = sorted(range(len(self.tpl)), key=lambda i: self.tpl[i]['stack']); acc, tot = 0, sum(t['w'] for t in self.tpl)
        for i in order:
            acc += self.tpl[i]['w']
            if acc >= 0.95 * tot: self.cap = self.tpl[i]['stack']; break
        if uni == 'A': U = {x['forme'] for x in json.load(open(os.path.join(HERE, 'mb_swap_pool_v2.json')))}
        else: U = {f for f, v in use.items() if v >= 0.0025} | self.new
        self.U = U; tu = sum(use[f] for f in U)
        prior = {f: 0.5 * use[f] / tu + 0.5 / len(U) for f in U}
        self.cands = []
        for f in sorted(U - self.new):
            c = sets[f]; n = sum(c.values()); top = [(k, v) for k, v in c.most_common(4) if v >= 0.1 * n] or c.most_common(1)
            for k, v in top: self.cands.append(dict(set=json.loads(k), w=prior[f] * v / sum(x for _, x in top)))
        bl = collections.defaultdict(list)
        for v in blind.values(): bl[L.battle_forme(v['set']['species'], v['set'].get('item'))].append(v['set'])
        for f in sorted(self.new & U):
            for s in bl[f]: self.cands.append(dict(set={k: s.get(k) for k in ('species', 'item', 'ability', 'nature', 'moves')}, w=prior[f] / len(bl[f])))
        for c in self.cands: c['t'] = tags(c['set'])
        self.prior, self.use, self.tc = prior, use, {}
        self.avail = {k for k in FAMILY if any(k in c['t']['setter'] for c in self.cands)}
        self.anchors = sorted(self.new & U)

    def wpick(self, rng, items, ws):
        tot = sum(ws)
        if tot <= 0: return None
        cum, a = [], 0
        for w in ws: a += w; cum.append(a)
        return items[min(bisect.bisect(cum, rng.random() * tot), len(items) - 1)]

    def tpl_pick(self, rng, key=None, ok=None):
        if key not in self.tc:
            T = [t for t in self.tpl if ok is None or ok(t)]; a, cum = 0, []
            for t in T: a += t['w']; cum.append(a)
            self.tc[key] = (T, cum)
        T, cum = self.tc[key]
        return T[min(bisect.bisect(cum, rng.random() * cum[-1]), len(T) - 1)] if T else None

    def fits(self, team, c, megas=2):
        """species and item clauses, in the universe, at most `megas` Mega Stones"""
        t = c['t']
        return (t['forme'] in self.U and all(t['base'] != x['t']['base'] and not (t['item'] and t['item'] == x['t']['item']) for x in team)
                and not (t['mega'] and sum(x['t']['mega'] for x in team) >= megas))

    def needs(self, team, plans, prof):
        out = []
        for k, p in plans.items():
            out += [('setter', k)] * max(0, p['s'] - sum(k in x['t']['setter'] for x in team))
            out += [('ben', k)] * max(0, p['b'] - sum(k in x['t']['ben'] and k not in x['t']['setter'] for x in team))
        for r, n in prof['roles'].items(): out += [('role', r)] * max(0, n - sum(r in x['t']['roles'] for x in team))
        out += [('mega', None)] * max(0, prof['mega'] - sum(x['t']['mega'] for x in team))
        return out

    @staticmethod
    def meets(t, nd):
        kind, k = nd
        return (k in t['setter'] if kind == 'setter' else k in t['ben'] and k not in t['setter'] if kind == 'ben'
                else k in t['roles'] if kind == 'role' else t['mega'])

    def build(self, rng, prof, first, plans):
        team = list(first)
        while len(team) < 6:
            nds = self.needs(team, plans, prof)
            C = [c for c in self.cands if self.fits(team, c, prof['mega'])]
            if nds:
                Cn = [c for c in C if self.meets(c['t'], nds[0])]
                if Cn: C = Cn
                ws = [c['w'] * (1 + sum(self.meets(c['t'], n) for n in nds[1:])) for c in C]
            else: ws = [c['w'] * (1 + len(c['t']['ben'] & set(plans)) + len(c['t']['setter'] & set(plans))) for c in C]
            c = self.wpick(rng, C, ws)
            if c is None: return None
            team.append(c)
        ts = [x['t'] for x in team]; pr = profile(ts)
        if pr['mega'] != prof['mega'] or abs(pr['phys'] - prof['phys']) > 1 or abs(pr['spec'] - prof['spec']) > 1 or stack(ts) > self.cap: return None
        for k, p in plans.items():
            if sum(k in t['setter'] for t in ts) < max(1, p['s']) or sum(k in t['ben'] and k not in t['setter'] for t in ts) < p['b'] - 1: return None
        return team

    def plans_of(self, rng, prof, fixed=None):
        out = {}
        for k0, p in prof['plans'].items():
            if fixed and k0 == fixed[0]: k = fixed[1]
            elif rng.random() < 0.5 and k0 in self.avail: k = k0
            else:
                fam = [x for x in FAMILY[k0] if x in self.avail]
                if not fam: continue
                k = rng.choice(fam)
            q = out.setdefault(k, dict(s=0, b=0)); q['s'] = max(q['s'], p['s']); q['b'] = max(q['b'], p['b'])
        return out

    def one(self, rng, anchor=None, keep=False):
        for _ in range(TRIES):
            first, fixed = [], None
            if anchor:
                A = [c for c in self.cands if c['t']['forme'] == anchor]; a = self.wpick(rng, A, [c['w'] for c in A]); t = a['t']
                opts = [(k, 'setter') for k in t['setter'] if k in self.avail] + [(k, 'ben') for k in t['ben'] if k in self.avail and k not in t['setter']]
                if opts:
                    k, rel = rng.choice(opts)
                    tp = self.tpl_pick(rng, ('fam', FAMILY[k]), lambda x: any(j in FAMILY[k] for j in x['prof']['plans']))
                    if tp: fixed = (rng.choice([j for j in tp['prof']['plans'] if j in FAMILY[k]]), k)
                    else: tp = self.tpl_pick(rng)
                else: tp = self.tpl_pick(rng, ('roles', tuple(sorted(t['roles']))), lambda x: any(x['prof']['roles'][r] for r in t['roles'])) or self.tpl_pick(rng)
                first.append(a)
            else: tp = self.tpl_pick(rng)
            prof = tp['prof']
            if anchor and a['t']['mega'] and prof['mega'] == 0: prof = dict(prof, mega=1)
            plans = self.plans_of(rng, prof, fixed)
            if fixed and fixed[1] not in plans: plans[fixed[1]] = dict(s=1, b=0)
            if keep:
                mine = [dict(set=s, w=0, t=t) for s, t in zip(tp['sets'], tp['ts'])]; rng.shuffle(mine)
                for c in mine[:rng.randint(0, 3)]:
                    if self.fits(first, c, prof['mega']): first.append(c)
            team = self.build(rng, prof, first, plans)
            if team: return team, tp
        return None, None

    def run(self, variant, n=N_MAX):
        rng = random.Random(SEED); out, seen, i, stall = [], set(), 0, 0
        while len(out) < n and stall < 20 * n:
            anchor = self.anchors[(len(out) // 2) % len(self.anchors)] if len(out) % 2 else None
            if variant == 'random': team = self.random_six(rng); origin = 'random'
            else:
                team, tp = self.one(rng, anchor, keep=variant != 'roles'); origin = f'anchor {anchor}' if anchor else 'free'
            key = tuple(sorted(c['t']['forme'] for c in team)) if team else None
            if not key or key in seen: stall += 1; continue
            seen.add(key); out.append(dict(formes=list(key), sets=[c['set'] for c in team], origin=origin))
        return out

    def random_six(self, rng):
        for _ in range(TRIES):
            team = []
            while len(team) < 6:
                C = [c for c in self.cands if self.fits(team, c)]; c = self.wpick(rng, C, [c['w'] for c in C])
                if c is None: break
                team.append(c)
            if len(team) == 6: return team
        return None

    def mbtop(self, n=N_MAX):
        c = collections.Counter()
        for t in self.tpl: c[tuple(sorted(x['forme'] for x in t['ts']))] += t['w']
        return [dict(formes=list(k), sets=None, origin='M-B six', w=round(v, 6)) for k, v in c.most_common(n)]

def save(name, sixes, meta):
    os.makedirs(OUT, exist_ok=True)
    tab, ids = [], {}
    for x in sixes:
        if x['sets']:
            x['sets'] = [ids.setdefault(json.dumps(s, sort_keys=True), len(ids)) for s in x['sets']]
    tab = [json.loads(k) for k in ids]
    json.dump(dict(meta, sets=tab, sixes=sixes), open(os.path.join(OUT, f'{name}.json'), 'w'))

def main():
    global GUARD_ON
    for uni in ('A', 'B'):
        for guard in (True, False):
            GUARD_ON = guard; G = Gen(uni)
            meta = dict(universe=uni, formes=len(G.U), new_formes=len(G.anchors), weakness_cap=G.cap, guard=guard, seed=SEED, U=sorted(G.U))
            vs = ('roles', 'keep', 'random') if guard else ('keep',)
            for v in vs:
                t0 = datetime.datetime.now(); S = G.run(v); name = f"{v}{'' if guard else '_noguard'}_{uni}"
                save(name, S, dict(meta, variant=v))
                print(f"{name}: {len(S)} sixes, {len(G.U)} formes, weakness cap {G.cap}, {(datetime.datetime.now() - t0).seconds} s", flush=True)
            if guard and uni == 'B': save('mbtop', G.mbtop(), dict(variant='mbtop'))

if __name__ == '__main__': main()
