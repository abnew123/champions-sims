"""Shared pieces of the sheet kit: paths, a team's folder and config, the archetype list, the sim setups, and small statistics helpers."""
import json, os, math, platform, subprocess, sys, datetime

KIT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(KIT)
PSSIM = os.path.join(ROOT, 'pssim')
VENV_PY = os.path.join(ROOT, '.venv', 'bin', 'python3')          # numpy / scipy live here (the turn-one solver needs them)
MAC_MAX_THREADS = 10                                             # standing rule: never more than 10 busy cores on the Mac, all threads together

def rj(path): return json.load(open(path))
def wj(obj, path, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, 'w'), **kw)

# The opponents a sheet is built against. Two kinds, chosen by the sheet's "opponents" (see use_opponents):
#   archetypes  (the default, the sheets through 2026-10-05) ten archetype models mined from replays (pssim/opp_model_a/b.json)
#   cards       real teams grouped by core rules (sheetkit/opponents/, built by opponents.py): one card per group, shown under the tab
#               of its nearest archetype, plus one "other" card per archetype
# ARCHS (the opponent names every step iterates over, in a fixed order), SHARE, TABS, BY_KEY, GUIDE and CARDS are filled in place, so
# modules that imported them by name see the sheet's opponents.
_A = rj(os.path.join(KIT, 'archetypes.json'))
THEIR_NAMES = _A['their_names']                                  # how opposing Pokemon are written on the page
ARCHS, SHARE, TABS, BY_KEY, GUIDE, CARDS = [], {}, [], {}, [], {}
OPPONENTS = {'kind': 'archetypes'}

def use_opponents(kind='archetypes'):
    ARCHS.clear(); SHARE.clear(); TABS.clear(); BY_KEY.clear(); GUIDE.clear(); CARDS.clear(); OPPONENTS['kind'] = kind
    if kind == 'archetypes':
        os.environ.pop('OPP_MODEL', None)
        for a in _A['archetypes']:
            ARCHS.append(a['model']); SHARE[a['model']] = a['share']; BY_KEY[a['key']] = dict(a, models=[a['model']])
        TABS.extend(BY_KEY[k] for k in _A['tab_order']); GUIDE.extend(_A['guide'])
    elif kind == 'cards':
        C = rj(os.path.join(KIT, 'opponents', 'cards.json'))
        os.environ['OPP_MODEL'] = os.path.join(KIT, 'opponents', 'opp_model.json')       # every node child (t1sim.js) reads these models
        for c in C['cards']: ARCHS.append(c['model']); SHARE[c['model']] = c['share']; CARDS[c['model']] = c
        for t in C['tabs']: BY_KEY[t['key']] = {'key': t['key'], 'tab': t['tab'], 'models': t['cards']}; TABS.append(BY_KEY[t['key']])
        GUIDE.extend(C['guide_fallback'])
    else: sys.exit(f"unknown opponents '{kind}' (archetypes or cards)")
use_opponents('archetypes')

def opp_model():
    """The opponents' models: {name: {pairs: [{pair, share, t1, back, ...} x up to 6], sets}}"""
    if OPPONENTS['kind'] == 'cards': return rj(os.environ['OPP_MODEL'])
    return {**rj(os.path.join(PSSIM, 'opp_model_a.json')), **rj(os.path.join(PSSIM, 'opp_model_b.json'))}

class Sheet:
    """One team's folder, sheets/<slug>/: team.json (the six, MYTEAM format), sheet.json (config), text.json (the page's prose),
    notes.json (one mechanics note per archetype card), work/ (jobs, results, logs), picks.json, t1.json, sheet.html."""
    def __init__(self, slug):
        self.slug = slug
        self.dir = slug if os.path.isdir(slug) and os.path.exists(os.path.join(slug, 'sheet.json')) else os.path.join(ROOT, 'sheets', slug)
        self.dir = os.path.abspath(self.dir); self.slug = os.path.basename(self.dir)
        if not os.path.exists(self.p('sheet.json')): sys.exit(f"no sheet.json in {self.dir} (see sheetkit/README.md, 'A new team')")
        self.cfg = rj(self.p('sheet.json'))
        self.team_path = self.p(self.cfg.get('team', 'team.json'))
        self.team = rj(self.team_path)
        self.names = list(self.team)                             # team.json order: the order of every bring-matrix job
        assert len(self.names) == 6, 'team.json must hold six Pokemon'
        self.lead_order = self.cfg.get('lead_order', self.names) # how a lead pair is written (and simulated on turn one): first name first
        assert sorted(self.lead_order) == sorted(self.names), 'lead_order must list the same six as team.json'
        self.my_names = self.cfg.get('my_names', {})             # display names for my Pokemon, e.g. {"Indeedee-F": "Indeedee"}
        use_opponents(self.cfg.get('opponents', 'archetypes'))
    def p(self, *parts): return os.path.join(self.dir, *parts)
    def w(self, *parts): return os.path.join(self.dir, 'work', *parts)
    def lead(self, pair): return sorted(pair, key=self.lead_order.index)
    def back(self, pair): return sorted(pair, key=self.names.index)
    def grid_dir(self):
        g = os.path.normpath(self.p(self.cfg.get('grid_dir', 'work/grid')))      # relative to the team folder
        if not os.path.exists(os.path.join(g, 'gx_cells_tr_inc.json')): sys.exit(f"no one-on-one grid in {g}: run the 'grid' step first")
        return g

def sim_setup(name=None):
    S = rj(os.path.join(KIT, 'sim.json')); name = name or S['current']
    if name not in S['setups']: sys.exit(f"no sim setup '{name}' in sheetkit/sim.json (have: {', '.join(S['setups'])})")
    s = dict(S['setups'][name], name=name)
    env = dict(s.get('env', {}))
    for k in s.get('env_paths', []): env[k] = os.path.join(ROOT, env[k])
    env['EG_VALUE'] = os.path.join(ROOT, s['value'])
    s['env'] = env; s['binary'] = os.path.join(ROOT, s['binary']); s['engine_data'] = os.path.join(ROOT, s['engine_data'])
    return s

def threads_arg(n, force=False):
    """Default worker count: 3 on the Mac (the limit while the player may be on the machine), every core on Linux (a cloud box)."""
    mac = platform.system() == 'Darwin'
    if n is None: return 3 if mac else os.cpu_count()
    if mac and n > MAC_MAX_THREADS and not force:
        sys.exit(f"{n} threads on the Mac is over the {MAC_MAX_THREADS}-core limit across all threads (ask first; --force overrides)")
    return n

def now(): return datetime.datetime.now().strftime('%H:%M:%S')

class RunLog:
    """A run's log, written where the progress page (status_server.py, port 8766) looks: pssim/kit_<slug>_<step>.log, starting with
    'HH:MM:SS <jobs.json> -> <outdir>, ...' (both relative to pssim/) and ending with 'HH:MM:SS done: ...'."""
    def __init__(self, sheet, step, fresh=True):
        self.path = os.path.join(PSSIM, f'kit_{sheet.slug}_{step}.log')
        if fresh: open(self.path, 'w').close()
    def line(self, s):
        with open(self.path, 'a') as f: f.write(s + '\n')
        print(s, flush=True)
    def start(self, jobs, outdir, detail):
        self.line(f"{now()} {os.path.relpath(jobs, PSSIM)} -> {os.path.relpath(outdir, PSSIM)}, {detail}")
    def done(self, outdir):
        n = len([f for f in os.listdir(outdir) if f.endswith('.json')]) if os.path.isdir(outdir) else 0
        self.line(f"{now()} done: {n} result files in {os.path.relpath(outdir, PSSIM)}")

def run(cmd, env=None, cwd=None, **kw):
    e = dict(os.environ); e.update(env or {})
    return subprocess.run(cmd, env=e, cwd=cwd, check=True, **kw)

def mean(x): return sum(x) / len(x) if x else float('nan')
def paired_gap(pairs):
    """pairs: [(weight, [per-game differences])] over opposing teams -> (weighted mean difference, its standard error)"""
    W = sum(w for w, _ in pairs); m = var = 0.0
    for w, d in pairs:
        if len(d) < 2: continue
        mu = mean(d); m += w / W * mu; var += (w / W) ** 2 * sum((x - mu) ** 2 for x in d) / (len(d) - 1) / len(d)
    return m, math.sqrt(var)
