"""Report for perish_fix.sh: the real Bo3 pairings with a Perish side, played by the sim in each arm, against the real games.
Per arm: the Perish side's sim win share against its real one (paired by game, SE by game), how often the sim's Perish side sang Perish
Song (any playout) against how often the human did (pssim/replays_protect logs), and how many Pokemon each side lost to a count.
  ../.venv/bin/python3 perish_fix.py report <folder> <arm> [<arm> ...]"""
import os, sys, json, glob, math, re
HERE = os.path.dirname(os.path.abspath(__file__))
CH = re.compile(r'^\|(c|c:|chat|raw|html|uhtml|uhtmlchange)\|')
def human_sang(pool_id, side):
    f = os.path.join(HERE, 'replays_protect', pool_id + '.log')
    if not os.path.exists(f): return None
    return any(l.startswith(f'|move|{side}') and '|Perish Song|' in l for l in open(f, errors='ignore') if not CH.match(l))
def report(folder, arms):
    J = json.load(open(os.path.join(folder, 'perish_pairs.json')))
    real = []
    for k, j in enumerate(J):
        m = j['meta']; mine = m['my_arch'] == 'Perish'
        four = j['mine'] if mine else j['theirs']; song = any('Perish Song' in x.get('moves', []) for x in four)
        real.append((mine, float(m['real_won']) if mine else 1.0 - m['real_won'], human_sang(m['pool_id'], 'p1' if mine else 'p2'), song))
    hs = [r[2] for r in real if r[2] is not None]
    print(f"Perish Song among the Perish side's brought four in {sum(r[3] for r in real)} of {len(real)} pairings")
    print(f"{len(J)} real pairings with a Perish side: the Perish side won {100 * sum(r[1] for r in real) / len(real):.1f}% for real; "
          f"the human sang Perish Song in {sum(hs)} of {len(hs)} games ({100 * sum(hs) / max(len(hs), 1):.0f}%)")
    for a in arms:
        d = os.path.join(folder, 'out_' + a); diffs, sims, sang, n_g, groups = [], [], 0, 0, {}
        for f in glob.glob(os.path.join(d, '*.json')):
            o = json.load(open(f)); k = o['job']; mine, rw, _, song = real[k]
            rows = [r for r in o.get('rows', []) if r.get('v') is not None]
            if not rows: continue
            v = sum(r['v'] for r in rows) / len(rows); p = v if mine else 1 - v
            sims.append(p); diffs.append(rw - p); groups.setdefault('Perish Song brought' if song else 'no Perish Song brought', []).append((rw, p))
            for r in rows:
                n_g += 1; log = r.get('log') or []
                part = 0 if mine else 1
                if any('Perish Song' in t.split(' || ')[part] for t in log if ' || ' in t): sang += 1
        if not sims: print(f'  {a}: nothing yet'); continue
        md = sum(diffs) / len(diffs); se = math.sqrt(sum((x - md) ** 2 for x in diffs) / max(len(diffs) - 1, 1) / len(diffs))
        print(f"  arm {a:6s} {len(sims):3d} games  sim Perish-side win {100 * sum(sims) / len(sims):5.1f}%  real - sim {100 * md:+5.1f} +- {100 * se:3.1f}"
              f"   sim's Perish side sang in {100 * sang / max(n_g, 1):4.1f}% of {n_g} playouts")
        for gname, gv in sorted(groups.items()):
            dd = [r - p for r, p in gv]; m_ = sum(dd) / len(dd); se_ = math.sqrt(sum((x - m_) ** 2 for x in dd) / max(len(dd) - 1, 1) / len(dd))
            print(f"      {gname:24s} {len(gv):3d} games  sim {100 * sum(p for _, p in gv) / len(gv):5.1f}%  real {100 * sum(r for r, _ in gv) / len(gv):5.1f}%  real - sim {100 * m_:+5.1f} +- {100 * se_:3.1f}")
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'report': report(a[1], a[2:])
