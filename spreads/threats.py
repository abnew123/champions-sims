"""Threat list for the spread search, from Smogon's Reg M-C moveset stats (Sept 2026): the most-used Pokemon covering ~92% of
usage, each with its most common ability and item (Mega stones -> the Mega forme), damaging moves used by >= 25% of them, the attack
investment they'd run at most (32 SP, attack-boosting nature) and their most common listed spread for bulk.
usage: python3 threats.py > threats.json"""
import json, re, sys
D = json.load(open('../native/champions_data.json'))
toid = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
txt = open('../regionals/smogon_mc_2026-09_moveset.txt').read()
blocks = re.split(r'\+-+\+\n\| (\S[^|]*?)\s*\|\n\+-+\+\n', txt)
mons = []
for i in range(1, len(blocks), 2):
    name, body = blocks[i].strip(), blocks[i + 1]
    secs = {}
    for part in re.split(r'\+-+\+\n', body):
        lines = [l.strip('| ').strip() for l in part.strip().split('\n') if l.strip('| ').strip()]
        if lines: secs[lines[0].split(':')[0]] = lines
    raw = int(re.search(r'Raw count: (\d+)', body).group(1))
    pct = lambda sec: [(m.group(1), float(m.group(2))) for l in secs.get(sec, [])[1:] for m in [re.match(r'(.+?) ([\d.]+)%$', l)] if m and m.group(1) != 'Other']
    mons.append(dict(name=name, raw=raw, abilities=pct('Abilities'), items=pct('Items'), spreads=pct('Spreads'), moves=pct('Moves')))
mons.sort(key=lambda m: -m['raw']); tot = sum(m['raw'] for m in mons)
out = []; acc = 0
for m in mons:
    if acc / tot > 0.92: break
    acc += m['raw']
    sp = toid(m['name']); item = toid(m['items'][0][0]) if m['items'] else ''
    if sp not in D['species']: continue
    ab = toid(m['abilities'][0][0]) if m['abilities'] else ''
    ms = (D['items'].get(item) or {}).get('megaStone')
    if ms:
        mega = toid(ms.get(D['species'][sp]['name']) or list(ms.values())[0])
        if mega in D['species']: sp = mega; ab = toid(D['species'][mega]['abilities']['0'])
    st = D['species'][sp]['stats']
    nat, evs = m['spreads'][0][0].split(':') if m['spreads'] else ('Hardy', '0/0/0/0/0/0')
    evs = [int(x) for x in evs.split('/')]
    moves = [(toid(n), p / 100) for n, p in m['moves'] if p >= 25 and toid(n) in D['moves'] and D['moves'][toid(n)]['category'] != 'Status']
    # attack investment: 32 SP in each attacking stat, nature boosting the stat its moves use most
    phys = sum(p for n, p in moves if D['moves'][n]['category'] == 'Physical'); spec = sum(p for n, p in moves if D['moves'][n]['category'] == 'Special')
    weather = {'drought': 'sunnyday', 'drizzle': 'raindance', 'sandstream': 'sandstorm', 'snowwarning': 'snowscape', 'megasol': 'sunnyday'}.get(ab, '')
    terrain = {'grassysurge': 'grassyterrain', 'psychicsurge': 'psychicterrain', 'electricsurge': 'electricterrain', 'mistysurge': 'mistyterrain'}.get(ab, '')
    out.append(dict(name=m['name'], species=sp, item=item, ability=ab, weight=m['raw'] / tot, moves=moves, weather=weather, terrain=terrain,
                    atk_nature=nat, atk_sp=[0, 32 if phys else 0, 0, 32 if spec else 0, 0, 0],
                    bulk_nature=nat, bulk_sp=evs))
json.dump(out, sys.stdout, indent=0)
print(f'{len(out)} threats, {100 * acc / tot:.0f}% of usage', file=sys.stderr)
