"""Find public Showdown M-C Bo3 replays of teams built on our core (Mega Blastoise + Torkoal + a Trick Room setter)
and record what they lead, bring, and click on turn one, by opposing archetype (the sheet's tab guide).
usage: python3 pro_replays.py <pages> <out.json>      (polite: ~1 request per 0.4 s; resumes from out.json)
"""
import json, sys, time, urllib.request, re, os
FMT = 'gen9championsvgc2026regmcbo3'
UA = {'User-Agent': 'champions-sims research (personal, low rate)'}
def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r: return r.read().decode()
        except Exception as e:
            time.sleep(2 + 3 * k)
    return None
CORE = {'Blastoise', 'Torkoal'}; SETTERS = {'Indeedee-F', 'Farigiraf', 'Hatterene'}
def arch(six):
    s = set(six); has = lambda *xs: any(x in s for x in xs)
    if has('Gengar'): return 'Perish'
    if has('Charizard') and has('Pelipper', 'Politoed'): return 'Rain + Sun'
    if has('Charizard', 'Torkoal'): return 'Sun'
    if has('Pelipper', 'Politoed'): return 'Rain'
    if has('Tyranitar'): return 'Sand'
    if has('Froslass', 'Ninetales-Alola', 'Vanilluxe'): return 'Snow'
    if has('Indeedee-F', 'Indeedee'): return 'Indeedee TR'
    if has('Farigiraf', 'Sinistcha'): return 'Trick Room'
    if has('Salamence', 'Whimsicott', 'Talonflame', 'Staraptor'): return 'Tailwind'
    return 'Balance'
def base(sp): return re.sub(r'-(Mega.*|\*)$', '', sp.split(',')[0].strip())
def parse(log):
    six = {'p1': [], 'p2': []}; name = {}; lead = {'p1': {}, 'p2': {}}; seen = {'p1': [], 'p2': []}; t1 = {'p1': {}, 'p2': {}}; turn = 0; win = None
    nick = {}
    for l in log.split('\n'):
        p = l.split('|')
        if len(p) < 2: continue
        if p[1] == 'player' and len(p) > 3 and p[3]: name[p[2]] = p[3]
        elif p[1] == 'poke': six[p[2]].append(base(p[3]))
        elif p[1] in ('switch', 'drag'):
            side = p[2][:2]; sp = base(p[3]); nick[p[2][:2] + p[2][3:].split(':')[0] + ':' + p[2].split(': ', 1)[1]] = sp
            if sp not in seen[side]: seen[side].append(sp)
            if turn == 0: lead[side][p[2][:3]] = sp
        elif p[1] == 'turn': turn = int(p[2])
        elif p[1] == 'move' and turn == 1:
            side = p[2][:2]; who = p[2].split(': ', 1)[1]
            sp = next((v for k, v in nick.items() if k.startswith(side) and k.endswith(':' + who)), who)
            tgt = p[4].split(': ', 1)[1] if len(p) > 4 and ': ' in p[4] else ''
            t1[side].setdefault(sp, p[3] + (f' -> {tgt}' if tgt and not p[4].startswith(side) else ''))
        elif p[1] == 'win': win = p[2]
    return six, name, lead, seen, t1, win

def main():
    pages, outf = int(sys.argv[1]), sys.argv[2]
    st = json.load(open(outf)) if os.path.exists(outf) else {'scanned': [], 'games': [], 'before': None}
    done = set(st['scanned'])
    for pg in range(pages):
        url = f'https://replay.pokemonshowdown.com/search.json?format={FMT}' + (f"&before={st['before']}" if st['before'] else '')
        txt = get(url); time.sleep(0.25)
        if not txt: break
        res = json.loads(txt)
        if not res: break
        for r in res:
            st['before'] = r['uploadtime']
            if r['id'] in done: continue
            done.add(r['id']); st['scanned'].append(r['id'])
            log = get(f"https://replay.pokemonshowdown.com/{r['id']}.log"); time.sleep(0.25)
            if not log: continue
            six, name, lead, seen, t1, win = parse(log)
            for side, foe in (('p1', 'p2'), ('p2', 'p1')):
                s = set(six[side])
                if not (CORE <= s and s & SETTERS): continue
                st['games'].append({'id': r['id'], 'rating': r.get('rating'), 'player': name.get(side), 'opp': name.get(foe), 'won': win == name.get(side),
                                    'six': six[side], 'oppSix': six[foe], 'arch': arch(six[foe]),
                                    'lead': [lead[side].get(side + 'a'), lead[side].get(side + 'b')], 'brought': seen[side],
                                    'oppLead': [lead[foe].get(foe + 'a'), lead[foe].get(foe + 'b')], 't1': t1[side]})
        json.dump(st, open(outf, 'w'))
        print(f"page {pg + 1}: scanned {len(st['scanned'])}, core games {len(st['games'])}, back to {time.strftime('%m-%d %H:%M', time.localtime(st['before']))}", flush=True)
if __name__ == '__main__': main()
