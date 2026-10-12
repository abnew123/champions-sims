"""Add one more Reg M-C regional to regional_teams.json and regional_sets.json (user, 2026-10-12: Louisville).
Reads the standings page saved as standings_<id>.html (not in git: it has player names), keeps the top N rows (256, as for
Baltimore, Brisbane and Frankfurt), fetches each player's open team sheet (polite: 1 request / 0.6 s; resumes), and appends
{event, place, day2, pid, six, arch} entries: six in Showdown names (sets_lib.normalize), arch from pssim/pro_replays.arch.
  curl -s -A 'champions-sims research (personal, low rate)' https://standings.limitlessvgc.com/<id>/standings -o standings_<id>.html
  python3 fetch_event.py <Event> <id> [top N=256]
"""
import json, re, sys, os, time, html, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'teamsearch')); sys.path.insert(0, os.path.join(ROOT, 'pssim'))
import sets_lib as L
from pro_replays import arch
from cluster_opps import norm
EVENT, EID = sys.argv[1], sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 256
TP, SP = os.path.join(HERE, 'regional_teams.json'), os.path.join(HERE, 'regional_sets.json')

def get(u):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'champions-sims research (personal, low rate)'}), timeout=20) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception: time.sleep(3 + 5 * k)

def teamlist(pid):
    s = get(f"https://standings.limitlessvgc.com/{EID}/player/{pid}/teamlist"); time.sleep(0.6)
    if not s: return None
    sets = []
    for name, body in re.findall(r'<a href="/00\d\d/pokemon/[^"]+">(.*?)</a></div>(.*?)</ul>', s, re.S):
        item = re.search(r'<div class="item">(.*?)</div>', body); abil = re.search(r'<div class="ability">Ability: (.*?)</div>', body)
        nat = re.search(r'Stat Alignment: (.*?)</div>', body); moves = re.findall(r'<li>(.*?)</li>', body)
        sets.append({'species': html.unescape(name), 'item': html.unescape(item.group(1)) if item else '',
                     'ability': html.unescape(abil.group(1)) if abil else '', 'nature': nat.group(1) if nat else '',
                     'moves': [html.unescape(m) for m in moves]})
    return sets

if __name__ == '__main__':
    page = open(os.path.join(HERE, f'standings_{EID}.html')).read()
    rows = re.findall(rf'<tr class="([^"]*)"><td>(\d+)</td><td><a href="/{EID}/player/(\d+)"', page)
    T = json.load(open(TP)); R = json.load(open(SP))
    have = {(t['event'], t['pid']) for t in T}; added = 0
    for cls, place, pid in rows:
        place = int(place)
        if place > N or (EVENT, pid) in have: continue
        key = f"{EVENT}|{pid}"
        if key not in R:
            sets = teamlist(pid)
            if not sets or len(sets) != 6: print(f"place {place}: no full team sheet, skipped", flush=True); continue
            R[key] = sets
        six = [L.normalize(dict(s))['species'] for s in R[key]]
        T.append(dict(event=EVENT, place=place, day2='day2' in cls.split(), pid=pid, six=six, arch=arch([norm(x) for x in six])))
        added += 1
        if added % 25 == 0: json.dump(R, open(SP, 'w')); print(time.strftime('%I:%M %p'), added, flush=True)
    json.dump(R, open(SP, 'w')); json.dump(T, open(TP, 'w'), indent=None)
    print(f"{EVENT}: {added} teams added ({sum(1 for t in T if t['event'] == EVENT)} in all)")
