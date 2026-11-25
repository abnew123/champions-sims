"""Every round's pairings and every player's team for the Reg M-C regionals (the user, 2026-11-25: run each past regional through the
sim, (1) as a random Monte Carlo of the event and (2) on the real pairings with the sim's odds in place of the real results).
regional_teams.json holds only the top 256 (Louisville: Day 2); round 1 at Baltimore had 31 of its 542 tables between two of them.
Pairings: Limitless's /<id>/pairings?round=r pages, kept as player ids and the winner's id (None: a tie, a bye or no result).
Teams: each player's open team sheet, as fetch_event.py. Raw pages carry player names and are not kept; nothing written has a name.
Polite: 1 request / 0.6 s; resumes (a round or team already saved is not fetched again).
Out: pairings.json {event: {"rounds": {r: [[p1, p2, winner], ...]}}}, field_sets.json {"<event>|<pid>": six sets} (players not in
regional_sets.json), field_teams.json [{event, pid, six, arch}] for every player in the pairings with a full sheet in either file.
  ../teamsearch/bin/teamsearch-py fetch_field.py
"""
import json, re, sys, os, time, html, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'teamsearch')); sys.path.insert(0, os.path.join(ROOT, 'pssim'))
import sets_lib as L
from pro_replays import arch
from cluster_opps import norm
EV = {'Baltimore': '0037', 'Brisbane': '0038', 'Frankfurt': '0039', 'Recife': '0040', 'Louisville': '0041'}
PP, FS, FT, RS = (os.path.join(HERE, f) for f in ('pairings.json', 'field_sets.json', 'field_teams.json', 'regional_sets.json'))
LOG = os.path.join(HERE, 'fetch_field.log')

def say(s):
    with open(LOG, 'a') as f: f.write(f"{time.strftime('%I:%M %p')} {s}\n")

def get(u):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'champions-sims research (personal, low rate)'}), timeout=20) as r:
                time.sleep(0.6); return r.read().decode('utf-8', 'replace')
        except Exception: time.sleep(3 + 5 * k)

def rounds(eid):
    s = get(f"https://standings.limitlessvgc.com/{eid}/pairings")
    return sorted({int(r) for r in re.findall(rf'href="/{eid}/pairings\?round=(\d+)"', s or '')})

def matches(eid, r):
    s = get(f"https://standings.limitlessvgc.com/{eid}/pairings?round={r}")
    if not s: return None
    out = []
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', s, re.S):
        p = re.findall(rf'href="/{eid}/player/(\d+)"', row)
        if not p: continue
        w = re.search(rf'winner">(?:<!--\[-->)?<a href="/{eid}/player/(\d+)"', row)
        out.append([p[0], p[1] if len(p) > 1 else None, w.group(1) if w else None])
    return out

def teamlist(eid, pid):
    s = get(f"https://standings.limitlessvgc.com/{eid}/player/{pid}/teamlist")
    if not s: return None
    sets = []
    for name, body in re.findall(r'<a href="/00\d\d/pokemon/[^"]+">(.*?)</a></div>(.*?)</ul>', s, re.S):
        item = re.search(r'<div class="item">(.*?)</div>', body); abil = re.search(r'<div class="ability">Ability: (.*?)</div>', body)
        nat = re.search(r'Stat Alignment: (.*?)</div>', body); moves = re.findall(r'<li>(.*?)</li>', body)
        sets.append({'species': html.unescape(name), 'item': html.unescape(item.group(1)) if item else '',
                     'ability': html.unescape(abil.group(1)) if abil else '', 'nature': nat.group(1) if nat else '',
                     'moves': [html.unescape(m) for m in moves]})
    return sets

def main():
    P = json.load(open(PP)) if os.path.exists(PP) else {}
    for ev, eid in EV.items():
        e = P.setdefault(ev, {'rounds': {}})
        for r in rounds(eid):
            if str(r) in e['rounds']: continue
            m = matches(eid, r)
            if m: e['rounds'][str(r)] = m
        json.dump(P, open(PP, 'w'))
        say(f"{ev}: {len(e['rounds'])} rounds, {sum(len(m) for m in e['rounds'].values())} tables")
    R = json.load(open(RS)); F = json.load(open(FS)) if os.path.exists(FS) else {}
    want = [(ev, p) for ev in EV for p in sorted({x for m in P[ev]['rounds'].values() for t in m for x in t[:2] if x})]
    todo = [(ev, p) for ev, p in want if f'{ev}|{p}' not in R and f'{ev}|{p}' not in F]
    say(f"team sheets: {len(want)} players, {len(todo)} to fetch")
    for n, (ev, p) in enumerate(todo, 1):
        s = teamlist(EV[ev], p)
        if s is not None: F[f'{ev}|{p}'] = s
        if n % 50 == 0 or n == len(todo):
            json.dump(F, open(FS, 'w')); say(f"  team sheets: {n}/{len(todo)} players")
    T = []
    for ev, p in want:
        sets = R.get(f'{ev}|{p}') or F.get(f'{ev}|{p}')
        if not sets or len(sets) != 6: continue
        six = [L.normalize(dict(s))['species'] for s in sets]
        T.append(dict(event=ev, pid=p, six=six, arch=arch([norm(x) for x in six])))
    json.dump(T, open(FT, 'w'))
    say(f"field teams: {len(T)} of {len(want)} players with a full sheet; fetch done")

if __name__ == '__main__': main()
