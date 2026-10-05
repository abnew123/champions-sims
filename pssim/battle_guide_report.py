"""Strategy-guide summaries from full battles with the per-turn state log (champ-battle-v4, BATTLE_TURNS=1), one block per archetype:
how the plan does, Trick Room timing, what each of my Pokemon clicks after turn one (Trick Room up / down), switching and Protect habits,
Mega timing, what decides games (conditional win rates), and the opposing Pokemon that beat the plan most. Opposing leads are weighted by
their replay share throughout.
usage: python3 battle_guide_report.py <results dir> [...]"""
import json, glob, sys, re, collections
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
base = lambda n: n.split('-Mega')[0].replace('Indeedee-F', 'Indeedee')
def acts(label):
    """'Mon: Move -> Target (Mega) | Mon2: switch to X' -> [(mon, kind, move, target, mega)]"""
    out = []
    for part in label.split(' | '):
        if ': ' not in part: continue
        mon, a = part.split(': ', 1); mega = a.endswith(' (Mega)'); a = a.replace(' (Mega)', '')
        if a.startswith('switch to '): out.append((base(mon), 'switch', 'switch', base(a[10:]), mega))
        else:
            mv, _, tgt = a.partition(' -> '); out.append((base(mon), 'move', mv, base(tgt) if tgt else '', mega))
    return out
G = collections.defaultdict(list)                      # arch -> [(weight, game rows)]
for d in sys.argv[1:]:
    for f in glob.glob(d + '/*.json'):
        r = json.load(open(f)); n = len(r['rows'])
        for g in r['rows']:
            if g.get('v') is None or not g.get('states'): continue
            G[r['arch']].append((r['share'] / n, g, r))
def pct(x): return f"{100 * x:.0f}%"
def wmean(pairs):
    W = sum(w for w, _ in pairs); return sum(w * v for w, v in pairs) / W if W else float('nan')
for arch in SH:
    L = G.get(arch, [])
    if not L: continue
    r0 = L[0][2]; W = sum(w for w, _, _ in L)
    win = sum(w * g['v'] for w, g, _ in L) / W; turns = sum(w * g['turns'] for w, g, _ in L) / W
    print(f"\n=== {arch} ({SH[arch]}% of the ladder): {'+'.join(map(base, r0['lead']))} lead, {'+'.join(map(base, r0['back']))} behind; "
          f"{len(L)} games, win {pct(win)}, {turns:.1f} turns on average")
    # Trick Room: who sets it, when, re-sets
    tr_up = [wmean([(w, 1.0 if len(g['states']) > t and g['states'][t]['tr'] > 0 else 0.0) for w, g, _ in L]) for t in (1, 2, 3)]
    sets = collections.Counter(); resets = 0.0; theirs = 0.0
    for w, g, _ in L:
        n_mine = 0
        for s in g['states']:
            for mon, kind, mv, tgt, mega in acts(s['a']):
                if mv == 'Trick Room': n_mine += 1; sets[(mon, min(s['t'], 4))] += w
            for mon, kind, mv, tgt, mega in acts(s['b']):
                if mv == 'Trick Room': theirs += w
        resets += w * (n_mine >= 2)
    print(f"  Trick Room up at the start of turns 2/3/4: {' / '.join(pct(x) for x in tr_up)}; I click it again later in {pct(resets / W)} of games;"
          f" they click Trick Room {theirs / W:.2f} times per game")
    who = collections.defaultdict(float)
    for (mon, t), w in sets.items(): who[mon] += w
    if who: print('  my Trick Room clicks by setter: ' + ', '.join(f"{m} {v / W:.2f}/game" for m, v in sorted(who.items(), key=lambda x: -x[1])))
    # what my Pokemon click after turn one, by Trick Room state
    for phase, lo, hi in (('turns 2-3', 2, 3), ('turn 4+', 4, 99)):
        for trs in (True, False):
            use = collections.defaultdict(collections.Counter); tot = collections.Counter()
            for w, g, _ in L:
                for s in g['states']:
                    if not (lo <= s['t'] <= hi) or (s['tr'] > 0) != trs: continue
                    for mon, kind, mv, tgt, mega in acts(s['a']):
                        use[mon][mv if kind == 'move' else 'switch out'] += w; tot[mon] += w
            if not tot: continue
            parts = []
            for mon in sorted(tot, key=lambda m: -tot[m]):
                top = use[mon].most_common(3); parts.append(f"{mon}: " + ', '.join(f"{mv} {pct(v / tot[mon])}" for mv, v in top))
            print(f"  {phase}, Trick Room {'up' if trs else 'down'} ({sum(tot.values()) / W:.1f} actions/game): " + ' | '.join(parts))
    # Mega timing, Protect, switches
    mega_t = [s['t'] for w, g, _ in L for s in g['states'] for mon, kind, mv, tgt, mega in acts(s['a']) if mega]
    if mega_t: print(f"  Blastoise Mega Evolves in {pct(len(mega_t) / len(L))} of games, on turn " + ', '.join(f"{t}: {pct(c / len(mega_t))}" for t, c in sorted(collections.Counter(min(t, 5) for t in mega_t).items())))
    sw = collections.Counter(); sw_in = collections.Counter(); prot = collections.Counter(); acts_n = collections.Counter()
    for w, g, _ in L:
        for s in g['states']:
            for mon, kind, mv, tgt, mega in acts(s['a']):
                acts_n[mon] += w
                if kind == 'switch': sw[mon] += w; sw_in[tgt] += w
                if mv == 'Protect': prot[mon] += w
    if sw: print('  switching out (share of that Pokemon\'s turns): ' + ', '.join(f"{m} {pct(sw[m] / acts_n[m])}" for m in sorted(sw, key=lambda m: -sw[m] / acts_n[m])[:4])
                 + ' | most common switch-in: ' + ', '.join(f"{m} {v / W:.2f}/game" for m, v in sw_in.most_common(2)))
    if prot: print('  Protect: ' + ', '.join(f"{m} {pct(prot[m] / acts_n[m])} of its turns" for m in prot))
    # what decides games: conditional win rates
    def cond(name, f):
        a = [(w, g['v']) for w, g, _ in L if f(g)]; b = [(w, g['v']) for w, g, _ in L if not f(g)]
        if len(a) >= 15 and len(b) >= 15: print(f"  {name}: win {pct(wmean(a))} ({len(a)} games) vs {pct(wmean(b))} otherwise")
    cond('Trick Room up at the start of turn 2', lambda g: len(g['states']) > 1 and g['states'][1]['tr'] > 0)
    def first_faint(g):
        prev = {base(m) for m, hp in g['states'][0]['me'] + g['states'][0]['mb']}      # base names: Mega Evolution is not a faint
        for s in g['states'][1:]:
            now = {base(m) for m, hp in s['me'] + s['mb']}
            if prev - now: return sorted(prev - now)[0], s['t']
            prev = now
        return None, None
    ff = collections.Counter(); ffw = collections.defaultdict(list)
    for w, g, _ in L:
        m, t = first_faint(g)
        if m and t <= 3: ff[base(m)] += w; ffw[base(m)].append((w, g['v']))
    for m, v in ff.most_common(3):
        if len(ffw[m]) >= 15: print(f"  {m} down by turn 2: {pct(v / W)} of games, win {pct(wmean(ffw[m]))} then")
    # opposing Pokemon in their four vs my win rate
    opp = collections.defaultdict(list)
    for w, g, r in L:
        for m in set(map(base, r['theirs'])): opp[m].append((w, g['v']))
    worst = sorted(((wmean(v), m, sum(w for w, _ in v) / W) for m, v in opp.items() if sum(w for w, _ in v) / W >= 0.15), key=lambda x: x[0])
    print('  win rate when their four includes: ' + ', '.join(f"{m} {pct(v)} (in {pct(s)})" for v, m, s in worst[:4]) + ' ... best: '
          + ', '.join(f"{m} {pct(v)}" for v, m, s in worst[-2:]))
