"""Fetch and parse the Reg M-C regional team lists (open team sheets) for the teams in regional_teams.json. Polite: 1 request / 0.6 s; resumes.
Each set: species, item, ability, nature ("Stat Alignment"), moves."""
import json, re, time, urllib.request, os, html
EV = {'Baltimore': '0037', 'Brisbane': '0038', 'Frankfurt': '0039'}
T = json.load(open('regional_teams.json')); out = json.load(open('regional_sets.json')) if os.path.exists('regional_sets.json') else {}
def get(u):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'champions-sims research (personal, low rate)'}), timeout=20) as r: return r.read().decode('utf-8', 'replace')
        except Exception: time.sleep(3 + 5 * k)
for n, t in enumerate(T):
    key = f"{t['event']}|{t['pid']}"
    if key in out or not t['pid']: continue
    s = get(f"https://standings.limitlessvgc.com/{EV[t['event']]}/player/{t['pid']}/teamlist"); time.sleep(0.6)
    if not s: continue
    sets = []
    for blk in re.findall(r'<a href="/00\d\d/pokemon/[^"]+">(.*?)</a></div>(.*?)</ul>', s, re.S):
        name, body = blk
        item = re.search(r'<div class="item">(.*?)</div>', body); abil = re.search(r'<div class="ability">Ability: (.*?)</div>', body)
        nat = re.search(r'Stat Alignment: (.*?)</div>', body); moves = re.findall(r'<li>(.*?)</li>', body)
        sets.append({'species': html.unescape(name), 'item': html.unescape(item.group(1)) if item else '', 'ability': html.unescape(abil.group(1)) if abil else '',
                     'nature': nat.group(1) if nat else '', 'moves': [html.unescape(m) for m in moves]})
    out[key] = sets
    if n % 25 == 0: json.dump(out, open('regional_sets.json', 'w')); print(time.strftime('%H:%M:%S'), n, len(out), flush=True)
json.dump(out, open('regional_sets.json', 'w')); print('done', len(out))
