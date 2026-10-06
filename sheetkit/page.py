"""Build a team's page from sheetkit/template.html and the team folder.

  Leads     one card per archetype tab: the pick (picks.json: lead, back row, whole-game win %) with its turn-one lines (t1.json)
            and the card's mechanics note (notes.json)
  Team      computed from team.json (formes, types, stats) plus cards.json (role, note, where the set comes from)
  Coverage, Matchups, Speed   optional: charts.json / speed.json; a section the team folder has no data for is left out
  Prose     text.json (every paragraph that is about this team); theme, names and options from sheet.json

The template's slots are {{NAME}}; lines '@@if <section>' ... '@@end' are kept only when the team has that section."""
import re, html
from common import *

DEX = None
def dex():
    global DEX
    if DEX is None: DEX = rj(os.path.join(ROOT, 'native', 'champions_data.json'))
    return DEX
def idf(s): return re.sub(r'[^a-z0-9]', '', s.lower())
def pct(x): return int(round(100 * x))
def js(o):
    """a JS literal with bare object keys (compact; what the page's scripts read)"""
    if isinstance(o, dict): return '{' + ','.join(f'{k}:{js(v)}' for k, v in o.items()) + '}'
    if isinstance(o, list): return '[' + ','.join(js(x) for x in o) + ']'
    if isinstance(o, str): return json.dumps(o, ensure_ascii=False)
    if o is None: return 'null'
    if isinstance(o, bool): return 'true' if o else 'false'
    return repr(o)
def cj(o): return json.dumps(o, ensure_ascii=False, separators=(',', ':'))

# ---------------------------------------------------------------- leads
def their(n): return THEIR_NAMES.get(n, n)
def pair_name(p): return ' + '.join(their(x) for x in p.split(' + '))

def act(sheet, s):
    """'Mon: Move -> Target' (a turn-one action from the sim) -> how the page writes it"""
    L = sheet.cfg.get('lines', {}); mine = lambda n: sheet.my_names.get(n, n)
    mon, a = s.split(': ', 1); mv, _, tgt = a.partition(' -> ')
    if mv == 'switch': return 'switch &rarr; ' + mine(tgt)
    for r in L.get('rewrites', []):                              # e.g. the sim never offers Iron Head where it is not super effective
        if (mon, mv, tgt) == (r['mon'], r['move'], r['target']): mv = r['show']
    mv = L.get('short_moves', {}).get(mv, mv)
    return mv + (' ' + their(tgt) if tgt else '')

def lead_card(sheet, arch, pick, plans, note):
    lead = '+'.join(sheet.lead(pick['lead'])); back = sheet.back(pick['back']); mine = lambda n: sheet.my_names.get(n, n)
    stat = sheet.cfg.get('t1', {}).get('stat_move'); rows = []
    order = [pr['pair'] for pr in opp_model()[arch]['pairs']]         # equal shares: the opponent model's order
    for key, p in plans.items():
        a, l, pair = key.split('||')
        if a != arch or l != lead or p['share'] <= 0: continue
        assert list(p['back']) == back, f"{arch}: the turn-one lines were simulated with back row {p['back']}, the pick's is {back}: rerun the t1 step"
        lines = [[pc] + [act(sheet, x) for x in s.split(' | ')] for pc, s in p['mix']]
        st = sum(pc for pc, s in p['mix'] if stat and f': {stat}' in s) / 100
        rows.append((100 * p['share'], pair, p['pop'], p['worst'], lines, st))
    if not rows: sys.exit(f"{arch}: no turn-one lines for {lead} in t1.json: run the t1 step for the current picks")
    rows.sort(key=lambda r: (-r[0], order.index(r[1]))); W = sum(r[0] for r in rows)
    wavg = lambda i: sum(r[0] * r[i] for r in rows) / W
    card = {'lead': [mine(x) for x in lead.split('+')], 'back': ', '.join(mine(x) for x in back), 'v': [pct(wavg(2)), pct(wavg(3))], 'top': None}
    if stat: card['tr'] = pct(wavg(5))
    card.update(rule='', vs=[[pair_name(r[1]), round(r[0], 1), [pct(r[2]), pct(r[3])], r[4]] for r in rows], note=note or '', fb=1, fbw=round(100 * pick['v']))
    return card

def leads_data(sheet, picks=None, t1=None, notes=None, guide=None):
    picks = picks if picks is not None else rj(sheet.p('picks.json'))['picks']
    plans = (t1 if t1 is not None else rj(sheet.p('t1.json')))['plans']
    notes = notes if notes is not None else (rj(sheet.p('notes.json')) if os.path.exists(sheet.p('notes.json')) else {})
    guide = guide if guide is not None else (rj(sheet.p('guide.json')) if os.path.exists(sheet.p('guide.json')) else {})
    out = []
    for a in TABS:
        if a['model'] not in picks: continue
        card = lead_card(sheet, a['model'], picks[a['model']], plans, notes.get(a['model']))
        gp = guide.get('plans', {}).get(a['model'])
        if gp and gp.get('lines'): card['plan'] = gp['lines']               # the game plan, from the strategy-guide battles of this four
        out.append({'k': a['key'], 'tab': a['tab'], 'picks': [card]})
    return out

def tells_html(sheet):
    g = rj(sheet.p('guide.json')) if os.path.exists(sheet.p('guide.json')) else {}
    rows = []
    for t in g.get('tells', []):
        up = [f'{m} <span class="up">+{d}</span>' for m, d in t['mine'] if d > 0]; dn = [f'{m} <span class="dn">&minus;{-d}</span>' for m, d in t['mine'] if d < 0]
        rows.append(f'<li><span class="tx">{t["them"]}</span><span>' + ('bring ' + ', '.join(up) if up else '') + ('; ' if up and dn else '') +
                    ('leave ' + ', '.join(dn) if dn else '') + '</span></li>')
    return ''.join(rows)

def check_leads(sheet, L):
    """problems a reader would hit: a turn-one switch to a Pokemon that is not in the card's back row, line weights not summing to 100"""
    bad = []
    for tab in L:
        for c in tab['picks']:
            back = c['back'].split(', ')
            for name, _, _, lines in c['vs']:
                if sum(l[0] for l in lines) != 100: bad.append(f"{tab['tab']} vs {name}: lines sum to {sum(l[0] for l in lines)}%")
                for l in lines:
                    for a in l[1:]:
                        if a.startswith('switch &rarr; ') and a[len('switch &rarr; '):] not in back:
                            bad.append(f"{tab['tab']} vs {name}: switch to {a[len('switch &rarr; '):]}, which is not in the back row ({c['back']})")
    return bad

# ---------------------------------------------------------------- team cards
def stats(base, nature, sp):
    """Champions: HP = base + 75 + SP; the others floor((base + 20 + SP) x nature)"""
    n = dex()['natures'][idf(nature)]; keys = ('hp', 'atk', 'def', 'spa', 'spd', 'spe')
    mult = lambda k: 1.1 if n['plus'] == k else 0.9 if n['minus'] == k else 1.0
    return [base['hp'] + 75 + sp[0]] + [math.floor((base[k] + 20 + sp[i]) * mult(k)) for i, k in enumerate(keys) if i]

def team_cards(sheet):
    D = dex(); cards = rj(sheet.p('cards.json')) if os.path.exists(sheet.p('cards.json')) else {}; out = []
    for name, s in sheet.team.items():
        sp = D['species'][idf(s['species'])]; ab = s['ability']; shown = sheet.my_names.get(name, name)
        mega = (D['items'].get(idf(s['item']), {}).get('megaStone') or {}).get(sp['name'])
        if mega: sp = D['species'][idf(mega)]; ab = f"{s['ability']}, then {sp['abilities']['0']}"; shown = 'Mega ' + shown
        c = cards.get(name, {})
        out.append({'n': shown, 't': ' / '.join(sp['types']), 'role': c.get('role', ''), 'item': s['item'], 'ab': ab, 'nat': s['nature'], 'sp': s['evs'],
                    'st': stats(sp['stats'], s['nature'], s['evs']), 'mv': s['moves'], 'note': c.get('note', ''), 'src': c.get('src', '')})
    return out

# ---------------------------------------------------------------- the page
WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six']
def theme_block(t):
    rows = [('ground', 'panel', 'panel-2'), ('ink', 'ink2', 'ink3'), ('rule', 'rule-2'), ('accent', 'accent-soft')]
    return ''.join('  ' + ' '.join(f'--{k}:{t[k]};' for k in r) + '\n' for r in rows)

def render(sheet, L=None, template=None):
    c = sheet.cfg; text = rj(sheet.p('text.json')); T = open(template or os.path.join(KIT, 'template.html')).read()
    charts = rj(sheet.p('charts.json')) if os.path.exists(sheet.p('charts.json')) else {}
    speed = rj(sheet.p('speed.json')) if os.path.exists(sheet.p('speed.json')) else {}
    tells = tells_html(sheet) if template is None else ''      # a frozen old template has no slot for them
    have = {'coverage': bool(charts.get('coverage')), 'matchups': bool(charts.get('matchups')), 'speed': bool(speed.get('rows')), 'tells': bool(tells)}
    have['charts'] = have['coverage'] or have['matchups']
    # optional sections
    out, keep = [], True
    for line in T.split('\n'):
        if line.startswith('@@if '): keep = have[line[5:].strip()]
        elif line == '@@end': keep = True
        elif keep: out.append(line)
    T = '\n'.join(out)
    L = L if L is not None else leads_data(sheet)
    stat = c.get('t1', {}).get('stat_move'); N = charts.get('attackers', []); short = c.get('short_names', {}); mine = lambda n: sheet.my_names.get(n, n)
    paras = lambda xs, pre, tag='<p class="snote">': ''.join(f'{pre}{tag}{x}</p>\n' for x in xs)
    tr_first = c.get('matchups_default', 'notr') == 'tr'
    btn = lambda tr, on: (f'<button type="button" class="mxm{" on" if on else ""}" role="tab" aria-selected="{"true" if on else "false"}" data-tr="{tr}">'
                          f'{"Trick Room up" if tr else "No Trick Room"}</button>')
    h2 = text.get('speed_h2', 'Speed')
    slots = {
        'TITLE': text['title'], 'SUB': text['sub'], 'THEME_NOTE': c['theme'].get('note', 'Layout: one reading column, sticky section bar'),
        'THEME_LIGHT': theme_block(c['theme']['light']), 'THEME_DARK': theme_block(c['theme']['dark']),
        'NAV': '<!--JUMPLEADS--><a href="#leads">Leads</a><a href="#team">Team</a>' + ''.join(
            f'<a href="#{k}">{k.capitalize()}</a>' for k in ('coverage', 'matchups', 'speed') if have[k]),
        'LEADS_INTRO': paras(text['leads_intro'], '    '),
        'LGUIDE': '<p class="lguide" id="lguide"><b>Which tab:</b> take the first match in their six. ' + ' &middot; '.join(
            f'{w}&nbsp;&rarr;&nbsp;<button type="button" class="lgk" data-k="{k}">{BY_KEY[k]["tab"]}</button>' for w, k in GUIDE) + '</p>',
        'LEADS_METHOD': text['leads_method'], 'STORAGE_KEY': c.get('storage_key', sheet.slug + '-leads-tab'),
        'T1_STAT': f'<span class="lptr">Sets {stat} <b>${{p.tr}}%</b></span>' if stat else '',
        'L_DATA': 'const L=[\n' + ',\n'.join(js(t) for t in L) + '\n];',
        'TEAM_H2': text.get('team_h2', 'The six'), 'TEAM_INTRO': text['team_intro'],
        'T_DATA': 'const T=[\n' + ',\n'.join(' ' + js(m) for m in team_cards(sheet)) + '\n];',
        'FOOTER': paras(text['footer'], '  ', '<p>'), 'TELLS': tells,
    }
    if have['coverage']: slots.update(COV_INTRO=paras(text['cov_intro'], '    '), C_DATA='const C=' + cj(charts['coverage']) + ';', N_ATTACKERS=WORDS[len(N)])
    if have['matchups']:
        slots.update(MX_INTRO=text['mx_intro'], MX_FOOT=text['mx_foot'], MX_COLSPAN=str(len(N) + 1), MX_DEFAULT='true' if tr_first else 'false',
                     MX_BAR=btn(1, True) + btn(0, False) if tr_first else btn(0, True) + btn(1, False),
                     MX_HEAD=''.join(f'<th scope="col"><span class="lg">{mine(n)}</span><span class="sm">{short.get(n) or (mine(n) if len(mine(n)) <= 6 else mine(n)[:5])}</span></th>' for n in N),
                     N_DATA='const N=' + cj([mine(n) for n in N]) + ';', X_DATA='const X=' + cj(charts['matchups']) + ';')
    if have['charts']: slots['XROW_TABLES'] = cj([i for i, k in (('covbody', 'coverage'), ('mxbody', 'matchups')) if have[k]])
    if have['speed']:
        foot = f'<p class="body spdnote">{text["speed_foot"]}</p>' if text.get('speed_foot') else ''      # indented by the template
        slots.update(SPEED_H2=h2, SPEED_INTRO=text['speed_intro'], SPEED_FOOT=foot, SPEED_COMMENT=h2[0].lower() + h2[1:],
                     R_DATA='const R=[' + ',\n '.join(cj(r) for r in speed['rows']) + '];')
    missing = set(re.findall(r'\{\{([A-Z0-9_]+)\}\}', T)) - set(slots)
    assert not missing, f'template slots without a value: {missing}'
    return re.sub(r'\{\{([A-Z0-9_]+)\}\}', lambda m: slots[m.group(1)], T), L

# ---------------------------------------------------------------- comparing two pages
BLOCKS = {'L': r'^const L=\[\n[\s\S]*?\n\];$', 'T': r'^const T=\[\n[\s\S]*?\n\];$', 'C': r'^const C=\[.*\];$', 'N': r'^const N=\[.*\];$',
          'X': r'^const X=\[.*\];$', 'R': r'^const R=\[[\s\S]*?\];$'}
def blocks(path): return json.loads(subprocess.run(['node', os.path.join(KIT, 'blocks.js'), path], capture_output=True, text=True, check=True).stdout)
def shell(s):
    """the page with each data block replaced by its name: markup, styles and scripts only"""
    for k, rx in BLOCKS.items(): s = re.sub(rx, f'<<{k}>>', s, count=1, flags=re.M)
    return s
def tie_order(L):
    """leads data with each card's opposing leads sorted by share, then name: two leads with the same share have no meaningful order"""
    return [dict(t, picks=[dict(c, vs=sorted(c['vs'], key=lambda r: (-r[1], r[0]))) for c in t['picks']]) for t in L or []]
def compare(a, b):
    """-> (differences, notes) between two page files: data blocks by value, everything else byte for byte"""
    A, B = blocks(a), blocks(b); diff = [f'data block {k} differs' for k in BLOCKS if A[k] != B[k] and k != 'L']; notes = []
    if A['L'] != B['L']:
        if tie_order(A['L']) == tie_order(B['L']):
            n = sum(ca['vs'] != cb['vs'] for ta, tb in zip(A['L'], B['L']) for ca, cb in zip(ta['picks'], tb['picks']))
            notes.append(f'leads: opposing leads with equal share are listed in a different order on {n} cards (nothing else differs)')
        else: diff.append('data block L differs')
    sa, sb = shell(open(a).read()), shell(open(b).read())
    if sa != sb:
        la, lb = sa.split('\n'), sb.split('\n'); n = sum(x != y for x, y in zip(la, lb)) + abs(len(la) - len(lb))
        first = next((i for i, (x, y) in enumerate(zip(la, lb)) if x != y), min(len(la), len(lb)))
        diff.append(f'markup/styles/scripts differ on {n} lines (first: line {first + 1})')
    return diff, notes
