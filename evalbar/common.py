"""Shared by the eval bar scripts: where things live, the cached replays, and version 0 of the bar (the real-game win-chance model:
pssim/replay_feats.py's eleven features at the start of a turn -> logistic model fitted on real games, pssim/results/fit_real_value.json)."""
import os, sys, json, glob, math, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
def main_root():
    """The main checkout. Replay logs, results and binaries are git-ignored, so in a git worktree they exist only there. CHAMP_MAIN overrides."""
    if os.environ.get('CHAMP_MAIN'): return os.environ['CHAMP_MAIN']
    try: return os.path.dirname(subprocess.check_output(['git', '-C', REPO, 'rev-parse', '--path-format=absolute', '--git-common-dir'], text=True).strip())
    except Exception: return REPO
MAIN = main_root(); PSSIM = os.path.join(REPO, 'pssim'); LOGS = os.path.join(MAIN, 'pssim', 'replays_protect')
def replay_feats():
    """pssim/replay_feats.py reads its data files from the current folder, so import it from inside pssim/"""
    cwd = os.getcwd(); os.chdir(PSSIM); sys.path.insert(0, PSSIM)
    try: import replay_feats as RF
    finally: os.chdir(cwd)
    return RF
def games():
    """(replay id, log text) for every cached Reg M-C best-of-three game with open team sheets"""
    idx = json.load(open(os.path.join(LOGS, 'index.json')))
    for f in sorted(glob.glob(os.path.join(LOGS, '*.log'))):
        rid = os.path.basename(f)[:-4]
        if not idx.get(rid, {}).get('fmt', '').endswith('bo3'): continue
        log = open(f).read()
        if '|showteam|' in log: yield rid, log
sig = lambda z: 1 / (1 + math.exp(-max(-40, min(40, z))))
def v0_weights(): return json.load(open(os.path.join(MAIN, 'pssim', 'results', 'fit_real_value.json')))['real']     # [intercept, 11 weights]
def v0(w, f11): return sig(w[0] + sum(a * x for a, x in zip(w[1:], f11)))                                         # player 1's win chance
