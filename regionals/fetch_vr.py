"""Add a regional from Victory Road's open team sheets when Limitless has none yet (user, 2026-10-12: Louisville, two days
after the event, had no Limitless team lists). Victory Road's event page lists every Day 2 Masters team with a VR Pastes link;
each paste's data comes from the paste site's JSON endpoint (species, item, ability, nature, moves: an open team sheet, no stat
points). Placements are matched to Limitless player ids by place (the two sites' places agreed for every name that matched),
so a later Limitless import (fetch_event.py) skips these players. Both saved pages have player names, so neither is in git;
nothing written here has a name.
  curl -s -A '...' https://victoryroad.pro/<event slug>/ -o vr_<id>.html            (and standings_<id>.html, see fetch_event.py)
  python3 fetch_vr.py <Event> <Limitless id>          polite: 1 request / 0.6 s; resumes
"""
import json, re, sys, os, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'teamsearch')); sys.path.insert(0, os.path.join(ROOT, 'pssim'))
import sets_lib as L
from pro_replays import arch
from cluster_opps import norm
EVENT, EID = sys.argv[1], sys.argv[2]
TP, SP = os.path.join(HERE, 'regional_teams.json'), os.path.join(HERE, 'regional_sets.json')
API = 'https://vrpaste-backend.vercel.app/api/paste/{}?lang=english'

def get_json(u):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'champions-sims research (personal, low rate)'}), timeout=20) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except Exception: time.sleep(3 + 5 * k)

def masters_rows(page):
    """[(place, paste id)] from the first results table (Masters): rows in order until the places start over"""
    out = []
    for r in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.S):
        pm = re.search(r'https://vrpastes\.com/([A-Za-z0-9]+)', r); pl = re.search(r'<td[^>]*><b>(\d+)</b></td>', r)
        if not (pm and pl): continue
        if out and int(pl.group(1)) < out[-1][0]: break
        out.append((int(pl.group(1)), pm.group(1)))
    return out

if __name__ == '__main__':
    vr = masters_rows(open(os.path.join(HERE, f'vr_{EID}.html')).read())
    lim = open(os.path.join(HERE, f'standings_{EID}.html')).read()
    rows = {int(p): (cls or '', pid) for cls, p, pid in re.findall(rf'<tr(?: class="([^"]*)")?><td>(\d+)</td><td><a href="/{EID}/player/(\d+)"', lim)}
    T = json.load(open(TP)); R = json.load(open(SP)); have = {(t['event'], t['pid']) for t in T}; added = 0
    for place, paste in vr:
        if place not in rows: print(f"place {place}: not in the Limitless standings, skipped", flush=True); continue
        cls, pid = rows[place]; key = f"{EVENT}|{pid}"
        if (EVENT, pid) in have: continue
        if key not in R:
            d = get_json(API.format(paste)); time.sleep(0.6)
            sets = [dict(species=m['species'], item=m.get('item') or '', ability=m.get('ability') or '', nature=m.get('nature') or '',
                         moves=list(m.get('moves') or [])) for m in (d or {}).get('teams') or []]
            if len(sets) != 6: print(f"place {place}: paste {paste} has {len(sets)} Pokemon, skipped", flush=True); continue
            R[key] = sets
        six = [L.normalize(dict(s))['species'] for s in R[key]]
        T.append(dict(event=EVENT, place=place, day2='day2' in cls.split(), pid=pid, six=six, arch=arch([norm(x) for x in six]), src='victoryroad'))
        added += 1
        if added % 25 == 0: json.dump(R, open(SP, 'w')); print(time.strftime('%I:%M %p'), added, flush=True)
    json.dump(R, open(SP, 'w')); json.dump(T, open(TP, 'w'))
    print(f"{EVENT}: {added} teams added from Victory Road ({sum(1 for t in T if t['event'] == EVENT)} in all)")
