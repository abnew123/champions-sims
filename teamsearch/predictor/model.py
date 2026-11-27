"""Matchup predictor learned from real results (the user, 2026-11-27): P(team A beats team B in one game) from what is on the two
team sheets, fitted to real ladder games, with no battle simulation and no hand-made archetypes. Light: a logistic model with
antisymmetric features, so P(A, B) = 1 - P(B, A) and a team never plays itself at other than 50%.

Feature blocks (each with its own ridge strength):
  sp    species on the sheet (count difference A - B)
  tok   set details: each item, ability and move on the sheet (count difference)
  attr  generic per-Pokemon attributes summed over the six: types and base stats (so a species never seen gets a sensible value
        from what it is; species and set weights then learn only what these miss)
  pair  species-versus-species: +1 for (u on A, v on B), -1 for (v on A, u on B), one feature per unordered pair of common species
  tpair type-versus-type, the same way over the two sheets' type counts (transfers to new species)
  pl    each player (+1 / -1): skill control only, left out when predicting teams
  rat   the rating gap when both players were rated (log-odds of the Elo expectation): skill control only, zero when predicting teams
Ridge strengths are in games: the penalty is lam * w^2 / 2 against the summed log loss.
Fitted by L-BFGS on the mean log loss plus the ridge terms.
"""
import os, sys, json, gzip, math, re, time, collections
import numpy as np, scipy.sparse as sp
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
GAMES = os.path.join(HERE, 'games.jsonl.gz'); LOG = os.path.join(HERE, 'predictor.log')
ENG = json.load(open(os.path.join(ROOT, 'native', 'engine_data_full.json')))
idf = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
TYPES = sorted(ENG['types']) if isinstance(ENG['types'], dict) else sorted(ENG['types'])
STATS = ('hp', 'atk', 'def', 'spa', 'spd', 'spe')
MEGA_OF = {idf(v['requiredItem']): k for k, v in ENG['species'].items() if v.get('isMega') and v.get('requiredItem')}

def say(s):
    with open(LOG, 'a') as f: f.write(f"{time.strftime('%I:%M %p')} {s}\n")

def mon_attr(spid, item=''):
    """types (one-hot) and base stats / 100 of a Pokemon; a Mega stone it holds adds half its Mega's stat gain (one Mega a game)"""
    e = ENG['species'].get(spid)
    if e is None: return None
    v = {f't:{t}': 1.0 for t in e['types']}
    for s in STATS: v[f's:{s}'] = e['stats'][s] / 100.0
    m = MEGA_OF.get(idf(item))
    if m and ENG['species'][m].get('baseSpeciesId', '') == e.get('baseSpeciesId', spid):
        for s in STATS: v[f's:{s}'] += 0.5 * (ENG['species'][m]['stats'][s] - e['stats'][s]) / 100.0
    return v

class Team:
    """a six: species ids, and set tokens when the sheet is known"""
    __slots__ = ('sp', 'tok', 'attr', 'types')
    def __init__(self, six, sets=None):
        self.sp = [idf(x) for x in six]
        by = {idf(s['species']): s for s in (sets or [])}
        self.tok = collections.Counter(); self.attr = collections.Counter(); self.types = collections.Counter()
        for x in self.sp:
            s = by.get(x)
            if s:
                if s.get('item'): self.tok['i:' + idf(s['item'])] += 1
                if s.get('ability'): self.tok['a:' + idf(s['ability'])] += 1
                for m in s.get('moves', []): self.tok['m:' + idf(m)] += 1
            a = mon_attr(x, s.get('item', '') if s else '')
            if a:
                for k, v in a.items(): self.attr[k] += v
                for k in a:
                    if k.startswith('t:'): self.types[k[2:]] += 1

class Model:
    BLOCKS = ('sp', 'tok', 'attr', 'pair', 'tpair', 'pl', 'rat')
    def __init__(self, lam=None, use=None, min_sp=20, min_tok=20, min_pair=300):
        self.lam = dict(sp=300.0, tok=300.0, attr=100.0, pair=3000.0, tpair=1000.0, pl=100.0, rat=1.0) | (lam or {})
        self.use = set(use or ('sp', 'tok', 'attr', 'pair', 'tpair', 'rat'))
        self.min_sp, self.min_tok, self.min_pair = min_sp, min_tok, min_pair

    def vocab(self, rows):
        c_sp, c_tok = collections.Counter(), collections.Counter()
        for A, B, *_ in rows:
            for T in (A, B): c_sp.update(T.sp); c_tok.update(T.tok.keys())
        rows = [r if len(r) > 3 else (*r, ()) for r in rows]
        self.sp_ix = {s: i for i, s in enumerate(sorted(s for s, n in c_sp.items() if n >= self.min_sp))}
        self.tok_ix = {s: i for i, s in enumerate(sorted(s for s, n in c_tok.items() if n >= self.min_tok))}
        common = sorted(s for s, n in c_sp.items() if n >= self.min_pair)
        self.pair_ix = {(u, v): i for i, (u, v) in enumerate((u, v) for a, u in enumerate(common) for v in common[a + 1:])}
        self.attr_ix = {k: i for i, k in enumerate([f't:{t}' for t in TYPES] + [f's:{s}' for s in STATS])}
        self.tpair_ix = {(u, v): i for i, (u, v) in enumerate((u, v) for a, u in enumerate(TYPES) for v in TYPES[a + 1:])}
        self.tpair_ix |= {(u, u): len(self.tpair_ix) + i for i, u in enumerate(TYPES)}  # never set (antisymmetric), kept for shape
        c_pl = collections.Counter(p for *_, pl in rows for p in pl)
        self.pl_ix = {p: i for i, p in enumerate(sorted(p for p, n in c_pl.items() if n >= 5))}
        off = 0; self.blocks = {}
        for b, ix in (('sp', self.sp_ix), ('tok', self.tok_ix), ('attr', self.attr_ix), ('pair', self.pair_ix), ('tpair', self.tpair_ix), ('pl', self.pl_ix), ('rat', {0: 0})):
            if b in self.use: self.blocks[b] = (off, off + len(ix)); off += len(ix)
        self.d = off

    def row(self, A, B, rgap=None, pl=None):
        """sparse feature row (cols, vals) for A vs B; pl = (player A, player B) for the skill-control block, None when predicting"""
        cols, vals = [], []
        o = self.blocks
        def add(b, ix, key, v):
            if b not in o: return
            i = ix.get(key)
            if i is not None and v: cols.append(o[b][0] + i); vals.append(v)
        for s, n in collections.Counter(A.sp).items(): add('sp', self.sp_ix, s, n)
        for s, n in collections.Counter(B.sp).items(): add('sp', self.sp_ix, s, -n)
        for k in set(A.tok) | set(B.tok): add('tok', self.tok_ix, k, A.tok[k] - B.tok[k])
        for k in set(A.attr) | set(B.attr): add('attr', self.attr_ix, k, A.attr[k] - B.attr[k])
        pc = collections.Counter()
        for u in A.sp:
            for v in B.sp:
                if u == v: continue
                if u < v: pc[(u, v)] += 1
                else: pc[(v, u)] -= 1
        for k, n in pc.items(): add('pair', self.pair_ix, k, n)
        tc = collections.Counter()
        for u, a in A.types.items():
            for v, b in B.types.items():
                if u == v: continue
                if u < v: tc[(u, v)] += a * b
                else: tc[(v, u)] -= a * b
        for k, n in tc.items(): add('tpair', self.tpair_ix, k, n / 6.0)
        if rgap is not None: add('rat', {0: 0}, 0, rgap)
        if pl: add('pl', self.pl_ix, pl[0], 1.0); add('pl', self.pl_ix, pl[1], -1.0)
        return cols, vals

    def matrix(self, rows):
        indptr, cols, vals = [0], [], []
        for A, B, rg, *pl in rows:
            c, v = self.row(A, B, rg, pl[0] if pl else None); cols += c; vals += v; indptr.append(len(cols))
        return sp.csr_matrix((np.array(vals, dtype=np.float64), np.array(cols, dtype=np.int32), np.array(indptr)), shape=(len(rows), self.d))

    def fit(self, rows, y, w0=None):
        self.vocab(rows); X = self.matrix(rows); y = np.asarray(y, dtype=np.float64); n = len(y)
        lam = np.zeros(self.d)
        for b, (a, z) in self.blocks.items(): lam[a:z] = self.lam[b]
        self.n_fit = n
        def f(w):
            z = X @ w; p = 1 / (1 + np.exp(-z))
            ll = np.sum(np.logaddexp(0, z) - y * z) / n
            g = X.T @ (p - y) / n + lam * w / n
            return ll + 0.5 * np.sum(lam * w * w) / n, g
        r = minimize(f, np.zeros(self.d) if w0 is None else w0, jac=True, method='L-BFGS-B', options=dict(maxiter=2000, ftol=1e-12, gtol=1e-8))
        self.w = r.x; return self

    def logit(self, rows):
        return self.matrix(rows) @ self.w

    def weights(self, block):
        a, z = self.blocks[block]; ix = {'sp': self.sp_ix, 'tok': self.tok_ix, 'attr': self.attr_ix, 'pair': self.pair_ix, 'tpair': self.tpair_ix, 'pl': self.pl_ix}[block]
        return {k: self.w[a + i] for k, i in ix.items()}

def rgap(g):
    return (g['r1'] - g['r2']) / 400 * math.log(10) if g.get('r1') and g.get('r2') else None

def load(filter=None):
    rows, y, meta = [], [], []
    for l in gzip.open(GAMES, 'rt'):
        g = json.loads(l)
        if filter and not filter(g): continue
        rows.append((Team(g['six1'], g['sets1']), Team(g['six2'], g['sets2']), rgap(g), (g['p1'], g['p2']))); y.append(g['win']); meta.append(g)
    return rows, np.array(y, dtype=float), meta

def logloss(z, y):
    return float(np.mean(np.logaddexp(0, z) - y * z))
