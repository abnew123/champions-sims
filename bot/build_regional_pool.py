"""The no-sheet arm's team pool (2026-10-11, the user: random teams from recent regionals, played with no sheet): the top 64 of each of
the latest regionals with open team sheets (teamsearch/regmatch/f192..f194.json), each six as the bot's team format, spreads by the
species' usual spread (regionals/smogon_mc_sets.json; the sheets show none), minus the two Frankfurt sixes the bot already plays with
sheets and any team with a species, item, ability or move the engine data lacks. Written to bot/out/regional_pool.json (git-ignored;
teams are named by event and placing only).
  .venv/bin/python3 bot/build_regional_pool.py [top=64]"""
import json, os, sys, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
top = int(sys.argv[1]) if len(sys.argv) > 1 else 64
D = json.load(open(os.path.join(ROOT, 'native', 'engine_data_full.json')))
toid = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
SPEC = {toid(s['name']): s['name'] for s in D['species'].values()}
ITEMS = {toid(x['name']) if isinstance(x, dict) and 'name' in x else toid(k): 1 for k, x in D['items'].items()}
ABIL = {toid(x['name']) if isinstance(x, dict) and 'name' in x else toid(k): 1 for k, x in D['abilities'].items()}
MOVES = {toid(m['name']): m['name'] for m in D['moves'].values()}
SM = json.load(open(os.path.join(ROOT, 'regionals', 'smogon_mc_sets.json')))
# the sheets' form names -> Showdown species (cosmetic Sinistcha forms are plain Sinistcha)
FORM = {'Indeedee [Female]': 'Indeedee-F', 'Indeedee [Male]': 'Indeedee', 'Arcanine [Hisuian Form]': 'Arcanine-Hisui', 'Floette [Eternal Flower]': 'Floette-Eternal',
        'Sinistcha [Masterpiece Form]': 'Sinistcha', 'Sinistcha [Unremarkable Form]': 'Sinistcha', 'Lycanroc [Dusk Form]': 'Lycanroc-Dusk', 'Lycanroc [Midnight Form]': 'Lycanroc-Midnight',
        'Basculegion [Male]': 'Basculegion', 'Basculegion [Female]': 'Basculegion-F', 'Maushold [Family of Three]': 'Maushold', 'Maushold [Family of Four]': 'Maushold-Four',
        'Meowstic [Female]': 'Meowstic-F', 'Meowstic [Male]': 'Meowstic', 'Ninetales [Alolan Form]': 'Ninetales-Alola', 'Tauros [Paldean Form]': 'Tauros-Paldea-Combat',
        'Slowking [Galarian Form]': 'Slowking-Galar', 'Zoroark [Hisuian Form]': 'Zoroark-Hisui', 'Typhlosion [Hisuian Form]': 'Typhlosion-Hisui', 'Goodra [Hisuian Form]': 'Goodra-Hisui',
        'Decidueye [Hisuian Form]': 'Decidueye-Hisui', 'Samurott [Hisuian Form]': 'Samurott-Hisui', 'Rotom [Wash Rotom]': 'Rotom-Wash', 'Rotom [Heat Rotom]': 'Rotom-Heat'}
def spread(sp, nature):
    s = SM.get(sp) or SM.get(sp.split('-')[0])
    if s and s.get('evs'): return s['evs']
    return [32, 32, 0, 0, 2, 0] if nature in ('Adamant', 'Jolly', 'Brave', 'Careful', 'Impish') else [32, 0, 0, 32, 2, 0]
sheets = []
for t in json.load(open(os.path.join(ROOT, 'bot', 'teams.json'))): sheets.append(sorted(x['species'] for x in t['sets']))
pool = []; skipped = {}
for ev in ('f192', 'f193', 'f194'):
    for p in json.load(open(os.path.join(ROOT, 'teamsearch', 'regmatch', ev + '.json'))):
        if not isinstance(p.get('placing'), int) or p['placing'] > top or len(p.get('decklist') or []) != 6: continue
        sets = []; why = None
        for m in p['decklist']:
            sp = FORM.get(m['name'], m['name'].split(' [')[0])
            if toid(sp) not in SPEC: why = 'species ' + sp; break
            sp = SPEC[toid(sp)]
            mv = [MOVES.get(toid(x)) for x in m.get('badges') or []]
            if None in mv or not mv: why = 'move in ' + sp; break
            if m.get('item') and toid(m['item']) not in ITEMS: why = 'item ' + m['item']; break
            if toid(m.get('ability')) not in ABIL: why = 'ability ' + str(m.get('ability')); break
            nat = m.get('stat_alignment') or 'Serious'
            sets.append({'species': sp, 'item': m.get('item') or '', 'ability': m['ability'], 'nature': nat, 'evs': spread(sp, nat), 'moves': mv})
        if why: skipped[why] = skipped.get(why, 0) + 1; continue
        if sorted(x['species'] for x in sets) in sheets: skipped['a sheet team'] = skipped.get('a sheet team', 0) + 1; continue
        pool.append({'name': f'{ev} #{p["placing"]}', 'sets': sets})
os.makedirs(os.path.join(ROOT, 'bot', 'out'), exist_ok=True)
json.dump(pool, open(os.path.join(ROOT, 'bot', 'out', 'regional_pool.json'), 'w'), indent=1)
print(f"{len(pool)} regional teams (top {top} of f192-f194) -> bot/out/regional_pool.json; skipped: {skipped}")
