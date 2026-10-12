"""What sets people bring, for playing without open team sheets (2026-10-12, the user: a capable Bo1 bot that guesses items, natures and
moves the way it already guesses spreads). Every open team sheet in the cached Bo3 games (pssim/replays_protect, |showteam| lines) is
counted per species: whole sets (item, ability, nature, the four moves) and each part on its own. Packed names are kept as the sheets
write them (FocusSash, WeatherBall), so a guessed sheet can be written back in the same form.
  .venv/bin/python3 bot/set_prior.py      -> bot/out/set_prior.json"""
import os, re, json, glob, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
toid = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
def sheets(text):
    """(side, [(species, item, ability, nature, moves)]) for each |showteam| line of a log"""
    for l in text.split('\n'):
        if not l.startswith('|showteam|'): continue
        p = l.split('|', 3)
        if len(p) < 4: continue
        team = []
        for blob in p[3].split(']'):
            f = blob.split('|')
            if len(f) < 6: continue
            team.append((f[1] or f[0], f[2], f[3], f[5] or 'Serious', tuple(sorted(m for m in f[4].split(',') if m))))
        yield p[2], team
def build():
    full = collections.defaultdict(collections.Counter); part = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    names = {}; n_sheets = 0; seen = set()
    for f in glob.glob(os.path.join(ROOT, 'pssim', 'replays_protect', '*.log')):
        text = open(f, errors='replace').read()
        for side, team in sheets(text):
            key = tuple(sorted(team))
            # a player's sheet repeats across the games of a match: count each distinct (player side, sheet) once per match file
            if (os.path.basename(f), side) in seen: continue
            seen.add((os.path.basename(f), side)); n_sheets += 1
            for sp, item, ab, nat, moves in team:
                k = toid(sp); names[k] = sp
                full[k][(item, ab, nat, moves)] += 1
                part[k]['item'][item] += 1; part[k]['ability'][ab] += 1; part[k]['nature'][nat] += 1
                for m in moves: part[k]['move'][m] += 1
    out = {}
    for k, c in full.items():
        n = sum(c.values())
        out[k] = {'species': names[k], 'n': n, 'sets': [[v, list(s[:3]), list(s[3])] for s, v in c.most_common(60)],
                  'item': part[k]['item'].most_common(), 'ability': part[k]['ability'].most_common(), 'nature': part[k]['nature'].most_common(),
                  'move': part[k]['move'].most_common()}
    os.makedirs(os.path.join(ROOT, 'bot', 'out'), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, 'bot', 'out', 'set_prior.json'), 'w'))
    top = sorted(out.values(), key=lambda x: -x['n'])[:5]
    print(f"{n_sheets} sheets, {len(out)} species -> bot/out/set_prior.json; most seen:", ', '.join(f"{x['species']} {x['n']}" for x in top))
    for x in top[:3]:
        s = x['sets'][0]; print(f"  {x['species']}: commonest whole set {s[0]}/{x['n']} ({100 * s[0] / x['n']:.0f}%): {s[1]} {s[2]}")
if __name__ == '__main__':
    build()
