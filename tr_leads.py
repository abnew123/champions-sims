# Leads section for the Trick Room Six sheet: data from pssim/tr_final.json, rules written here, injected at <!--LEADS-->.
import json, re, sys, html, itertools
SRC = sys.argv[1] if len(sys.argv) > 1 else 'pssim/tr_final.json'
D = json.load(open(SRC)); PL = D['plans']; LV = D['leads']
SRC2 = SRC.replace('.json', '_x2.json'); import os
LAM = float(os.environ.get('READER_W', '0.5'))          # weight on the reader number in the lead score
# Edit TEAM_NOTE when the six or the runs behind it change (it ends up in the method note under the leads).
TEAM_NOTE = os.environ.get('TEAM_NOTE', "Incineroar&rsquo;s five pairs were simulated with it in the team; the other ten reuse the runs from the Hatterene version, with Farigiraf in the back row where Hatterene was, its Speed used for the Trick Room credit, and turn-one switches into Hatterene removed. ")
_r = LAM / (1 - LAM) if LAM < 1 else None
SCORE_TEXT = ("Leads are ranked on the average of the two numbers. " if abs(LAM - 0.5) < 1e-9 else
              "Leads are ranked on the reader number alone. " if _r is None else
              f"Leads are ranked on a score that counts the reader number {({2: 'twice', 3: 'three times', 4: 'four times'}.get(round(_r)) or f'{_r:.1f} times')} as much as the ladder number, because ladder rates come from all of a Pok&eacute;mon&rsquo;s games, not from games against a lead like yours. ")
BL = lambda a, b: (1 - LAM) * a + LAM * b
D2 = json.load(open(SRC2)) if os.path.exists(SRC2) else None
SETTERS = {'Indeedee-F', 'Farigiraf', 'Hatterene'}
# BACK_FILE: 2v2 endgame summary (pssim/eg_analyze.py --json). The back pair shown is the one with the best 2v2 win share against
# the archetype's likely back pairs, mixing Trick Room up / down by how often the lead's plan sets it on turn one.
EG = json.load(open(os.environ['BACK_FILE']))['tr'] if os.environ.get('BACK_FILE') else None
TRM = json.load(open(os.environ['TRMULT_FILE'])) if os.environ.get('TRMULT_FILE') else None
EGALL = json.load(open(os.environ['BACK_FILE'])) if os.environ.get('BACK_FILE') else None
# TRUP_FILE: P(Trick Room up after turn one, whoever set it) per plan (pssim/tr_up.py); mixes the back row's 2v2 values. Else my click rate.
TRUP = json.load(open(os.environ['TRUP_FILE'])) if os.environ.get('TRUP_FILE') else {}
SIX6 = ['Incineroar', 'Indeedee-F', 'Farigiraf', 'Torkoal', 'Kingambit', 'Blastoise']
def best_back(arch, lead, trr, default):
    if not EG or arch not in EG: return list(default), 0.0
    P = {frozenset(k.split('+')): v for k, v in EG[arch]['pairs'].items()}
    sc = {b: trr * P[frozenset(b)][0] + (1 - trr) * P[frozenset(b)][1] for b in itertools.combinations([x for x in SIX6 if x not in lead], 2) if frozenset(b) in P}
    b = max(sc, key=sc.get); d0 = next((v for k, v in sc.items() if set(k) == set(default)), sc[b])
    return list(b), sc[b] - d0
TABS = [('tw', 'Tailwind', 'Tailwind goodstuffs', 'Raichu'), ('indeedee', 'Indeedee TR', 'Indeedee TR / Psychic Terrain', 'Farigiraf'),
        ('sun', 'Sun', 'Sun', 'Farigiraf'), ('rain', 'Rain', 'Rain', 'Farigiraf'), ('balance', 'Balance', 'Balance, no speed control', 'Raichu'),
        ('sand', 'Sand', 'Sand', 'Salamence'), ('snow', 'Snow', 'Snow', 'Froslass'), ('tr', 'Trick Room', 'Trick Room without Indeedee', 'Farigiraf'),
        ('rainsun', 'Rain + Sun', 'Rain + sun', 'Farigiraf'), ('perish', 'Perish', 'Perish trap', 'Archaludon')]
SHOW_PLAN = os.environ.get('SHOW_PLAN', '1') != '0'          # 0: no plan paragraph, mechanics notes only
# LEAD_OVERRIDE: {archetype: {"lead": "A+B" (tr_final name), "back": [c, d], "note": "..."}}: the main lead and back row picked from full-battle
# sims (pssim/battle_leads_*.py, 2026-10-03). The tab then shows that one card, marked "Full-battle pick", with its turn-one lines from tr_final.
OVR = json.load(open(os.environ['LEAD_OVERRIDE'])) if os.environ.get('LEAD_OVERRIDE') else {}
RULES = json.load(open('tr_rules.json')) if __import__('os').path.exists('tr_rules.json') else {}
MYN = {'Indeedee-F': 'Indeedee'}
OPN = {'Indeedee-F': 'Indeedee F', 'Indeedee': 'Indeedee M', 'Arcanine-Hisui': 'Arcanine-H', 'Floette-Eternal': 'Floette'}
def act(s):
    mon, a = s.split(': ', 1); mv, _, tgt = a.partition(' -> ')
    if mv == 'switch': return MYN.get(mon, mon), 'switch &rarr; ' + MYN.get(tgt, tgt)
    if mon == 'Kingambit' and mv == 'Kowtow Cleave' and tgt == 'Sneasler': mv = 'Iron Head'
    mv = {'Kowtow Cleave': 'Kowtow'}.get(mv, mv)
    return MYN.get(mon, mon), mv + (' ' + OPN.get(tgt, tgt) if tgt else '')
def pair_name(p): return ' + '.join(OPN.get(x, x) for x in p.split(' + '))
def lead_name(l): return ' + '.join(MYN.get(x, x) for x in l.split('+'))
def pct(x): return int(round(100 * x))
def vals(arch, tag, LV=LV): return {x[0]: x for x in LV[arch][tag]['vals']}
def pick(arch, tag, lead, when=None, D=D, x2=False, back_force=None):
    PL, LV = D['plans'], D['leads']
    ws = LV[arch][tag]['weights']; rows = []
    for key, p in PL.items():
        a, l, pair = key.split('||')
        if a != arch or l != lead: continue
        sh = 100 * p['share'] if ws is None else ws.get(pair, 0)
        if sh <= 0: continue
        lines = []
        for pc, s in p['mix']:
            (m1, a1), (m2, a2) = [act(x) for x in s.split(' | ')]
            lines.append([pc, a1, a2])
        tr = sum(pc for pc, s in p['mix'] if ': Trick Room' in s) / 100
        rows.append((sh, pair, p['pop1'] if x2 else p['pop'], p['worst1'] if x2 else p['worst'], lines, p['back'], tr, TRUP.get(key, tr)))
    rows.sort(key=lambda r: -r[0]); W = sum(r[0] for r in rows)
    v0 = sum(r[0] * r[2] for r in rows) / W; v1 = sum(r[0] * r[3] for r in rows) / W; trr = sum(r[0] * r[6] for r in rows) / W
    trup = sum(r[0] * r[7] for r in rows) / W
    ref = vals(arch, tag, LV)[lead]
    if not x2: assert abs(v0 - ref[1]) < 1e-9 and abs(v1 - ref[2]) < 1e-9, (arch, tag, lead)
    top = LV[arch][tag]['vals'][0]; g = 100 * (top[3] - ref[3])
    backs = {tuple(r[5]) for r in rows}; assert len(backs) == 1, backs
    k = f'{arch}|{tag}|{lead}' + ('|x2' if x2 else '')
    rule = RULES.get(k, {}).get('rule') or ('<i>Draft:</i> ' + '; '.join(f"vs {pair_name(r[1])}: {r[4][0][1]} / {r[4][0][2]}" for r in rows[:3]))
    back, bgain = (list(back_force), 0.0) if back_force else best_back(arch, lead.split('+'), trup, rows[0][5])
    BLOG.append((arch, tag, lead, rows[0][5], back, round(100 * bgain)))
    pk = {'lead': [MYN.get(x, x) for x in lead.split('+')], 'back': ', '.join(MYN.get(x, x) for x in back), 'v': [pct(v0), pct(v1)],
          'top': None if g < 0.05 else [lead_name(top[0]), round(g, 1)], 'tr': pct(trr), 'rule': rule,
          'vs': [[pair_name(r[1]), round(r[0], 1), [pct(r[2]), pct(r[3])], r[4]] for r in rows]}
    if when: pk = {'when': when, **pk}
    if x2:
        t1 = LV1[arch]['all']['vals'][0]
        pk['x2'] = round(100 * (t1[3] - BL(v0, v1)), 1)          # this plan, scored with the fitted weights, vs the fitted top lead
        pk['top'] = None
    if RULES.get(k, {}).get('note'): pk['note'] = RULES[k]['note']
    if not SHOW_PLAN:                                        # the move lines already give the plan; keep only the mechanics behind it
        sents = re.split(r'(?<=[.!?])\s+', re.sub(r'</?b>', '', re.sub(r'<i>Draft:</i>.*', '', pk['rule'])))
        mech = [x for x in sents if re.search(r'Armor Tail|blocks?|terrain|replaces their|cancel|flies|immune|Eject|fails if|their own setter', x)]
        if RULES.get(k, {}).get('mech'): mech = [RULES[k]['mech']]
        note = ' '.join(dict.fromkeys(mech + ([pk['note']] if pk.get('note') else [])))
        pk['rule'] = ''
        if note: pk['note'] = note
        else: pk.pop('note', None)
    return pk
LV1 = LV
BLOG = []
# Rule 1: Farigiraf + Blastoise is the main lead wherever it is within FB_WITHIN of the strongest lead (per tell when the tab splits);
# the strongest lead it displaced is shown after it. Rule 2: the "If Trick Room counts double" lead is shown only against archetypes
# whose leads click Trick Room on turn one less than X2_MAX of the time (their own Trick Room makes yours worth less).
FB, FB_WITHIN, X2_MAX = 'Farigiraf+Blastoise', 0.03, 0.05
def their_tr_rate():
    A = {**json.load(open('pssim/opp_model_a.json')), **json.load(open('pssim/opp_model_b.json'))}; out = {}
    for arch, d in A.items():
        num = den = 0.0
        for pr in d['pairs']:
            none = 1.0
            for mon, st in pr['t1'].items():
                m = re.search(r'Trick Room:([0-9.]+)', st)
                if m: none *= 1 - float(m.group(1))
            num += pr['share'] * (1 - none); den += pr['share']
        out[arch] = num / den
    return out
TRT1 = their_tr_rate()
out = []; log = []
for k, tab, arch, tell in TABS:
    if arch not in LV: continue
    T = LV[arch]; P = []
    if arch in OVR:                                         # full-battle pick: one card
        o = OVR[arch]; pk = pick(arch, 'all', o['lead'], back_force=o['back']); pk['top'] = None; pk['fb'] = 1
        if o.get('fbw') is not None: pk['fbw'] = o['fbw']          # whole-game win % in the full-battle sims
        pk['note'] = ' '.join(x for x in (pk.get('note'), o.get('note')) if x)
        out.append({'k': k, 'tab': tab, 'picks': [pk]}); log.append((tab, '', ' + '.join(pk['lead']), pk['v'], None, pk['tr'])); continue
    yes, no = f'{tell} yes', f'{tell} no'
    def rule_main(tag):                                     # (main lead, strongest lead it displaced or None)
        v = vals(arch, tag); top = T[tag]['vals'][0][0]
        return (FB, top) if top != FB and FB in v and v[top][3] - v[FB][3] <= FB_WITHIN + 1e-9 else (top, None)
    split = False
    if yes in T and no in T:                                # split on the tell only when the two main leads differ and each
        (my, _), (mn, _) = rule_main(yes), rule_main(no); vy, vn = vals(arch, yes), vals(arch, no)   # beats the other by 2+ points on its side
        split = my != mn and mn in vy and my in vn and vy[my][3] - vy[mn][3] >= 0.02 and vn[mn][3] - vn[my][3] >= 0.02
    conds = [(yes, f'{tell} in their six'), (no, f'No {tell} in their six')] if split else [('all', None)]
    main, shown_top = [], []
    for tag, when in conds:
        m, d = rule_main(tag); main.append((tag, m, when))
        if d: shown_top.append((tag, d, when))
    for tag, l, when in main: P.append(pick(arch, tag, l, when))
    for tag, l, when in shown_top: P.append(pick(arch, tag, l, when))
    x2lead = D2['leads'][arch]['all']['vals'][0][0] if D2 is not None and arch in D2['leads'] and TRT1.get(arch, 0) < X2_MAX else None
    shown = lambda: {'+'.join(p['lead']).replace('Indeedee', 'Indeedee-F') for p in P}
    if not split and not shown_top:                         # the main lead is the strongest: offer another setter within 5 points
        L = T['all']['vals']; top = L[0]; st = set(top[0].split('+')) & SETTERS
        alt = next((x for x in L[1:] if set(x[0].split('+')) & SETTERS and set(x[0].split('+')) & SETTERS != st and top[3] - x[3] <= 0.05), None)
        if alt and (x2lead is None or x2lead in shown()): P.append(pick(arch, 'all', alt[0]))
    if x2lead and x2lead not in shown(): P.append(pick(arch, 'all', x2lead, 'If Trick Room counts double', D=D2, x2=True))
    print(f"{tab:12s} their turn-one Trick Room {100*TRT1.get(arch, 0):4.1f}%  x2 {'shown' if x2lead and any(p.get('x2') is not None for p in P) else 'none'}")
    out.append({'k': k, 'tab': tab, 'picks': P}); log += [(tab, p.get('when', ''), ' + '.join(p['lead']), p['v'], p['top'], p['tr']) for p in P]
OTHER = json.load(open(os.environ['OTHER_FILE'])) if os.environ.get('OTHER_FILE') else None
if OTHER:                                                   # unusual team or unsure: best lead and back against a random team, general plan only
    nmf = lambda x: x.replace('Indeedee-F', 'Indeedee').replace('Floette-Eternal', 'Floette')
    P = []
    for i, p in enumerate(OTHER['picks']):
        pk = {'lead': [nmf(x) for x in p['lead'].split('+')], 'back': ', '.join(nmf(x) for x in p['back']), 'v': [pct(p['v'][0]), pct(p['v'][1])],
              'top': [lead_name(OTHER['top']), OTHER['gap']] if i == 0 and p['lead'] != OTHER['top'] else None, 'tr': pct(p['tr']), 'rule': '', 'vs': [],
              'general': [[nmf(m), [[pc, mv, [nmf(t) for t in ts]] for pc, mv, ts in L]] for m, L in p['general'].items()]}
        if 'Farigiraf' in p['lead']: pk['note'] = 'Farigiraf&rsquo;s Armor Tail keeps their Fake Out off both of you. Indeedee&rsquo;s Psychic Terrain blocks your Fake Out on grounded targets.'
        elif 'Incineroar' in p['lead'] or 'Blastoise' in p['lead']: pk['note'] = 'Indeedee&rsquo;s Psychic Terrain and Farigiraf&rsquo;s Armor Tail block your Fake Out.'
        P.append(pk)
    out.append({'k': 'other', 'tab': 'Other', 'picks': P})
def js(o):
    if isinstance(o, dict): return '{' + ','.join(f'{kk}:{js(vv)}' for kk, vv in o.items()) + '}'
    if isinstance(o, list): return '[' + ','.join(js(x) for x in o) + ']'
    if isinstance(o, str): return json.dumps(o, ensure_ascii=False)
    if o is None: return 'null'
    return repr(o)
L = 'const L=[\n' + ',\n'.join(js(t) for t in out) + '\n];'
G = [('Gengar', 'perish', 'Perish'), ('Charizard + Pelipper or Politoed', 'rainsun', 'Rain + Sun'), ('Charizard or Torkoal', 'sun', 'Sun'),
     ('Pelipper or Politoed', 'rain', 'Rain'), ('Tyranitar', 'sand', 'Sand'), ('Froslass, Alolan Ninetales or Vanilluxe', 'snow', 'Snow'),
     ('Indeedee', 'indeedee', 'Indeedee TR'), ('Farigiraf or Sinistcha', 'tr', 'Trick Room'), ('Salamence, Whimsicott, Talonflame or Staraptor', 'tw', 'Tailwind'),
     ('none of these', 'balance', 'Balance'), ('an unusual team, or you&rsquo;re unsure', 'other', 'Other')]
guide = ('<p class="lguide" id="lguide"><b>Which tab:</b> take the first match in their six. '
         + ' &middot; '.join(f'{w}&nbsp;&rarr;&nbsp;<button type="button" class="lgk" data-k="{k}">{t}</button>' for w, k, t in G) + '</p>')
EXC, FBL = [], []                                          # where Farigiraf + Blastoise is / isn't the first card
for t in out:
    firsts = {}
    for p in t['picks']:
        if p.get('x2') is not None: continue
        firsts.setdefault(p.get('when'), p)
    for w, p in firsts.items():
        d = t['tab'] + (' teams' if t['tab'] == 'Trick Room' else '')
        if w and w.endswith(' in their six'):
            d += (' without a ' + w[3:].split(' in their six')[0]) if w.startswith('No ') else (' with a ' + w.split(' in their six')[0])
        (FBL if '+'.join(p['lead']) == 'Farigiraf+Blastoise' else EXC).append(d)
def andlist(xs): return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' and ' + xs[-1]
FBTEXT = 'which is every tab' if not EXC else (f'which is every tab except {andlist(EXC)}' if len(EXC) <= len(FBL) else f'which is {andlist(FBL)}')
BACK_TEXT = ("The back row shown is the pair that did best in a 2v2 endgame sim: the two you bring in the back against the pairs the archetype actually has on the field at turn 3 in public replays (leads that stayed in or pivoted, and back Pok&eacute;mon), both fresh, every turn played at each side&rsquo;s best mix in Showdown&rsquo;s engine, with Trick Room up (2&ndash;4 turns) as often as it is up after the lead&rsquo;s turn one, whoever set it. The turn-one numbers were simulated with a default back row, which only affects turn-one switches and the Trick Room credit. " if EG else
             "The back row is a default (a second setter and an attacker), not something the sim chose. ")
TRM_TEXT = (" and by how much Trick Room decided those 2v2 endgames against that archetype (its overall size still comes from the replay fit)" if TRM else "")
def _trtext():
    if not EGALL: return ''
    m = {a: 100 * v['mean'] for a, v in EGALL['tr'].items()}
    nm = {'Tailwind goodstuffs': 'Tailwind', 'Indeedee TR / Psychic Terrain': 'Indeedee TR', 'Balance, no speed control': 'Balance', 'Trick Room without Indeedee': 'Trick Room teams', 'Rain + sun': 'Rain + Sun', 'Perish trap': 'Perish'}
    parts = '; '.join(f"{nm.get(a, a)} {v:+.0f}" for a, v in sorted(m.items(), key=lambda kv: -kv[1]))
    return ('<p class="snote">How much Trick Room is worth depends on the archetype. In the 2v2 endgame sim (your back two against the pairs their archetype has on the field at turn 3, '
            f'Trick Room up for 2&ndash;4 turns or not at all), it changes your win share by: {parts} points. The lead scores use those ratios, so Trick Room counts more against fast teams and less against slow ones.</p>')
X2_PARA = ('''<p class="snote">A lead marked <b>If Trick Room counts double</b> is the best one when the win model&rsquo;s bonus for having Trick Room up after turn one (about 15 points of win chance from an even spot) is doubled. That bonus was fit on every team that sets Trick Room, and a team built entirely around it probably gets more from it. Its numbers are still scored with the fitted model, so they compare directly with the leads above it. It only appears against archetypes whose leads almost never set Trick Room themselves (under 5% of the time on turn one), since their own Trick Room makes yours worth less, not more.</p>''' if D2 is not None else _trtext())
SECTION = f'''<section id="leads">
  <div class="shead">
    <h2>Leads</h2>
    <p class="snote">Pick the lead at team preview, then the turn-one line for what they send out. Percentages are how often to click each line; use any randomizer. The two numbers are your win chance after turn one against how the Showdown ladder clicks, then against a player who reads your mix; red means the lead loses turn one. {SCORE_TEXT}&ldquo;Sets Trick Room&rdquo; is how often the plan clicks it on turn one.</p>
    <p class="snote">The first card is the main lead. That is Farigiraf + Blastoise wherever it comes within 3 points of the strongest lead, {FBTEXT}; elsewhere it is the strongest lead. Where Farigiraf + Blastoise displaced a stronger lead, that lead follows it, marked &ldquo;Top lead&rdquo;.</p>
    {X2_PARA}
  </div>
  {guide}
  <div class="lsegbar" role="tablist" aria-label="Their archetype" id="lseg"></div>
  <div id="lpanel"></div>
  <p class="snote" style="margin-top:4px">All 15 lead pairs were screened against each archetype&rsquo;s six most common opposing leads in 5,000 Showdown M-C Bo3 replays; the leads near the top were re-run with 12 RNG samples per cell in Showdown&rsquo;s engine with Champions mechanics and scored with a win model fit on 7,781 games. {TEAM_NOTE}Two changes for a Trick Room team: Trick Room up after turn one counts for whichever side brought the slower four, scaled by how much slower{TRM_TEXT}, not for whoever clicked it, and a Tailwind set in the same turn as Trick Room scores nothing, since it runs out inside Trick Room. Your Indeedee holds Psychic Seed; your Kingambit was simulated as Adamant, and Brave only changes turn one when both Kingambit attack each other. Their Indeedee F&rsquo;s item is mixed at replay rates: Rocky Helmet 48%, Colbur Berry 32%, Psychic Seed 20%. Iron Head replaces Kowtow Cleave into Sneasler, because Fighting resists Dark. {BACK_TEXT}Their other leads are not simulated.</p>
</section>'''
CSS = '''
/* leads */
.lsegbar{display:grid;grid-template-columns:repeat(11,minmax(0,1fr));gap:1px;margin-bottom:14px;border:1px solid var(--rule);border-radius:4px;overflow:hidden;background:var(--rule-2)}
.lseg{min-width:0;font-family:var(--disp);font-size:11.5px;font-weight:600;letter-spacing:.02em;line-height:1.25;padding:9px 4px;border:0;background:var(--panel);color:var(--ink3);cursor:pointer}
@media(max-width:760px){.lsegbar{grid-template-columns:repeat(6,minmax(0,1fr))}.lseg{font-size:11px;padding:8px 3px}}
.lseg:hover{background:var(--panel-2);color:var(--ink2)}
.lseg.on{background:var(--accent);color:var(--panel)}
.lseg:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.lguide{margin:0 0 12px;font-size:12.5px;line-height:1.7;color:var(--ink2);max-width:74ch}
.lguide b{color:var(--ink);font-weight:600}
.lgk{font:inherit;font-weight:600;color:var(--accent);background:none;border:0;padding:0;cursor:pointer;text-decoration:underline;text-underline-offset:2px}
.lgk:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.lpick{background:var(--panel);border:1px solid var(--rule);border-radius:4px;overflow:hidden;margin-bottom:14px}
.lphead{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px;padding:13px 16px;border-bottom:1px solid var(--rule-2);background:var(--panel-2)}
.lpwhen{flex-basis:100%;font-family:var(--disp);font-size:10.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--ink3)}
.lplead{font-family:var(--disp);font-size:19px;font-weight:700;letter-spacing:-.01em;color:var(--ink)}
.lpback{font-size:13px;color:var(--ink2)}
.lpv{margin-left:auto;font-family:var(--mono);font-size:12px;color:var(--ink2);white-space:nowrap}
.lpv b{color:var(--ink);font-weight:700}
.lptop{flex-basis:100%;display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--ink3)}
.lptop .is-top{color:var(--accent);font-weight:600}
.lptr{font-family:var(--mono);font-size:11.5px;color:var(--ink2)}
.lptr b{color:var(--accent);font-weight:700}
.lrule{padding:10px 16px;font-size:13.5px;line-height:1.55;color:var(--ink2);border-bottom:1px solid var(--rule-2)}
.lrule b{color:var(--ink);font-weight:600}
.lvs{padding:10px 16px 9px;border-bottom:1px solid var(--rule-2)}
.lvs:last-child{border-bottom:0}
.lvshead{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px;margin-bottom:5px}
.lvsname{font-family:var(--disp);font-weight:600;font-size:14px;color:var(--ink)}
.lvsshare{font-family:var(--mono);font-size:11px;color:var(--ink3)}
.lvsv{margin-left:auto;font-family:var(--mono);font-size:11.5px;color:var(--ink2);white-space:nowrap;font-variant-numeric:tabular-nums}
.lvsv.low{color:var(--off)}
.lline{display:grid;grid-template-columns:40px minmax(0,1fr) minmax(0,1fr);gap:1px 14px;align-items:baseline;padding:3px 0;font-size:13.5px;color:var(--ink)}
.lpct{font-family:var(--mono);font-size:11.5px;font-weight:700;color:var(--accent);font-variant-numeric:tabular-nums}
.lmon{font-family:var(--disp);font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--ink3);margin-right:5px}
.lgen{display:grid;grid-template-columns:40px minmax(0,1fr);gap:1px 14px;align-items:baseline;padding:3px 0;font-size:13.5px;color:var(--ink)}
.lgt{color:var(--ink3);font-size:12.5px}
.lnote{padding:9px 16px;font-size:12.5px;line-height:1.55;color:var(--ink2);background:var(--panel-2);border-top:1px solid var(--rule-2)}
@media(max-width:560px){.lline{grid-template-columns:36px minmax(0,1fr)}.lline .la2{grid-column:2}.lline+.lline{margin-top:4px}}
'''
JS = '''
/* leads: one archetype at a time; the last one you looked at is remembered on this device */
(function(){
%s
const bar=document.getElementById("lseg"), panel=document.getElementById("lpanel"), KEY="trsix-leads-tab";
const line=(p,l)=>`<div class="lline"><span class="lpct">${l[0]}%%</span><span class="la1"><span class="lmon">${p.lead[0]}</span>${l[1]}</span><span class="la2"><span class="lmon">${p.lead[1]}</span>${l[2]}</span></div>`;
function draw(k){
  const a=L.find(x=>x.k===k)||L[0];
  panel.innerHTML=a.picks.map(p=>`<div class="lpick">
    <div class="lphead">${p.when?`<span class="lpwhen">${p.when}</span>`:""}<span class="lplead">${p.lead.join(" + ")}</span>
      <span class="lpback">back: ${p.back}</span><span class="lpv"><b>${p.v[0]}%%</b> / ${p.v[1]}%%</span>
      <span class="lptop"><span class="${p.top?"":"is-top"}">${p.top?`Top lead: ${p.top[0]}, ${p.top[1].toFixed(1)} points ahead`:(p.x2!=null?"Top lead with Trick Room doubled":"Top lead")}</span><span class="lptr">Sets Trick Room <b>${p.tr}%%</b></span>${p.x2!=null?`<span>${p.x2>0.05?`Scored as fitted: ${p.x2.toFixed(1)} points behind the top lead`:"Scored as fitted, it matches the top lead"}</span>`:""}</span></div>
    ${p.rule?`<div class="lrule">${p.rule}</div>`:""}
    ${(p.general||[]).map(([m,ls])=>`<div class="lvs"><div class="lvshead"><span class="lvsname">${m}</span><span class="lvsshare">turn one, all archetypes</span></div>${ls.map(([pc,mv,ts])=>`<div class="lgen"><span class="lpct">${pc}%%</span><span>${mv}${ts.length?` <span class="lgt">(usually ${ts.join(", ")})</span>`:""}</span></div>`).join("")}</div>`).join("")}
    ${p.vs.map(([n,sh,v,ls])=>`<div class="lvs"><div class="lvshead"><span class="lvsname">vs ${n}</span><span class="lvsshare">${sh.toFixed(1)}%% of their leads</span>
      <span class="lvsv${v[0]<50?" low":""}">${v[0]}%% / ${v[1]}%%</span></div>${ls.map(l=>line(p,l)).join("")}</div>`).join("")}
    ${p.note?`<div class="lnote">${p.note}</div>`:""}</div>`).join("");
  bar.querySelectorAll(".lseg").forEach(b=>{const on=b.dataset.k===a.k; b.classList.toggle("on",on); b.setAttribute("aria-selected",on);});
  try{localStorage.setItem(KEY,a.k);}catch(e){}
}
bar.innerHTML=L.map(a=>`<button class="lseg" role="tab" aria-selected="false" data-k="${a.k}">${a.tab}</button>`).join("");
bar.addEventListener("click",e=>{const b=e.target.closest(".lseg"); if(b) draw(b.dataset.k);});
document.getElementById("lguide").addEventListener("click",e=>{const b=e.target.closest(".lgk"); if(b) draw(b.dataset.k);});
let start="tw"; try{start=localStorage.getItem(KEY)||"tw";}catch(e){}
draw(start);
})();
''' % L
page = sys.argv[2] if len(sys.argv) > 2 else 'trsheet/tr-sheet.html'
s = open(page).read()
s = re.sub(r'<!--PENDING-->.*?<!--/PENDING-->', '', s, flags=re.S)
if '<!--/LEADS-->' in s:
    a = s.index('<!--LEADS-->'); b = s.rindex('<!--/LEADS-->') + len('<!--/LEADS-->')
    s = s[:a] + '<!--LEADS-->\n' + SECTION + '\n<!--/LEADS-->' + s[b:]
else: s = s.replace('<!--LEADS-->', '<!--LEADS-->\n' + SECTION + '\n<!--/LEADS-->', 1)
s = s.replace('<!--JUMPLEADS-->', '<!--JUMPLEADS--><a href="#leads">Leads</a>', 1) if '<a href="#leads">' not in s else s
if '/* leads */' not in s: s = s.replace('@media (prefers-reduced-motion:reduce)', CSS.strip() + '\n@media (prefers-reduced-motion:reduce)', 1)
else:                                                       # replace the existing leads styles so CSS changes reach the page
    i = s.index('/* leads */'); j = s.index('@media (prefers-reduced-motion:reduce)', i); s = s[:i] + CSS.strip() + '\n' + s[j:]
s = re.sub(r'/\* leads: one archetype.*?\}\)\(\);\n+', '', s, flags=re.S)
assert s.count('<script>\n/* team */') == 1
s = s.replace('<script>\n/* team */', '<script>\n' + JS.strip() + '\n\n/* team */', 1)
out_path = sys.argv[3] if len(sys.argv) > 3 else page
open(out_path, 'w').write(s)
json.dump(out, open('tr_leads_data.json', 'w'), indent=1)
for c in log: print(c)
for b in BLOG: print('back', b)
print('ok', len(s), '->', out_path)
