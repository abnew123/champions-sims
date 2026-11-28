"""Is the regional-pick edge the team or the pilot? (the user, 2026-11-28: "run the skill-controlled version" of regional_pick.py)

regional_pick.py found that teams the predictor ranks high did better at the M-C regionals, but regional players were anonymous
there, so strong players choosing those teams could explain it. Here each regional player gets a skill estimate from elsewhere,
and the team's predicted strength is tested with skill held fixed, at the level of each real regional match:
  logit P(a beats b) = b_s (s_a - s_b) + b_m m_ab + skill terms
  s     the team's predicted Bo3 strength against the expected field (logit of its match win share; pre-event fit, as regional_pick)
  m     the predicted matchup beyond that (pre-event match log-odds for this pairing minus s_a - s_b)
Skill terms (each with a 'not known' indicator, so unlinked players cost nothing):
  online   the player's online-tournament skill (Limitless, M-B and M-C): a rating fitted on their games with the predictor's team
           log-odds as an offset, so a good team does not count as skill
  worlds   their match record at the 2026 World Championship (Aug 28-30, M-B: another format, so another team)
  pilot    one effect per player shared across the five regionals (ridge), so a player's results at other events count
Players are linked across events by name and country, and to online accounts by display name and country. Names are fetched from
the public standings pages, kept in memory, and stored only as one-way hashes in predictor/regional_links.json (git-ignored).
If b_s keeps its size with skill held fixed, the team edge is real; if it shrinks toward 0, it was the pilots.
  teamsearch/bin/teamsearch-py predictor/skill_control.py      -> predictor/skill_control.json, lines in predictor.log
"""
import os, sys, re, json, glob, time, html, hashlib, calendar, unicodedata, collections, urllib.request
import numpy as np, scipy.sparse as sp
from scipy.optimize import minimize
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M, meta as X
from parse_games import OFFMETA, TOURS
TS = os.path.dirname(M.HERE); sys.path.insert(0, TS)
import regsim, sets_lib as L
import regional_pick as RP
OUT = os.path.join(M.HERE, 'skill_control.json'); LINKS = os.path.join(M.HERE, 'regional_links.json')
EIDS = {'Worlds': '0036', 'Baltimore': '0037', 'Brisbane': '0038', 'Frankfurt': '0039', 'Recife': '0040', 'Louisville': '0041'}
UA = {'User-Agent': 'champions-sims research (personal, low rate)'}
USE = RP.USE; BO3 = RP.BO3; DAY = 86400

def norm(name):
    s = unicodedata.normalize('NFKD', html.unescape(name or '')).lower()                 # accents off, other scripts kept
    return ''.join(ch for ch in s if ch.isalnum() and not unicodedata.combining(ch))

def h(name): return hashlib.sha1(('champ-skill|' + norm(name)).encode()).hexdigest()[:16] if norm(name) else None

def get(u):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20) as r:
                time.sleep(0.6); return r.read().decode('utf-8', 'replace')
        except Exception: time.sleep(3 + 5 * k)

def fetch_links():
    """{'links': {event|pid: [name hash, country]}, 'worlds': [[p1, p2, winner], ...]} from the public pairings pages"""
    if os.path.exists(LINKS): return json.load(open(LINKS))
    J = dict(links={}, worlds=[])
    for ev, eid in EIDS.items():
        s = get(f"https://standings.limitlessvgc.com/{eid}/pairings") or ''
        rs = sorted({int(r) for r in re.findall(rf'href="/{eid}/pairings\?round=(\d+)"', s)})
        for r in rs:
            page = get(f"https://standings.limitlessvgc.com/{eid}/pairings?round={r}") or ''
            anchors = list(re.finditer(rf'href="/{eid}/player/(\d+)"', page))
            for i, a in enumerate(anchors):
                seg = page[a.end(): anchors[i + 1].start() if i + 1 < len(anchors) else len(page)]
                nm = re.search(r'<span class="text-center">(.*?)</span>', seg, re.S); c = re.search(r'title="([A-Z]{2})"', seg)
                if nm: J['links'][f'{ev}|{a.group(1)}'] = [h(nm.group(1)), c.group(1) if c else None]
            if ev == 'Worlds':
                for row in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.S):
                    p = re.findall(rf'href="/{eid}/player/(\d+)"', row)
                    if len(p) < 2: continue
                    w = re.search(rf'winner">(?:<!--\[-->)?<a href="/{eid}/player/(\d+)"', row)
                    J['worlds'].append([p[0], p[1], w.group(1) if w else None])
        M.say(f"  skill links: {ev}: {len(rs)} rounds, {sum(k.startswith(ev + '|') for k in J['links'])} players")
    json.dump(J, open(LINKS, 'w')); return J

def ridge_logit(Xm, y, lam, offset=None, w=None):
    """logistic regression on a sparse design with a ridge strength per column (0 = none) and an optional offset"""
    off = np.zeros(len(y)) if offset is None else offset; n = len(y)
    def f(b):
        z = Xm @ b + off; p = 1 / (1 + np.exp(-z))
        return np.sum(np.logaddexp(0, z) - y * z) + 0.5 * np.sum(lam * b * b), Xm.T @ (p - y) + lam * b
    r = minimize(f, np.zeros(Xm.shape[1]) if w is None else w, jac=True, method='L-BFGS-B', options=dict(maxiter=3000, gtol=1e-7))
    return r.x

def se_of(Xm, y, b, lam, offset, cols):
    """standard errors of the named columns from the full Hessian (so player effects fitted alongside are accounted for)"""
    z = Xm @ b + (offset if offset is not None else 0); p = 1 / (1 + np.exp(-z))
    H = (Xm.T @ sp.diags(p * (1 - p)) @ Xm).toarray() + np.diag(lam)
    return np.sqrt(np.diag(np.linalg.inv(H))[cols])

def online_skill(model):
    """online username -> (skill, games), and display-name hash + country -> usernames; skill fitted with the team log-odds as offset"""
    games, disp = [], collections.defaultdict(set)
    for f in glob.glob(os.path.join(TOURS, '*.json')):
        if f.endswith('index.json'): continue
        d = json.load(open(f))
        if d.get('no_sheets') or d['t']['format'] not in ('M-B', 'M-C') or OFFMETA.search(d['t']['name']): continue
        sheet = {}
        for p in d['standings']:
            u = (p.get('player') or '').lower()
            if not u: continue
            disp[(h(p.get('name')), p.get('country'))].add(u); disp[(h(u), p.get('country'))].add(u)
            dl = p.get('decklist') or []
            if len(dl) == 6:
                sets = [dict(species=x.get('id') or x.get('name'), item=x.get('item') or '', ability=x.get('ability') or '',
                             moves=[m for m in (x.get('attacks') or []) if m], nature=x.get('nature') or '') for x in dl]
                sheet[u] = M.Team([s['species'] for s in sets], sets)
        for m in d['pairings']:
            ar, br = m.get('player1'), m.get('player2')
            if not isinstance(ar, str) or not isinstance(br, str): continue
            a, b = ar.lower(), br.lower()
            if a not in sheet or b not in sheet: continue
            ws = [v.get('winner') for v in (m.get('games') or {}).values()] or [m.get('winner')]
            for wv in ws:
                if wv in (ar, br): games.append((a, b, int(wv == ar), sheet[a], sheet[b]))
    off = model.logit([(A, B, None) for *_, A, B in games])
    cnt = collections.Counter(x for a, b, *_ in games for x in (a, b)); us = sorted(u for u, n in cnt.items() if n >= 10); ix = {u: i for i, u in enumerate(us)}
    ri, ci, vv, keep = [], [], [], []
    for r, (a, b, *_) in enumerate(games):
        if a in ix or b in ix:
            k = len(keep); keep.append(r)
            if a in ix: ri.append(k); ci.append(ix[a]); vv.append(1.0)
            if b in ix: ri.append(k); ci.append(ix[b]); vv.append(-1.0)
    Xm = sp.csr_matrix((vv, (ri, ci)), shape=(len(keep), len(us))); y = np.array([games[r][2] for r in keep], dtype=float)
    th = ridge_logit(Xm, y, np.full(len(us), 20.0), offset=off[keep])
    return {u: (float(th[ix[u]]), cnt[u]) for u in us}, disp, len(games)

def main():
    t0 = time.time()
    links = fetch_links(); LK = links['links']
    rows, y, meta = M.load(lambda g: g['src'] in ('ladder', 'online')); lam = json.load(open(os.path.join(M.HERE, 'lambdas.json')))
    full = M.Model(lam, use=USE).fit(rows, y)
    M.say(f"  score (skill control fits): 1/{1 + len(set(RP.EVENTS.values()))} fits, {int((time.time() - t0) / 60)} min")
    ons, disp, ng = online_skill(full)
    # Worlds skill: shrunk match record (logit)
    W = collections.defaultdict(lambda: [0, 0])
    for a, b, wv in links['worlds']:
        if a and b and wv in (a, b):
            for p in (a, b): W[p][1] += 1
            W[wv][0] += 1
    key_of = lambda ev, pid: tuple(LK.get(f'{ev}|{pid}') or (None, None))
    worlds = {}
    for p, (wv, n) in W.items():
        k = key_of('Worlds', p)
        if k[0]: worlds[k] = (float(np.log((wv + 3) / (n - wv + 3))), n)
    def online_of(k):
        us = disp.get(k, set()) & set(ons)
        if not us: return None
        u = max(us, key=lambda u: ons[u][1]); return ons[u][0]
    # regional matches with both sheets, pre-event predictor terms (as regional_pick)
    R0 = json.load(open(os.path.join(M.ROOT, 'regionals', 'regional_sets.json'))); F0 = json.load(open(os.path.join(M.ROOT, 'regionals', 'field_sets.json')))
    sheets = {k: [L.normalize(dict(s)) for s in v] for k, v in {**R0, **F0}.items() if len(v) == 6}
    P = json.load(open(os.path.join(M.ROOT, 'regionals', 'pairings.json')))
    models, Ms, S = {}, [], {}
    for ev, d0 in RP.EVENTS.items():
        te = calendar.timegm(time.strptime(d0, '%Y-%m-%d')); hi = X.day(te - DAY)
        if d0 not in models:
            pre = [i for i, g in enumerate(meta) if g['t'] < te]; models[d0] = M.Model(lam, use=USE).fit([rows[i] for i in pre], y[pre])
            M.say(f"  score (skill control fits): {1 + len(models)}/{1 + len(set(RP.EVENTS.values()))} fits, {int((time.time() - t0) / 60)} min")
        m = models[d0]
        for days in (14, 28):
            lo = X.day(te - days * DAY); sd = X.sides(meta, rows, 'M-C', lo, hi)
            if len({p for p, *_ in sd}) >= 150: break
        _, groups, _, x, _ = X.pool(sd, min_players=1); FP = M.Pool(m, groups)
        ps = sorted({p for ms in P[ev]['rounds'].values() for t in ms for p in t[:2] if p and f'{ev}|{p}' in sheets})
        T = {p: M.Team([s['species'] for s in sheets[f'{ev}|{p}']], sheets[f'{ev}|{p}']) for p in ps}
        fs = BO3(1 / (1 + np.exp(-M.Pool(m, [[T[p]] for p in ps]).cross(FP)))) @ x
        s = {p: float(np.log(f / (1 - f))) for p, f in zip(ps, fs)}; S.update({(ev, p): v for p, v in s.items()})
        for ms in P[ev]['rounds'].values():
            for a, b, wv in ms:
                if not (a in T and b in T and wv in (a, b)): continue
                g = float(m.logit([(T[a], T[b], None)])[0]); q = BO3(1 / (1 + np.exp(-g))); z = float(np.log(q / (1 - q)))
                Ms.append(dict(ev=ev, a=a, b=b, y=int(wv == a), ds=s[a] - s[b], mm=z - (s[a] - s[b]), ka=key_of(ev, a), kb=key_of(ev, b)))
    # skill features
    oc = {}
    for d in Ms:
        for k in (d['ka'], d['kb']):
            if k not in oc: oc[k] = online_of(k) if k[0] else None
    multi = collections.Counter()
    seen_ev = collections.defaultdict(set)
    for d in Ms:
        for k in (d['ka'], d['kb']):
            if k[0]: seen_ev[k].add(d['ev'])
    pk = sorted(k for k, e in seen_ev.items()); pix = {k: i for i, k in enumerate(pk)}
    n_on = sum(1 for k in seen_ev if oc.get(k) is not None); n_w = sum(1 for k in seen_ev if k in worlds); n_multi = sum(1 for e in seen_ev.values() if len(e) > 1)
    M.say(f"skill control: {len(Ms)} regional matches with both sheets; {len(seen_ev)} players linked by name; with an online-tournament rating {n_on}"
          f" (from {ng} online games), with a Worlds record {n_w}, at 2+ M-C regionals {n_multi}")
    yv = np.array([d['y'] for d in Ms], dtype=float)
    def col(f): return np.array([f(d) for d in Ms], dtype=float)
    ds, mm = col(lambda d: d['ds']), col(lambda d: d['mm'])
    on = lambda k: oc.get(k) if oc.get(k) is not None else 0.0; onk = lambda k: float(oc.get(k) is not None)
    wl = lambda k: worlds[k][0] if k in worlds else 0.0; wk = lambda k: float(k in worlds)
    d_on, d_onk = col(lambda d: on(d['ka']) - on(d['kb'])), col(lambda d: onk(d['ka']) - onk(d['kb']))
    d_w, d_wk = col(lambda d: wl(d['ka']) - wl(d['kb'])), col(lambda d: wk(d['ka']) - wk(d['kb']))
    # pilot effects across the five regionals
    ri, ci, vv = [], [], []
    for r, d in enumerate(Ms):
        if d['ka'][0]: ri.append(r); ci.append(pix[d['ka']]); vv.append(1.0)
        if d['kb'][0]: ri.append(r); ci.append(pix[d['kb']]); vv.append(-1.0)
    PL = sp.csr_matrix((vv, (ri, ci)), shape=(len(Ms), len(pk)))
    specs = [('team only', [ds, mm], False), ('+ online skill', [ds, mm, d_on, d_onk], False), ('+ Worlds record', [ds, mm, d_w, d_wk], False),
             ('+ online + Worlds', [ds, mm, d_on, d_onk, d_w, d_wk], False), ('+ online + Worlds + pilot effects', [ds, mm, d_on, d_onk, d_w, d_wk], True),
             ('pilot fixed effects (within player)', [ds, mm], 'fe')]
    J = dict(matches=len(Ms), linked=len(seen_ev), online=n_on, worlds=n_w, multi=n_multi, models={})
    sd_s = float(np.std([v for v in ds]))
    def fit(cols, pilots, sel, plam=5.0):
        D = sp.hstack([sp.csr_matrix(np.column_stack(cols)[sel])] + ([PL[sel]] if pilots else [])).tocsr()
        lamv = np.concatenate([np.full(len(cols), 1e-6), np.full(PL.shape[1] if pilots else 0, 0.01 if pilots == 'fe' else plam)])
        b = ridge_logit(D, yv[sel], lamv); se = se_of(D, yv[sel], b, lamv, None, list(range(len(cols)))); return b, se
    for subset, sel in (('all matches', np.ones(len(Ms), bool)),
                        ('matches with a player seen at 2+ M-C regionals', np.array([len(seen_ev.get(d['ka'], ())) > 1 or len(seen_ev.get(d['kb'], ())) > 1 for d in Ms]))):
        J['models'][subset] = {}
        M.say(f"  {subset} ({int(sel.sum())} matches): coefficient on the team's predicted strength gap (b_s, 1 = as predicted) and on the matchup term (b_m);"
              f" what the top tenth's edge is worth against an average team")
        for name, cols, pilots in specs:
            b, se = fit(cols, pilots, sel)
            J['models'][subset][name] = dict(b=[float(v) for v in b[:len(cols)]], se=[float(v) for v in se])
            M.say(f"    {name:36s} b_s {b[0]:.2f} ± {se[0]:.2f}   b_m {b[1]:.2f} ± {se[1]:.2f}"
                  + (f"   online skill {b[2]:.2f} ± {se[2]:.2f}" if len(cols) > 2 and cols[2] is d_on else '')
                  + (f"   Worlds {b[-2]:.2f} ± {se[-2]:.2f}" if cols[-2] is d_w else ''))
    # selection: do skilled players bring teams the predictor likes? (their teams' predicted-strength percentile within the event)
    pct = {}
    for ev in RP.EVENTS:
        ks_ = [k for k in S if k[0] == ev]; v = np.array([S[k] for k in ks_]); r = v.argsort().argsort() / max(1, len(v) - 1)
        pct.update(dict(zip(ks_, r)))
    kp = {(ev, p): key_of(ev, p) for (ev, p) in S}
    grp = {'Worlds players': lambda k: k in worlds, 'at 2+ M-C regionals': lambda k: len(seen_ev.get(k, ())) > 1,
           'online-rated, top half of skill': lambda k: oc.get(k) is not None and oc[k] > np.median([v for v in oc.values() if v is not None]),
           'everyone else': lambda k: not (k in worlds or len(seen_ev.get(k, ())) > 1 or oc.get(k) is not None)}
    J['selection'] = {g: float(np.mean([pct[e] for e, k in kp.items() if f(k)] or [np.nan])) for g, f in grp.items()}
    M.say("  selection: mean predicted-strength percentile of the teams brought (0.50 = the event's middle): "
          + ', '.join(f"{g} {v:.2f} ({sum(1 for e, k in kp.items() if grp[g](k))})" for g, v in J['selection'].items()))
    sel_c = J['selection']['Worlds players'] - J['selection']['everyone else']
    J['selection_corr'] = sel_c
    b0 = J['models']['all matches']['team only']['b'][0]; b4 = J['models']['all matches']['+ online + Worlds + pilot effects']['b'][0]
    gap = []                                                            # the top tenth's predicted strength over its event's mean
    for ev in RP.EVENTS:
        v = np.array([x for (e, _), x in S.items() if e == ev]); v.sort(); gap.append((v[-max(3, len(v) // 10):].mean() - v.mean(), len(v)))
    dg = float(np.average([g for g, _ in gap], weights=[n for _, n in gap])); J['top10_gap'] = dg
    edge = lambda b: 1 / (1 + np.exp(-b * dg)) - 0.5
    bf = J['models']['all matches']['pilot fixed effects (within player)']['b'][0]; J['edge'] = dict(team_only=edge(b0), controls=edge(b4), within=edge(bf))
    M.say(f"  team-strength coefficient: {b0:.2f} with no control, {b4:.2f} with skill controls, {bf:.2f} within player; a top-tenth team against an average one"
          f" (pilots equal): {100 * edge(b0):+.1f} / {100 * edge(b4):+.1f} / {100 * edge(bf):+.1f} points of match win rate")
    json.dump(J, open(OUT, 'w'), indent=1)
    M.say(f"skill control done ({int((time.time() - t0) / 60)} min)")

if __name__ == '__main__': main()
