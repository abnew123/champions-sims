"""Official Pokémon Champions broadcasts -> the battle log the eval bar's live mode reads (Showdown's protocol), from the video alone:
the open team sheets the broadcast shows, the HP boxes of the four Pokémon on the field (percentages), the battle text and the decision
screen ("Trainers are choosing actions"). For watching on your own computer.
  python3 evalbar/broadcast.py frames <video file or YouTube URL> <dir> [start] [end]   frames at 2 per second (yt-dlp for a URL;
                                                                                         start / end like 1:44:09)
  python3 evalbar/broadcast.py ocr <dir>                                                 Apple Vision text of every frame -> <dir>.ocr.jsonl
  python3 evalbar/broadcast.py scan <YouTube URL> <out.ocr.jsonl> [workers=2] [fetchers=4] a whole recording, 20 minutes at a time: frames, text,
                                                                                         frames deleted; resumes where it stopped
  python3 evalbar/broadcast.py read <dir.ocr.jsonl> <out.log>                            the whole match -> battle log
  python3 evalbar/broadcast.py replay <dir.ocr.jsonl> [speed=4] [threads=2] [port=8768] [YouTube id] [start]
                                                                                         a recorded match through the live page, as if live
  python3 evalbar/broadcast.py watch <YouTube URL or id> [start] [threads=2] [port=8768] a broadcast in real time (live, or a recording from
                                                                                         start, e.g. 1:44:09): page at http://localhost:<port>
Player 1 is the player on the left: the battle text speaks from their side (their Pokémon are named plainly, the other player's are
"the opposing ..."). No names are kept: the log calls the players Player 1 and Player 2, and sheets are matched to sides by species."""
import os, re, sys, json, time, difflib, subprocess, threading, collections
import common as C, replay as R, procs as P
toid = R.toid
E = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_full.json')))
OCR = os.path.join(C.MAIN, 'recordings', 'ocr')
NAMES = {k: {E[k][i]['name'].upper(): E[k][i]['name'] for i in E[k] if E[k][i].get('name')} for k in ('species', 'moves', 'items', 'abilities')}
NATURES = {'ADAMANT', 'MODEST', 'TIMID', 'JOLLY', 'BOLD', 'CALM', 'IMPISH', 'CAREFUL', 'BRAVE', 'QUIET', 'RELAXED', 'SASSY', 'HASTY', 'NAIVE',
           'LONELY', 'MILD', 'RASH', 'GENTLE', 'LAX', 'NAUGHTY', 'HARDY', 'DOCILE', 'SERIOUS', 'BASHFUL', 'QUIRKY'}
STAT = {'Attack': 'atk', 'Defense': 'def', 'Sp. Atk': 'spa', 'Sp. Def': 'spd', 'Speed': 'spe', 'accuracy': 'accuracy', 'evasiveness': 'evasion'}
def fuzzy(text, kind, pool=None, cut=0.8):
    """the closest dex name to an OCR'd string (pool: names to prefer)"""
    t = text.upper().replace('0', 'O').strip(' .,!*~•')
    for names in ([{n.upper(): n for n in pool}] if pool else []) + [NAMES[kind]]:
        if t in names: return names[t]
        m = difflib.get_close_matches(t, list(names), 1, cut)
        if m: return names[m[0]]
    return None
def frames(src, out, start=None, end=None):
    os.makedirs(out, exist_ok=True)
    if src.startswith('http'):
        url = subprocess.run(['yt-dlp', '-g', '-f', 'bv*[height<=720]', src], capture_output=True, text=True, check=True).stdout.split()[0]
    else: url = src
    cmd = [P.exe('ffmpeg'), '-v', 'error', '-y'] + (['-ss', start] if start else []) + (['-to', end] if end else []) + ['-i', url, '-vf', 'fps=2,scale=1280:-2', '-q:v', '3', os.path.join(out, 'f_%05d.jpg')]
    subprocess.run(['nice', '-n', '10'] + cmd, check=True)
def media(url):
    """yt-dlp's media URL for the 720p video, with the request headers YouTube wants and the duration"""
    info = json.loads(subprocess.run(['yt-dlp', '-j', '--no-warnings', '-f', 'bv*[height<=720][protocol^=http]/bv*[height<=720]/b[height<=720]', url],
                                     capture_output=True, text=True, check=True).stdout)
    return info['url'], ''.join(f'{k}: {v}\r\n' for k, v in (info.get('http_headers') or {}).items()), info.get('duration')
def scan(url, outf, workers=2, chunk=1200, fetchers=4):
    """a whole recording through Apple Vision without keeping the video. YouTube serves one connection at about twice real time, so
    `fetchers` ffmpeg processes each cut a different 20-minute piece to 2 frames a second while `workers` OCR processes read the finished
    pieces in order; each piece's text is appended to outf (frames numbered from the start of the video) and its frames deleted.
    Resumes after the last piece read."""
    import concurrent.futures as cf
    src, hdr, dur = media(url); tmp = outf + '.frames'; os.makedirs(tmp, exist_ok=True); lock = threading.Lock(); cur = {'src': src, 'hdr': hdr}
    done = 0
    if os.path.exists(outf):
        for l in open(outf): done = max(done, int(json.loads(l)['file'][2:8]))
    json.dump({'title': 'Reading the regional broadcast (OCR)', 'out': os.path.relpath(outf, os.path.join(C.HERE, 'out')), 'total': int(dur * 2),
               'done0': done, 'started': time.time(), 'threads': workers + 1, 'seeds': 0, 'staged': False, 'unit': 'frames', 'proc': 'broadcast.py scan'},
              open(outf + '.run.json', 'w'))
    def fetch(t0):
        d = os.path.join(tmp, f'c{t0:06d}'); os.makedirs(d, exist_ok=True)
        for f in os.listdir(d): os.remove(os.path.join(d, f))
        for attempt in range(4):
            r = subprocess.run(['nice', '-n', '10', P.exe('ffmpeg'), '-v', 'error', '-y', '-threads', '1', '-headers', cur['hdr'], '-ss', str(t0), '-t', str(chunk), '-i', cur['src'],
                                '-vf', 'fps=2,scale=1280:-2', '-q:v', '3', '-start_number', str(t0 * 2 + 1), os.path.join(d, 'f_%06d.jpg')], capture_output=True, text=True)
            if r.returncode == 0: return d
            with lock: cur['src'], cur['hdr'], _ = media(url)                  # the media URL expired: fetch a new one
        return d
    starts = list(range(done // 2 // chunk * chunk, int(dur), chunk))
    with cf.ThreadPoolExecutor(fetchers) as ex:
        futs = [ex.submit(fetch, t0) for t0 in starts[:fetchers]]; nxt = fetchers
        for i, t0 in enumerate(starts):
            d = futs[i].result()
            if nxt < len(starts): futs.append(ex.submit(fetch, starts[nxt])); nxt += 1
            frames_ = sorted(f for f in os.listdir(d) if f.endswith('.jpg') and int(f[2:8]) > done)
            parts = [os.path.join(d, f'w{k}') for k in range(workers)]
            for k, p in enumerate(parts):
                os.makedirs(p, exist_ok=True)
                for f in frames_[k::workers]: os.replace(os.path.join(d, f), os.path.join(p, f))
            procs = [subprocess.Popen(['nice', '-n', '10', P.exe('ocr', OCR), p], stdout=subprocess.PIPE, text=True) for p in parts]
            rows = [json.loads(l) for pr in procs for l in pr.communicate()[0].splitlines()]
            with open(outf, 'a') as f:
                for row in sorted(rows, key=lambda x: x['file']): f.write(json.dumps(row) + '\n')
            subprocess.run(['rm', '-rf', d])
            if frames_: done = int(frames_[-1][2:8])
            print(f'{time.strftime("%H:%M")} read {t0 // 60}-{(t0 + chunk) // 60} min of {int(dur) // 60}', flush=True)
    subprocess.run(['rm', '-rf', tmp])
def ocr(d):
    with open(d.rstrip('/') + '.ocr.jsonl', 'w') as f: subprocess.run(['nice', '-n', '10', P.exe('ocr', OCR), d], stdout=f, check=True)
# --------------------------------------------------------------------------------------------------------------------------- sheets
def sheet(lines):
    """one team-sheet screen -> [set, ...]: each panel starts with the species name in capitals"""
    L = [(t.strip(), x, y) for t, x, y, w, h in lines]
    other = lambda t: any(t.upper().replace('0', 'O') in NAMES[k] for k in ('abilities', 'moves', 'items'))   # DRIZZLE is not Drizzile
    anchors = [(fuzzy(t, 'species', cut=0.85), x, y) for t, x, y in L if t.isupper() and len(t) > 3 and not other(t)]
    anchors = [a for a in anchors if a[0]]
    out = []
    for sp, x0, y0 in anchors:
        near = [(t, x, y) for t, x, y in L if -0.02 < x - x0 < 0.2 and 0.02 < y - y0 < 0.26]
        ability = next((fuzzy(t, 'abilities') for t, x, y in sorted(near, key=lambda r: r[2]) if abs(x - x0) < 0.02 and y - y0 < 0.08 and fuzzy(t, 'abilities')), '')
        nature = next((t.title() for t, x, y in near if t.upper() in NATURES), '')
        moves = [fuzzy(t, 'moves') for t, x, y in sorted(near, key=lambda r: r[2]) if 0 <= x - x0 < 0.03 and y - y0 > 0.07 and fuzzy(t, 'moves')]
        item = next((fuzzy(t, 'items') for t, x, y in near if x - x0 > 0.1 and y - y0 > 0.15 and fuzzy(t, 'items')), '')
        if sp == 'Indeedee' and ('Follow Me' in moves or 'Trick Room' in moves): sp = 'Indeedee-F'   # the sheet shows only the name
        if item and E['items'].get(toid(item), {}).get('megaStone'):            # the species that holds this stone (Floette -> Floette-Eternal)
            sp = next(iter(E['items'][toid(item)]['megaStone']), sp)
        out.append({'species': sp, 'item': item, 'ability': ability, 'nature': nature, 'moves': moves[:4]})
    return out
# --------------------------------------------------------------------------------------------------------------------------- battle
BOXES = (('p1', 'a', 0.0, 0.16), ('p1', 'b', 0.16, 0.42), ('p2', 'a', 0.58, 0.81), ('p2', 'b', 0.81, 1.0))
def battle(lines):
    """one battle frame -> (HP boxes {(side, slot): (name, pct)}, decision screen?, turn number or None, battle text or None)"""
    names = [(t.strip(), x) for t, x, y, w, h in lines if 0.86 < y < 0.91]
    pcts = [(int(re.sub(r'\D', '', t)), x) for t, x, y, w, h in lines if 0.91 < y < 0.96 and re.fullmatch(r'\d{1,3} ?%', t.strip())]
    boxes = {}
    for sd, sl, lo, hi in BOXES:
        n = next((t for t, x in names if lo <= x < hi), None); p = next((v for v, x in pcts if lo <= x < hi), None)
        if n and p is not None: boxes[(sd, sl)] = (n, min(100, p))
    mid = [t.strip() for t, x, y, w, h in lines if 0.70 < y < 0.86 and 0.2 < x + w / 2 < 0.8]   # the text box sits at two heights
    decision = any('choosing actions' in t for t in mid)
    text = next((t for t in mid if len(t) > 8 and (t.endswith('!') or t.endswith('!l') or t.endswith('...')) and 'Trainer' != t), None)
    turn = next((int(m.group(1)) for t, x, y, w, h in lines for m in [re.fullmatch(r'Turn (\d+)', t.strip())] if m and x > 0.8 and y < 0.12), None)
    return boxes, decision, turn, text
def letters(t): return re.sub(r'[^A-Z]', '', t.upper())
def scoreboard(lines):
    """the players' names on the scoreboard (left, right), as letters only: used in memory to match the team sheets to sides"""
    top = [(t, x) for t, x, y, w, h in lines if 0.08 < y < 0.13 and sum(c.isalpha() for c in t) >= 6 and t.upper() == t]
    left = max((letters(t) for t, x in top if x < 0.45), key=len, default=''); right = max((letters(t) for t, x in top if x > 0.55), key=len, default='')
    return (left, right) if left and right else None
def sheet_owner(lines):
    """the name in a team sheet's header (letters only)"""
    top = [t for t, x, y, w, h in lines if y < 0.09 and t.upper() == t and sum(c.isalpha() for c in t) >= 6 and not fuzzy(t, 'species', cut=0.85)]
    return max((letters(t) for t in top), key=len, default='')
class Reader:
    """frames in time order -> battle log lines. feed() one frame's OCR at a time; lines() is the log so far."""
    def __init__(s):
        s.games = []; s.meta = []; s.sheets = {}; s.raw_sheets = []; s.frame = 0; s.names = collections.deque(maxlen=600); s.note = ''
        s.board = None; s.match = 0; s.game_in_match = 0; s.prev_end = 0; s.owners = {}; s.t0 = 0; s.new_game()
    def new_game(s):
        s.out = []; s.games.append(s.out); s.meta.append({}); s.started = False; s.turn = 0; s.in_decision = False; s.ended = False
        s.active = {}; s.hp = {}; s.last_text = None; s.slot_free = {'p1': [], 'p2': []}; s.megas = {'p1': False, 'p2': False}
        s.fainted = {'p1': set(), 'p2': set()}; s.lead_seen = False; s.pending = []; s.pairs = {'p1': -999, 'p2': -999}; s.game_names = collections.Counter(); s.sides_checked = False
    def team(s, sd): return s.sheets.get(sd, [])
    def species(s, sd, name):
        """an OCR'd Pokémon name on side sd -> the species on that side's sheet (Mega names map back to the base)"""
        name = re.sub(r'^Mega ', '', name.strip()); pool = {}
        for st in s.team(sd):
            disp = st['species'].split('-')[0]; pool[disp.upper()] = st['species']; pool[st['species'].upper()] = st['species']
        t = name.upper()
        if t in pool: return pool[t]
        m = difflib.get_close_matches(t, list(pool), 1, 0.7)
        return pool[m[0]] if m else fuzzy(name, 'species', cut=0.75)
    def ident(s, sd, sp):
        sl = next((sl for (x, sl), v in s.active.items() if x == sd and v == sp), None)
        return f"{sd}{sl or 'a'}: {sp.split('-')[0] if sp != 'Floette-Eternal' else 'Floette'}"
    def emit(s, *lines): s.out.extend(lines)
    def header(s, boxes):
        s.emit('|gametype|doubles', '|player|p1|Player 1|', '|player|p2|Player 2|', '|tier|[Gen 9 Champions] VGC Reg M-C (broadcast)')
        for sd in ('p1', 'p2'):
            for st in s.team(sd): s.emit(f"|poke|{sd}|{st['species']}, L50|")
        for sd in ('p1', 'p2'):
            blob = ']'.join(f"{st['species']}||{st['item'].replace(' ', '')}|{st['ability'].replace(' ', '')}|{','.join(m.replace(' ', '') for m in st['moves'])}|{st['nature']}||||||50|" for st in s.team(sd))
            if blob: s.emit(f'|showteam|{sd}|{blob}')
        s.emit('|teampreview|4', '|start')
        for (sd, sl), (n, p) in sorted(boxes.items()):
            sp = s.species(sd, n); s.active[(sd, sl)] = sp; s.hp[(sd, sl)] = p
            s.emit(f"|switch|{sd}{sl}: {s.nick(sp)}|{sp}, L50|{p}/100")
        s.started = True
    def nick(s, sp): return 'Floette' if sp == 'Floette-Eternal' else sp.split('-Mega')[0]
    def who(s, text):
        """'The opposing X ...' -> ('p2', species, rest); 'X ...' -> ('p1', ...)"""
        sd = 'p2' if text.startswith('The opposing ') else 'p1'
        body = text[len('The opposing '):] if sd == 'p2' else text
        best = None
        for st in s.team(sd):
            for nm in {s.nick(st['species']), 'Mega ' + s.nick(st['species'])}:
                if body.startswith(nm) and (not best or len(nm) > len(best[1])): best = (st['species'], nm)
        if not best:
            m = re.match(r"([A-Z][\w.'-]*(?: [A-Z][\w.'-]*)?)", body)
            if not m: return sd, None, body
            sp = s.species(sd, m.group(1)); return sd, sp, body[len(m.group(1)):]
        return sd, best[0], body[len(best[1]):]
    def slot_of(s, sd, sp):
        return next((sl for (x, sl), v in s.active.items() if x == sd and v == sp), None)
    def mon(s, sd, sp):
        sl = s.slot_of(sd, sp) or 'a'; return f"{sd}{sl}: {s.nick(sp)}"
    def message(s, text):
        text = re.sub(r'!+[^!]*$', '!', text.strip())
        if re.search(r"won the battle|forfeit|\blost!$|You won", text, re.I) and 'lost some' not in text:
            if not s.ended:
                left = {sd: 4 - len(s.fainted[sd]) for sd in ('p1', 'p2')}
                win = 'p1' if left['p2'] == 0 or ('forfeit' not in text and left['p1'] > left['p2']) else 'p2' if left['p1'] == 0 or left['p2'] > left['p1'] else None
                if win: s.emit('|', f"|win|Player {win[1]}")
                s.ended = True; s.prev_end = s.frame; s.meta[-1]['end'] = s.now()
                if s.game_names: s.board = s.game_names.most_common(1)[0][0]      # who played this game, for telling the next one apart
            return
        # field-wide
        FIELD = [(r'twisted the dimensions', '|-fieldstart|move: Trick Room'), (r'dimensions returned to normal', '|-fieldend|move: Trick Room'),
                 (r'sunlight turned harsh', '|-weather|SunnyDay'), (r'started to rain', '|-weather|RainDance'), (r'sandstorm kicked up', '|-weather|Sandstorm'),
                 (r'started to snow', '|-weather|Snowscape'), (r'(sunlight faded|rain stopped|sandstorm subsided|snow stopped)', '|-weather|none'),
                 (r'battlefield got weird', '|-fieldstart|move: Psychic Terrain'), (r'Grass grew to cover', '|-fieldstart|move: Grassy Terrain'),
                 (r'electric current ran', '|-fieldstart|move: Electric Terrain'), (r'Mist swirled', '|-fieldstart|move: Misty Terrain'),
                 (r'weirdness disappeared', '|-fieldend|move: Psychic Terrain'), (r'grass disappeared', '|-fieldend|move: Grassy Terrain'),
                 (r'electricity disappeared', '|-fieldend|move: Electric Terrain'), (r'mist disappeared', '|-fieldend|move: Misty Terrain')]
        for pat, line in FIELD:
            if re.search(pat, text, re.I): s.emit(line); return
        m = re.search(r'tailwind (started blowing|blew).* (your|the opposing) (side|team)', text, re.I)
        if m: s.emit(f"|-sidestart|{'p1' if m.group(2).lower() == 'your' else 'p2'}: Player|move: Tailwind"); return
        m = re.search(r"(your|the opposing) (team|side)'s tailwind petered out", text, re.I)
        if m: s.emit(f"|-sideend|{'p1' if m.group(1).lower() == 'your' else 'p2'}: Player|move: Tailwind"); return
        m = re.search(r'(Reflect|Light Screen|Aurora Veil) made (your|the opposing) (team|side)', text)
        if m: s.emit(f"|-sidestart|{'p1' if m.group(2) == 'your' else 'p2'}: Player|{'move: ' if m.group(1) != 'Reflect' else ''}{m.group(1)}"); return
        m = re.search(r'Go! (.+?)!$', text) or re.search(r'sent out (.+?)!$', text)
        if m:
            if ' and ' in m.group(1): s.pairs['p1' if text.startswith('Go!') else 'p2'] = s.frame
            elif s.started: s.send('p1' if text.startswith('Go!') else 'p2', m.group(1))
            return
        # about one Pokémon (or two: "A and the opposing B's Attack fell!")
        m = re.match(r"(.+?) and ((?:the opposing )?[^,']+?)'s (.+?) (fell|rose|harshly fell|severely fell|rose sharply|rose drastically)!", text)
        if m:                                                               # Intimidate on two: "A and the opposing B's Attack fell!"
            for who in (m.group(1), m.group(2)): s.about(re.sub(r'^the opposing ', 'The opposing ', who) + "'s " + m.group(3) + ' ' + m.group(4) + '!')
            return
        s.about(text)
    def about(s, text):
        sd, sp, rest = s.who(text)
        if not sp: return
        me = s.mon(sd, sp); rest = rest.strip()
        mv = re.match(r'used (.+?)!$', rest)
        if mv:
            st = next((x for x in s.team(sd) if x['species'] == sp), None)
            move = fuzzy(mv.group(1), 'moves', st['moves'] if st else None) or mv.group(1)
            s.emit(f'|move|{me}|{move}|'); return
        if re.match(r'protected itself', rest): s.emit(f'|-singleturn|{me}|Protect'); return
        if re.match(r'fainted', rest):
            s.emit(f'|faint|{me}'); sl = s.slot_of(sd, sp); s.fainted[sd].add(sp)
            if sl: s.slot_free[sd].append(sl); s.hp[(sd, sl)] = 0
            return
        if re.match(r'has Mega Evolved', rest):
            mg = next(iter(E['species'].get(toid(sp), {}).get('otherFormes') or []), None)
            st = next((x for x in s.team(sd) if x['species'] == sp), {})
            mega = (E['items'].get(toid(st.get('item', '')), {}).get('megaStone') or {}).get(sp) or (sp + '-Mega')
            s.emit(f'|detailschange|{me}|{mega}, L50', f"|-mega|{me}|{sp}|{st.get('item', '')}"); s.megas[sd] = True; return
        if re.match(r'(went back to|, come back)', rest) or rest.startswith(', come back'):
            sl = s.slot_of(sd, sp)
            if sl: s.slot_free[sd].append(sl); s.active.pop((sd, sl), None)
            return
        bm = re.match(r"'s (.+?) (fell|rose|harshly fell|severely fell|rose sharply|rose drastically)", rest)
        if bm:
            n = 2 if ('harshly' in bm.group(2) or 'sharply' in bm.group(2)) else 3 if ('severely' in bm.group(2) or 'drastically' in bm.group(2)) else 1
            for stat in re.split(r', and |, | and ', bm.group(1)):
                if stat.strip() in STAT: s.emit(f"|{'-boost' if 'rose' in bm.group(2) else '-unboost'}|{me}|{STAT[stat.strip()]}|{n}")
            return
        for pat, st in ((r'was burned', 'brn'), (r'is paralyzed', 'par'), (r'fell asleep', 'slp'), (r'was badly poisoned', 'tox'), (r'was poisoned', 'psn'), (r'was frozen', 'frz')):
            if re.match(pat, rest): s.emit(f'|-status|{me}|{st}'); return
        if re.match(r'woke up', rest): s.emit(f'|-curestatus|{me}|slp'); return
        im = re.search(r'using its (.+?)!$', rest) or re.search(r'(ate its .+?)!$', rest)
        if im:
            item = fuzzy(re.sub(r'^ate its ', '', im.group(1)), 'items')
            if item and item not in ('Leftovers', 'Shell Bell') and 'Mega' not in rest: s.emit(f'|-enditem|{me}|{item}')
    def send(s, sd, name):
        sp = s.species(sd, re.sub(r' the [A-Z][\w-]*(?: [A-Z][\w-]*)*$', '', name.strip()))     # "Primarina the Rank Master": a title
        if not sp: return
        free = s.slot_free[sd]; sl = free.pop(0) if free else next((x for x in 'ab' if (sd, x) not in s.active), None)
        if sl is None:                                                      # who went back was not shown: the HP boxes will tell which slot
            s.pending.append((sd, sp, len(s.out))); return
        s.active[(sd, sl)] = sp
        s.emit(f"|switch|{sd}{sl}: {s.nick(sp)}|{sp}, L50|{s.hp.get(('mon', sd, sp), 100)}/100")
    def place(s, boxes):
        """a send-out whose slot was unknown: put the switch where the battle text had it, in the slot the HP boxes now show it in"""
        keep = []
        for i, (sd, sp, at) in enumerate(s.pending):
            sl = next((x for (y, x), (n, p) in boxes.items() if y == sd and s.species(sd, n) == sp and s.active.get((sd, x)) != sp), None)
            if not sl: keep.append((sd, sp, at)); continue
            s.active[(sd, sl)] = sp
            s.out.insert(at, f"|switch|{sd}{sl}: {s.nick(sp)}|{sp}, L50|{s.hp.get(('mon', sd, sp), 100)}/100")
            s.pending[i + 1:] = [(a, b, c + 1 if c >= at else c) for a, b, c in s.pending[i + 1:]]; keep = [(a, b, c + 1 if c >= at else c) for a, b, c in keep]
        s.pending = keep
    def reconcile(s, boxes):
        """at a decision screen: the Pokémon on the field and their HP as the HP boxes show them"""
        s.pending = []
        for (sd, sl), (n, p) in sorted(boxes.items()):
            sp = s.species(sd, n)
            if not sp: continue
            if s.active.get((sd, sl)) != sp:                                  # a switch the battle text did not show
                s.active[(sd, sl)] = sp; s.emit(f"|switch|{sd}{sl}: {s.nick(sp)}|{sp}, L50|{p}/100"); s.hp[(sd, sl)] = p; continue
            if s.hp.get((sd, sl)) != p:
                s.emit(f"|{'-damage' if p < (s.hp.get((sd, sl)) or 100) else '-heal'}|{sd}{sl}: {s.nick(sp)}|{p}/100"); s.hp[(sd, sl)] = p
            s.hp[('mon', sd, sp)] = p
        for sd in ('p1', 'p2'): s.slot_free[sd] = []
    def close(s):
        """end the current game without having seen its last message: the result from who has Pokémon left, when that is clear"""
        left = {sd: 4 - len(s.fainted[sd]) for sd in ('p1', 'p2')}
        win = 'p1' if left['p2'] <= 0 < left['p1'] else 'p2' if left['p1'] <= 0 < left['p2'] else None
        if win: s.emit('|', f'|win|Player {win[1]}')
        s.ended = True; s.prev_end = s.frame - 1; s.meta[-1]['end'] = s.now()
        if s.game_names: s.board = s.game_names.most_common(1)[0][0]
    def now(s): return s.t0 + (s.frame - 1) / 2                         # the video time of the current frame, in seconds
    def mark(s): s.meta[-1].setdefault('times', {})[s.turn] = s.now()
    def feed(s, lines):
        L = [l for l in lines]; s.frame += 1
        NAT = sum(1 for l in L if l[0].strip().upper() in NATURES)
        if NAT >= 3:
            if s.started and not s.ended: s.close()
            sets = sheet(L)
            if len(sets) >= 4: s.raw_sheets.append((s.frame, sheet_owner(L), sets))
            return
        sb = scoreboard(L)
        if sb:
            s.names.append((s.frame, sb))
            if s.started and not s.ended:
                s.game_names[sb] += 1
                if not s.sides_checked and sum(s.game_names.values()) >= 10:  # the players' names during this game: sheets on the right sides?
                    s.board = s.game_names.most_common(1)[0][0]; s.check_sides(); s.sides_checked = True
        boxes, decision, turn, text = battle(L)
        if s.ended and decision and len(boxes) >= 3: s.new_game()                       # the next game of the set
        if len(boxes) < 2 and not text: s.in_decision = False if not decision else s.in_decision; return
        if not s.started:
            if text and re.search(r'^Go! .+ and .+!$|sent out .+ and .+!$', text): s.lead_seen = True
            fresh = s.lead_seen or turn == 1 or (len(boxes) == 4 and all(p == 100 for n, p in boxes.values()))
            if decision and len(boxes) >= 3 and fresh:
                recent = [n for fr, n in s.names if fr > s.frame - 240]              # scoreboard reads in the last two minutes
                board = collections.Counter(recent).most_common(1)[0][0] if recent else None
                fresh_sheets = sum(1 for fr, o, st in s.raw_sheets if fr > s.prev_end) >= 2
                if board and s.board: other = not all(difflib.SequenceMatcher(None, a, b).ratio() > 0.7 for a, b in zip(board, s.board))
                else: other = fresh_sheets                                        # no names to go by: new sheets mean a new match
                new_match = not s.match or other
                if new_match: s.sheets = {}                                       # new players: a new match, new sheets
                if len(s.sheets) < 2: s.owners = {}; s.assign_sheets(boxes, board)
                if len(s.sheets) < 2: s.note = 'waiting for both team sheets: start before the broadcast shows them'; return
                if new_match: s.match += 1; s.game_in_match = 0
                s.board = s.board if s.board and not other else None; s.game_in_match += 1; s.meta[-1] = {'match': s.match, 'game': s.game_in_match, 'frame': s.frame}
                s.note = ''; s.header(boxes); s.turn = turn or 1; s.emit(f'|turn|{s.turn}'); s.in_decision = True; s.mark()
            elif decision and len(boxes) >= 3 and not s.note: s.note = 'joined mid-game: the bar starts with the next game'
            return
        if s.ended: return
        if s.pending and len(boxes) >= 2: s.place(boxes)
        if decision and not s.in_decision and s.turn >= 2 and len(boxes) == 4 and all(p == 100 for n, p in boxes.values()) \
                and max(s.pairs.values()) > s.frame - 120:                       # new leads sent out in the last minute, everyone at full HP
            s.close(); s.prev_end = s.frame - 120
            s.new_game(); s.lead_seen = True; s.frame -= 1; return s.feed(lines)   # this frame again, as the new game's first decision
        if decision and not s.in_decision:
            s.reconcile(boxes); s.turn = max(s.turn + 1, turn or 0); s.emit('|upkeep', '|', f'|turn|{s.turn}'); s.mark()   # upkeep: durations count down
        s.in_decision = decision
        if text and not decision:
            if s.last_text and difflib.SequenceMatcher(None, text, s.last_text).ratio() > 0.85: return
            s.last_text = text; s.message(text)
    def assign_sheets(s, boxes, board=None):
        """the team sheets shown before the battle -> sides. Sheet screens come in runs, one player's sheet per run; each run's reads are
        merged (the fullest read of each Pokémon). A run goes to the side whose scoreboard name matches its header; failing that, to the
        side whose Pokémon on the field it has."""
        runs = []
        sim = lambda a, b: difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0
        for fr, owner, sets in s.raw_sheets:
            # only sheets shown since the last game ended and in the 20 minutes before this game: others belong to other matches
            if fr <= s.prev_end or fr < s.frame - 20 * 120: continue
            sig = frozenset(x['species'].split('-')[0] for x in sets)
            same = runs and fr - runs[-1]['end'] <= 6 and (sim(owner, runs[-1]['owners'].most_common(1)[0][0]) > 0.6 or len(sig & runs[-1]['sig']) >= 4)
            if same: runs[-1]['reads'].append(sets); runs[-1]['owners'][owner] += 1; runs[-1]['end'] = fr; runs[-1]['sig'] |= sig
            else: runs.append({'end': fr, 'reads': [sets], 'owners': collections.Counter([owner]), 'sig': set(sig)})
        full = lambda st: len(st['moves']) + bool(st['item']) + bool(st['ability']) + bool(st['nature'])
        teams = []
        for run in runs:
            by = {}
            for sets in run['reads']:
                for st in sets:
                    key = st['species'].split('-')[0]                            # Floette and Floette-Eternal are one entry
                    if key not in by or full(st) > full(by[key]): by[key] = st
            teams.append((run['owners'].most_common(1)[0][0], [st for st in by.values() if full(st) >= 3][:6], run['end']))
        on = {sd: {s.species_any(n) for (x, sl), (n, p) in boxes.items() if x == sd} for sd in ('p1', 'p2')}
        # one sheet per player: the latest read of each owner (or of each team, when the header was not read)
        latest = {}
        for owner, team, end in teams:
            if len(team) < 4: continue
            k = next((o for o in latest if sim(o, owner) > 0.6), None) or owner or frozenset(st['species'] for st in team)
            latest[k] = (owner, team, end)
        for owner, team, end in sorted(latest.values(), key=lambda x: -x[2])[:2]:
            if len(s.sheets) == 2: continue
            if board and max(sim(owner, board[0]), sim(owner, board[1])) > 0.6: sd = 'p1' if sim(owner, board[0]) >= sim(owner, board[1]) else 'p2'
            else:
                names = {st['species'].split('-')[0] for st in team}
                sd = max(('p1', 'p2'), key=lambda k: sum(1 for n in on[k] if n and n.split('-')[0] in names))
            if sd in s.sheets: sd = 'p1' if sd == 'p2' else 'p2'
            s.sheets[sd] = team; s.owners[sd] = owner
    def check_sides(s):
        """once the scoreboard names are known: if the sheets were given to the wrong sides (by species, before the names showed), swap
        them and rewrite the log's team lines"""
        sim = lambda a, b: difflib.SequenceMatcher(None, a or '', b or '').ratio()
        o = s.owners
        if not s.board or 'p1' not in o or 'p2' not in o: return
        if sim(o['p1'], s.board[1]) + sim(o['p2'], s.board[0]) > sim(o['p1'], s.board[0]) + sim(o['p2'], s.board[1]) + 0.3:
            s.sheets = {'p1': s.sheets['p2'], 'p2': s.sheets['p1']}; s.owners = {'p1': o['p2'], 'p2': o['p1']}
            sw = lambda l: l.replace('|p1|', '|P1|').replace('|p2|', '|p1|').replace('|P1|', '|p2|')
            s.out[:] = [sw(l) if l.startswith(('|poke|', '|showteam|')) else l for l in s.out]
    def species_any(s, n): return fuzzy(re.sub(r'^Mega ', '', n), 'species', cut=0.75)
    def lines(s): return s.out
    def logs(s): return [g for g in s.games if any(l.startswith('|turn|') for l in g)]
    def logs_meta(s): return [(g, m) for g, m in zip(s.games, s.meta) if any(l.startswith('|turn|') for l in g)]
class Runner:
    """the reader's games through the live mode, one live.Live per game, served together on one page"""
    def __init__(s, tag, threads, port, video=None, t0=0):
        """video: {'id': YouTube id, 'start': seconds, 'live': bool} to embed the player on the page; t0: the video time of the first frame"""
        import live as LV
        s.LV = LV; s.tag = tag; s.threads = threads; s.port = port; s.reader = Reader(); s.reader.t0 = t0; s.lives = []; s.written = []; s.video = video
        os.makedirs(LV.OUT, exist_ok=True); s.serve()
    def serve(s):
        import http.server
        run = s
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                p = self.path.split('?')[0]
                if p == '/data.json':
                    games = []
                    for i, lv in enumerate(run.lives):
                        if lv.data and lv.data['games']:
                            lm = run.reader.logs_meta(); m = lm[i][1] if i < len(lm) else {}
                            g = {**lv.data['games'][0], 'title': f'Game {i + 1}', 'end': m.get('end')}
                            g['steps'] = [{**st, 'vt': (m.get('times') or {}).get(st['turn'])} for st in g['steps']]
                            games.append(g)
                    st = run.reader.note or (run.lives[-1].status if run.lives else 'waiting for the first turn')
                    b = json.dumps({'games': games, 'video': run.video, 'live': {'url': 'data.json', 'status': st, 'format': 'Champions broadcast, open team sheets'}}).encode(); ct = 'application/json'
                elif p in ('/', '/index.html'):
                    html = open(os.path.join(C.HERE, 'page.html')).read().replace('<title>Eval Bar</title>', '<title>Champions Eval Bar</title>', 1)
                    html = html.replace('/*DATA*/null', json.dumps({'games': [], 'video': run.video, 'live': {'url': 'data.json', 'status': 'starting'}}))
                    b = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                         '<style>body{margin:0}</style></head><body>' + html + '</body></html>').encode(); ct = 'text/html; charset=utf-8'
                else: self.send_error(404); return
                self.send_response(200); self.send_header('Content-Type', ct); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)
            def log_message(self, *a): pass
        threading.Thread(target=http.server.ThreadingHTTPServer(('127.0.0.1', s.port), H).serve_forever, daemon=True).start()
        print(f'eval bar at http://localhost:{s.port}  (for watching on your own computer)', flush=True)
    def feed(s, lines):
        s.reader.feed(lines)
        for i, g in enumerate(s.reader.logs()):
            f = os.path.join(s.LV.OUT, f'{s.tag}_g{i + 1}.log')
            if i >= len(s.written): s.written.append(0)
            if len(g) != s.written[i]:
                open(f, 'w').write('\n'.join(g) + '\n'); s.written[i] = len(g)
            if i >= len(s.lives):
                lv = s.LV.Live(None, s.threads, 0, logfile=f, tag=f'{s.tag}_g{i + 1}', fmt='Champions broadcast, open team sheets'); s.lives.append(lv)
                threading.Thread(target=lv.run, daemon=True).start()
def secs(x): return sum(int(v) * 60 ** i for i, v in enumerate(reversed(x.split(':')))) if x else 0
def replay(ocrf, speed=4.0, threads=2, port=8768, vid=None, start=None):
    """vid, start: the YouTube video and the time its first frame was taken from, to embed the player"""
    rows = sorted(map(json.loads, open(ocrf)), key=lambda x: x['file'])
    run = Runner(os.path.basename(ocrf).split('.')[0], threads, port, video={'id': vid, 'start': secs(start), 'live': False} if vid else None, t0=secs(start))
    t0 = time.time()
    for k, row in enumerate(rows):
        wait = t0 + k / 2 / speed - time.time()
        if wait > 0: time.sleep(wait)
        run.feed(row['lines'])
    print('end of the recording; the page stays up until you stop this (Ctrl-C)', flush=True)
    while True: time.sleep(60)
def watch(url, threads=2, port=8768, start=None):
    """a YouTube broadcast in real time (live, or a recording from `start`, e.g. 1:44:09): ffmpeg writes 2 frames a second, Apple
    Vision reads them in small batches, the reader follows"""
    tag = 'live_' + re.sub(r'\W', '', url.split('v=')[-1])[:16]; d = os.path.join(C.HERE, 'out', 'live', tag + '_frames'); os.makedirs(d, exist_ok=True)
    # the media URL from yt-dlp, opened by ffmpeg with the same request headers, in real time (-re). YouTube sometimes refuses a media
    # URL (403): then fetch a new one and carry on from where the frames got to
    def open_stream(at):
        src, hdr, _ = media(url)
        return subprocess.Popen(['nice', '-n', '10', P.exe('ffmpeg'), '-v', 'error', '-y', '-headers', hdr, '-re'] + (['-ss', str(at)] if at else []) + ['-i', src,
                                 '-vf', 'fps=2,scale=1280:-2', '-q:v', '3', '-start_number', str(int((at - secs(start)) * 2) + 1), os.path.join(d, 'f_%06d.jpg')],
                                stderr=subprocess.PIPE, text=True)
    ff = open_stream(secs(start)); retries = 0
    vid = re.search(r'(?:v=|youtu\.be/|/live/)([\w-]{11})', url)
    run = Runner(tag, threads, port, video={'id': vid.group(1), 'start': secs(start), 'live': not start} if vid else None, t0=secs(start)); done = 0
    while True:
        files = sorted(f for f in os.listdir(d) if f.endswith('.jpg'))[:-1]          # the newest frame may still be being written
        new = [f for f in files if int(f[2:8]) > done]
        if new:
            b = os.path.join(d, 'batch'); os.makedirs(b, exist_ok=True)
            for f in new: os.replace(os.path.join(d, f), os.path.join(b, f))
            out = subprocess.run([P.exe('ocr', OCR), b], capture_output=True, text=True).stdout
            for row in sorted(map(json.loads, out.splitlines()), key=lambda x: x['file']): run.feed(row['lines'])
            for f in new: os.remove(os.path.join(b, f))
            done = int(new[-1][2:8])
        elif ff.poll() is not None:
            err = ff.stderr.read()
            if ('403' in err or 'Forbidden' in err or ff.returncode) and retries < 8:
                retries += 1; time.sleep(3); ff = open_stream(secs(start) + done / 2); continue
            print('the stream ended', flush=True); break
        time.sleep(1)
    while True: time.sleep(60)
def read(ocrf):
    r = Reader()
    for row in sorted(map(json.loads, open(ocrf)), key=lambda x: x['file']): r.feed(row['lines'])
    return r
def youtube(x):
    """a YouTube link, or just its video id (no quotes needed in zsh, which reads the '?' of a link as a wildcard)"""
    return x if x.startswith('http') or os.path.exists(x) else f'https://www.youtube.com/watch?v={x}'
if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] in ('watch', 'scan', 'frames') and len(a) > 1: a[1] = youtube(a[1])
    if a[0] == 'frames': frames(a[1], a[2], *(a[3:5]))
    elif a[0] == 'ocr': ocr(a[1])
    elif a[0] == 'scan': scan(a[1], a[2], int(a[3]) if len(a) > 3 else 2, fetchers=int(a[4]) if len(a) > 4 else 4)
    elif a[0] in ('replay', 'watch'):
        args = a[2:]
        try:
            if a[0] == 'replay': replay(a[1], float(args[0]) if args else 4.0, int(args[1]) if len(args) > 1 else 2, int(args[2]) if len(args) > 2 else 8768,
                                        args[3] if len(args) > 3 else None, args[4] if len(args) > 4 else None)
            else:
                st = next((x for x in args if ':' in x), None); nums = [x for x in args if ':' not in x]
                watch(a[1], int(nums[0]) if nums else 2, int(nums[1]) if len(nums) > 1 else 8768, st)
        except KeyboardInterrupt: pass
    elif a[0] == 'read':
        r = read(a[1]); base = a[2][:-4] if a[2].endswith('.log') else a[2]
        for i, (g, m) in enumerate(r.logs_meta()):
            f = f"{base}_m{m['match']}g{m['game']}.log"; open(f, 'w').write('\n'.join(g) + '\n')
            print(f"match {m['match']} game {m['game']} (at {m['frame'] / 120:.0f} min): {sum(l.startswith('|turn|') for l in g)} turns, {next((l for l in g if l.startswith('|win|')), 'no result')} -> {f}")
        print('sheets: ' + '; '.join(f"{sd}: {', '.join(st['species'] for st in r.sheets.get(sd, []))}" for sd in ('p1', 'p2')))
