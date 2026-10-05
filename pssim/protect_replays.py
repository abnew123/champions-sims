"""Double-Protect check, real side (2026-10-04): fetch public Showdown replays of Reg M-C (Bo3 and ladder Bo1), cache the logs in
replays_protect/, and measure how often a Pokemon that just Protected successfully (a fresh Protect, not itself a second one) Protects
again on its next action, out of the times it acts again (a move, or a voluntary switch out). Also the overall Protect share of actions.
usage: python3 protect_replays.py fetch <pages per format> [bo3: Bo3 only]   |   rated <pages> (Bo3 by rating, highest first)      (polite: ~0.3 s between requests; resumes)
       python3 protect_replays.py stats [min rating]"""
import json, sys, time, urllib.request, os, re, glob, collections
FMTS = ['gen9championsvgc2026regmcbo3', 'gen9championsvgc2026regmc']
UA = {'User-Agent': 'champions-sims research (personal, low rate)'}
D = 'replays_protect'; os.makedirs(D, exist_ok=True)
PROTECT = {'Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Baneful Bunker', 'Silk Trap', 'Burning Bulwark', 'Obstruct'}
def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r: return r.read().decode()
        except Exception: time.sleep(2 + 3 * k)
    return None
def fetch(pages, only=None):
    idx = json.load(open(f'{D}/index.json')) if os.path.exists(f'{D}/index.json') else {}
    for fmt in [f for f in FMTS if not only or f.endswith(only)]:
        before = None
        for pg in range(pages):
            txt = get(f'https://replay.pokemonshowdown.com/search.json?format={fmt}' + (f'&before={before}' if before else '')); time.sleep(0.3)
            if not txt: break
            res = json.loads(txt)
            if not res: break
            for r in res[:50]:
                idx[r['id']] = {'fmt': fmt, 'rating': r.get('rating'), 'time': r.get('uploadtime')}
                p = f"{D}/{r['id']}.log"
                if os.path.exists(p): continue
                log = get(f"https://replay.pokemonshowdown.com/{r['id']}.log"); time.sleep(0.3)
                if log: open(p, 'w').write(log)
            before = res[-1]['uploadtime']; json.dump(idx, open(f'{D}/index.json', 'w'))
            print(f"{fmt} page {pg + 1}: {sum(1 for v in idx.values() if v['fmt'] == fmt)} replays", flush=True)
def fetch_rated(pages, fmt='gen9championsvgc2026regmcbo3'):
    """Bo3 replays in rating order (search sort=rating, page 1 = highest), for the Elo comparison"""
    idx = json.load(open(f'{D}/index.json')) if os.path.exists(f'{D}/index.json') else {}
    for pg in range(1, pages + 1):
        txt = get(f'https://replay.pokemonshowdown.com/search.json?format={fmt}&sort=rating&page={pg}'); time.sleep(0.3)
        if not txt: break
        res = json.loads(txt)
        if not res: break
        for r in res[:50]:
            idx[r['id']] = {'fmt': fmt, 'rating': r.get('rating'), 'time': r.get('uploadtime')}
            p = f"{D}/{r['id']}.log"
            if os.path.exists(p): continue
            log = get(f"https://replay.pokemonshowdown.com/{r['id']}.log"); time.sleep(0.3)
            if log: open(p, 'w').write(log)
        json.dump(idx, open(f'{D}/index.json', 'w'))
        print(f"rated page {pg}: ratings {res[0].get('rating')}-{res[-1].get('rating')}, {len(idx)} replays indexed", flush=True)
def acts(log):
    """per turn: {position: ('move', name, success) | ('switch',)} for each mon's own action, plus the set of positions active at turn start"""
    turns = []; cur = None; active = {}; started = False; tr = False
    lines = log.split('\n')
    for i, l in enumerate(lines):
        p = l.split('|')
        if len(p) < 2: continue
        if p[1] == 'turn': cur = {'act': {}, 'start': dict(active), 'tr': tr}; turns.append(cur); started = True; continue
        if p[1] == '-fieldstart' and 'Trick Room' in l: tr = True; continue
        if p[1] == '-fieldend' and 'Trick Room' in l: tr = False; continue
        if p[1] in ('switch', 'drag', 'replace'):
            pos = p[2][:3]; nm = p[2][5:]
            if cur is not None and pos in cur['start'] and pos not in cur['act'] and p[1] == 'switch' and active.get(pos) == cur['start'][pos]:
                cur['act'][pos] = ('switch',)                      # voluntary switch before this mon acted
            active[pos] = nm; continue
        if p[1] == 'move' and cur is not None and not any(x.startswith('[from]') for x in p[5:]):
            pos = p[2][:3]
            if pos in cur['act'] or active.get(pos) != cur['start'].get(pos): continue
            ok = None
            if p[3] in PROTECT:
                ok = False
                for l2 in lines[i + 1:i + 4]:
                    q = l2.split('|')
                    if len(q) > 3 and q[1] == '-singleturn' and q[2][:3] == pos: ok = True; break
            cur['act'][pos] = ('move', p[3], ok)
    return turns
def stats(minr=0):
    idx = json.load(open(f'{D}/index.json'))
    C = collections.defaultdict(collections.Counter)
    for f in glob.glob(f'{D}/*.log'):
        rid = os.path.basename(f)[:-4]; meta = idx.get(rid, {})
        if (meta.get('rating') or 0) < minr: continue
        tag = 'Bo3' if meta.get('fmt', '').endswith('bo3') else 'ladder'
        T = acts(open(f).read())
        for t in range(len(T)):
            for pos, a in T[t]['act'].items():
                C[tag]['actions'] += 1
                if a[0] == 'move' and a[1] in PROTECT: C[tag]['protects'] += 1
                fresh = a[0] == 'move' and a[1] in PROTECT and a[2] and not (t > 0 and T[t - 1]['act'].get(pos, ('',))[0] == 'move'
                                                                           and T[t - 1]['act'][pos][1] in PROTECT)
                if not fresh or t + 1 >= len(T): continue
                nxt = T[t + 1]['act'].get(pos)
                if nxt is None or T[t + 1]['start'].get(pos) != T[t]['start'].get(pos): continue
                for sfx in ('', '_tr' if T[t + 1]['tr'] else '_notr'):
                    C[tag]['opps' + sfx] += 1
                    if nxt[0] == 'move' and nxt[1] in PROTECT: C[tag]['double' + sfx] += 1; C[tag]['double_ok' + sfx] += bool(nxt[2])
                    if nxt[0] == 'switch': C[tag]['switch_after' + sfx] += 1
        C[tag]['games'] += 1
    return C
if __name__ == '__main__':
    if sys.argv[1] == 'fetch': fetch(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
    elif sys.argv[1] == 'rated': fetch_rated(int(sys.argv[2]))
    else:
        for tag, c in stats(int(sys.argv[2]) if len(sys.argv) > 2 else 0).items():
            print(f"{tag}: {c['games']} games, Protect {100*c['protects']/c['actions']:.1f}% of actions; after a fresh successful Protect, next action "
                  f"is Protect again {c['double']}/{c['opps']} = {100*c['double']/max(1,c['opps']):.1f}% (those succeeded {c['double_ok']}), "
                  f"switch out {100*c['switch_after']/max(1,c['opps']):.1f}% | Trick Room up: {100*c['double_tr']/max(1,c['opps_tr']):.1f}% of {c['opps_tr']}"
                  f" | down: {100*c['double_notr']/max(1,c['opps_notr']):.1f}% of {c['opps_notr']}")
