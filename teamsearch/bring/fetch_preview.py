"""Team preview decisions from public Showdown M-C Bo3 replays: both sixes, the four each side brought, the two each side led,
winner, rating. Same 3,060 replays as pssim/endpairs.json (its 'scanned' list). Polite (~3 requests/s); resumes.
usage: python3 fetch_preview.py            -> previews.json
"""
import json, os, re, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'previews.json')
IDS = json.load(open(os.path.join(HERE, '..', '..', 'pssim', 'endpairs.json')))['scanned']
UA = {'User-Agent': 'champions-sims research (personal, low rate)'}

def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r: return r.read().decode()
        except Exception:
            time.sleep(2 + 3 * k)
    return None

def species(s): return s.split(',')[0].strip()                     # keeps the forme: "Indeedee-F", "Charizard-Mega-Y"
def parse(rep):
    log = rep['log']
    six = {'p1': [], 'p2': []}; lead = {'p1': [], 'p2': []}; brought = {'p1': [], 'p2': []}; mega = {'p1': None, 'p2': None}
    name = {}; win = None; turn = 0
    for l in log.split('\n'):
        p = l.split('|')
        if len(p) < 2: continue
        if p[1] == 'player' and len(p) > 3 and p[3]: name[p[2]] = p[3]
        elif p[1] == 'poke': six[p[2]].append(species(p[3]))
        elif p[1] in ('switch', 'drag', 'replace'):
            side = p[2][:2]; sp = re.sub(r'-Mega.*$', '', species(p[3]))
            if turn == 0 and len(lead[side]) < 2: lead[side].append(sp)
            if sp not in brought[side]: brought[side].append(sp)
        elif p[1] == 'detailschange' and '-Mega' in p[3]: mega[p[2][:2]] = species(p[3])
        elif p[1] == 'turn': turn = int(p[2])
        elif p[1] == 'win': win = p[2]
    sides = {}
    for s in ('p1', 'p2'):
        sides[s] = dict(name=name.get(s), six=six[s], lead=lead[s], brought=brought[s], mega=mega[s], won=(win == name.get(s)) if win else None)
    return dict(id=rep['id'], rating=rep.get('rating'), turns=turn, p1=sides['p1'], p2=sides['p2'])

if __name__ == '__main__':
    st = json.load(open(OUT)) if os.path.exists(OUT) else {'games': [], 'failed': []}
    done = {g['id'] for g in st['games']} | set(st['failed'])
    todo = [i for i in IDS if i not in done]
    print(time.strftime('%I:%M %p'), f'{len(todo)} of {len(IDS)} replays to fetch', flush=True)
    for n, rid in enumerate(todo):
        txt = get(f'https://replay.pokemonshowdown.com/{rid}.json'); time.sleep(0.25)
        try: st['games'].append(parse(json.loads(txt)))
        except Exception: st['failed'].append(rid)
        if (n + 1) % 100 == 0 or n + 1 == len(todo):
            json.dump(st, open(OUT, 'w')); print(time.strftime('%I:%M %p'), n + 1, 'fetched,', len(st['failed']), 'failed', flush=True)
    print('done', flush=True)
