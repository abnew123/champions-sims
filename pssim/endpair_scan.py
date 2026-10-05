"""Which two Pokemon each team has on the field after the lead exchange (start of turns 3 and 4), by the team's archetype,
from public Showdown M-C Bo3 replays. Leads that pivot out (Parting Shot, U-turn, switches) and back-row Pokemon both show up.
usage: python3 endpair_scan.py <pages> <out.json>     (polite: ~4 requests/s; resumes)"""
import json, sys, time, os
from pro_replays import get, arch, base, FMT
def fields(log):
    six = {'p1': [], 'p2': []}; act = {}; snap = {}; turn = 0; brought = {'p1': set(), 'p2': set()}
    for l in log.split('\n'):
        p = l.split('|')
        if len(p) < 3: continue
        if p[1] == 'poke': six[p[2]].append(base(p[3]))
        elif p[1] in ('switch', 'drag', 'replace'): act[p[2][:3]] = base(p[3]); brought[p[2][:2]].add(base(p[3]))
        elif p[1] == 'faint': act[p[2][:3]] = None
        elif p[1] == 'turn':
            turn = int(p[2])
            if turn in (3, 4): snap[turn] = {s: sorted(v for k, v in act.items() if k.startswith(s) and v) for s in ('p1', 'p2')}
    return six, snap, brought, turn
def main():
    pages, outf = int(sys.argv[1]), sys.argv[2]
    st = json.load(open(outf)) if os.path.exists(outf) else {'scanned': [], 'rows': [], 'before': None}
    done = set(st['scanned'])
    for pg in range(pages):
        txt = get(f'https://replay.pokemonshowdown.com/search.json?format={FMT}' + (f"&before={st['before']}" if st['before'] else '')); time.sleep(0.25)
        if not txt: break
        res = json.loads(txt)
        if not res: break
        for r in res:
            st['before'] = r['uploadtime']
            if r['id'] in done: continue
            done.add(r['id']); st['scanned'].append(r['id'])
            log = get(f"https://replay.pokemonshowdown.com/{r['id']}.log"); time.sleep(0.25)
            if not log: continue
            six, snap, brought, last = fields(log)
            for s in ('p1', 'p2'):
                if len(six[s]) != 6: continue
                st['rows'].append({'arch': arch(six[s]), 'six': six[s], 'brought': sorted(brought[s]), 't3': snap.get(3, {}).get(s), 't4': snap.get(4, {}).get(s), 'turns': last})
        json.dump(st, open(outf, 'w'))
        print(f"page {pg + 1}: scanned {len(st['scanned'])}, team rows {len(st['rows'])}", flush=True)
if __name__ == '__main__': main()
