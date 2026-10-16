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
                                                                                         start, e.g. 1:44:09): page at http://localhost:<port>; every
                                                                                         frame's text is kept in out/live/live_<id>.ocr.jsonl
  python3 evalbar/broadcast.py follow <YouTube URL or id> [at=h:mm:ss] [threads=2] [port=8768] [src=<saved fragment URL .json>]
                                                                                         a live stream through its 5-second fragments, from the
                                                                                         live edge or from `at` into the stream
  python3 evalbar/broadcast.py serve <YouTube URL or id> [threads=2] [port=8768]         a stream read earlier, on the page, fetching nothing
  (evalbar/auto.py runs follow / serve / scan by itself for the Play Pokémon channel's VGC streams)
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
REGION = {'HISUIAN': 'Hisui', 'ALOLAN': 'Alola', 'GALARIAN': 'Galar', 'PALDEAN': 'Paldea'}
def sheet_species(t):
    """a species name as a team sheet prints it -> the species: 'INDEEDEE (FEMALE)' -> Indeedee-F, 'HISUIAN ARCANINE' -> Arcanine-Hisui,
    'FLOETTE (ETERNAL FLOWER)' -> Floette-Eternal (a form in brackets: its first word)"""
    m = re.match(r'^(.*?)\s*\(\s*([A-Za-z ]+?)\s*\)?\s*$', t.strip()); paren = m.group(2).upper() if m else ''; t = m.group(1) if m else t
    g = paren if paren in ('FEMALE', 'MALE') else None; shape = paren.split()[0].title() if paren and not g else None
    w = t.split(None, 1); reg = REGION.get(w[0].upper().replace('0', 'O')) if len(w) == 2 else None
    base = fuzzy(w[1] if reg else t, 'species', cut=0.85)
    if not base: return None
    form = base + '-' + reg if reg else base + '-F' if g == 'FEMALE' else base + '-' + shape if shape else None
    return E['species'][toid(form)].get('name', form) if form and toid(form) in E['species'] else base
def sheet(lines):
    """one team-sheet screen -> [set, ...]: each panel starts with the species name in capitals"""
    L = [(t.strip(), x, y) for t, x, y, w, h in lines]
    other = lambda t: any(t.upper().replace('0', 'O') in NAMES[k] for k in ('abilities', 'moves', 'items'))   # DRIZZLE is not Drizzile
    anchors = [(sheet_species(t), x, y) for t, x, y in L if t.isupper() and len(t) > 3 and not other(t)]
    anchors = [a for a in anchors if a[0]]
    out = []
    for sp, x0, y0 in anchors:
        near = [(t, x, y) for t, x, y in L if -0.02 < x - x0 < 0.2 and 0.02 < y - y0 < 0.26]
        ability = next((fuzzy(t, 'abilities') for t, x, y in sorted(near, key=lambda r: r[2]) if abs(x - x0) < 0.02 and y - y0 < 0.08 and fuzzy(t, 'abilities')), '')
        nature = next((n.title() for t, x, y in near for n in NATURES if t.upper().startswith(n)), '')   # "JollyAspeed": text run together
        moves = [fuzzy(t, 'moves') for t, x, y in sorted(near, key=lambda r: r[2]) if 0 <= x - x0 < 0.03 and y - y0 > 0.07 and fuzzy(t, 'moves')]
        item = next((fuzzy(t, 'items') for t, x, y in near if x - x0 > 0.1 and y - y0 > 0.15 and fuzzy(t, 'items')), '')
        if sp == 'Indeedee' and ('Follow Me' in moves or 'Trick Room' in moves): sp = 'Indeedee-F'   # the sheet shows only the name
        if item and E['items'].get(toid(item), {}).get('megaStone'):            # the species that holds this stone (Floette -> Floette-Eternal)
            sp = next(iter(E['items'][toid(item)]['megaStone']), sp)
        out.append({'species': sp, 'item': item, 'ability': ability, 'nature': nature, 'moves': moves[:4]})
    return out
# --------------------------------------------------------------------------------------------------------------------------- battle
SINGLE = {'normal', 'any', 'adjacentFoe', 'adjacentAlly', 'adjacentAllyOrSelf'}   # move targets the player picks
PIVOT = {'Baton Pass', 'U-turn', 'Volt Switch', 'Flip Turn', 'Parting Shot', 'Teleport', 'Chilly Reception', 'Shed Tail', 'Roar', 'Whirlwind',
         'Dragon Tail', 'Circle Throw'}                                     # moves after which a Pokemon comes in without a faint
BOXES = (('p1', 'a', 0.0, 0.16), ('p1', 'b', 0.16, 0.42), ('p2', 'a', 0.58, 0.81), ('p2', 'b', 0.81, 1.0))
# the battle messages that end with a full stop (the others end with "!" or "..."); other text in that part of the screen is the overlay's
PERIOD = re.compile(r"(rain stopped|sunlight faded|sandstorm subsided|snow stopped|disappeared from the battlefield|weirdness disappeared|"
                    r"electricity disappeared|mist disappeared|returned to normal|ended due to a forfeit)\.$")
# what can happen as the leads come in, before turn 1: Intimidate and other stat changes, weather and terrain starting
PRE = re.compile(r"('s .+ (fell|rose)|started to rain|sunlight turned harsh|sandstorm kicked up|started to snow|battlefield got weird|Grass grew|"
                 r"electric current ran|Mist swirled)", re.I)
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
    text = next((t for t in mid if len(t) > 8 and (t.endswith('!') or t.endswith('!l') or t.endswith('...') or PERIOD.search(t)) and 'Trainer' != t), None)
    turn = next((int(m.group(1)) for t, x, y, w, h in lines for m in [re.fullmatch(r'Turn (\d+)', t.strip())] if m and x > 0.8 and y < 0.12), None)
    return boxes, decision, turn, text
def letters(t): return re.sub(r'[^A-Z]', '', t.upper())
def scoreboard(lines):
    """the players' names on the scoreboard (left, right), as letters only: used in memory to match the team sheets to sides"""
    top = [(t, x) for t, x, y, w, h in lines if 0.08 < y < 0.13 and sum(c.isalpha() for c in t) >= 6 and t.upper() == t]
    left = max((letters(t) for t, x in top if x < 0.45), key=len, default=''); right = max((letters(t) for t, x in top if x > 0.55), key=len, default='')
    return (left, right) if left and right else None
def scoreboard_names(lines):
    """the players' names as the scoreboard shows them (left, right), without country and record ("CARSON CONFER (US 5/0/0"): for the live
    page only. They are kept in memory, never written to a file"""
    top = [(t.strip(), x, y) for t, x, y, w, h in lines if 0.08 < y < 0.13 and sum(c.isalpha() for c in t) >= 4 and t.upper() == t]
    clean = lambda t: re.sub(r'^[\d/ ]+[A-Z]{2}\s+', '', re.sub(r'\s*\(?\s*\b[A-Z]{2}\b[\s\d/()-]*$', '', t)).strip().title()   # "4/0/0 CA DORIAN KANG" too
    out = {}
    for sd in ('p1', 'p2'):
        mine = [(t, x, y) for t, x, y in top if (x < 0.45 if sd == 'p1' else x > 0.55)]
        if not mine: out[sd] = ''; continue
        main = max(mine, key=lambda r: len(r[0]))
        parts = sorted((r for r in mine if abs(r[1] - main[1]) < 0.04), key=lambda r: r[2])   # a name on two stacked lines: MATTHEW / WOODRUFF
        out[sd] = ' '.join(clean(t) for t, x, y in parts) if sum(c.isalpha() for c in main[0]) >= 6 or len(parts) > 1 else ''
    return out
def sheet_owner(lines):
    """the name in a team sheet's header (letters only)"""
    top = [t for t, x, y, w, h in lines if y < 0.09 and t.upper() == t and sum(c.isalpha() for c in t) >= 6 and not fuzzy(t, 'species', cut=0.85)]
    return max((letters(t) for t in top), key=len, default='')
class Reader:
    """frames in time order -> battle log lines. feed() one frame's OCR at a time; lines() is the log so far."""
    def __init__(s):
        s.games = []; s.meta = []; s.sheets = {}; s.raw_sheets = []; s.frame = 0; s.names = collections.deque(maxlen=600); s.note = ''
        s.board = None; s.match = 0; s.game_in_match = 0; s.prev_end = 0; s.owners = {}; s.t0 = 0; s.pre = []; s.pre_on = False; s.pre_frame = 0; s.p2_label = ''
        s.run = []; s.gap = 0; s.at_msg = None; s.seen = {'p1': [], 'p2': []}; s.new_game()   # run: the message on screen, kept across games
    def new_game(s):
        s.out = []; s.games.append(s.out); s.meta.append({}); s.started = False; s.turn = 0; s.in_decision = False; s.ended = False
        s.active = {}; s.hp = {}; s.last_text = None; s.slot_free = {'p1': [], 'p2': []}; s.megas = {'p1': False, 'p2': False}
        s.fainted = {'p1': set(), 'p2': set()}; s.open = None; s.cur = {}; s.changed = {}; s.foreign = 0; s.timed = {}; s.sent = []; s.forfeit = False; s.closed = False; s.poked = {'p1': set(), 'p2': set()}; s.lead_seen = False; s.pending = []; s.pairs = {'p1': -999, 'p2': -999}; s.game_names = collections.Counter(); s.sides_checked = False; s.settle = []
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
        if not s.closed:                                                         # a lead the sheet as read lacks joins it first
            for (sd, sl), (n, p) in sorted(boxes.items()): s.note_seen(sd, s.species(sd, n))
        for sd in ('p1', 'p2'):
            for st in s.team(sd): s.emit(f"|poke|{sd}|{st['species']}, L50|")
            if s.closed:                                                         # no sheets: the Pokemon this match has shown so far, and the leads
                for sp in s.seen[sd] + [s.species(x, n) for (x, sl), (n, p) in sorted(boxes.items()) if x == sd]:
                    if sp and sp not in s.poked[sd]: s.poked[sd].add(sp); s.emit(f'|poke|{sd}|{sp}, L50|')
        for sd in ('p1', 'p2'):
            if s.team(sd): s.emit(s.sheet_line(sd))
        s.emit('|teampreview|4', '|start')
        for (sd, sl), (n, p) in sorted(boxes.items()):
            sp = s.species(sd, n); s.active[(sd, sl)] = sp; s.hp[(sd, sl)] = p; s.note_seen(sd, sp)
            s.emit(f"|switch|{sd}{sl}: {s.nick(sp)}|{sp}, L50|{p}/100")
        s.started = True
    def note_seen(s, sd, sp):
        """a Pokemon this match has shown; without sheets, one not in this game's preview yet is added to it (returned as log lines); with
        sheets, one the sheet as read lacks (a panel misread) is added to the sheet with its most common set"""
        if sp and sp not in s.seen[sd]: s.seen[sd].append(sp)
        if s.closed and sp and sp not in s.poked[sd]: s.poked[sd].add(sp); return [f'|poke|{sd}|{sp}, L50|']
        if not s.closed and sp and s.team(sd) and sp not in {x['species'] for x in s.team(sd)} and len(s.team(sd)) < 6:
            import recorded as RC
            try: cs = RC.common_set(sp)
            except Exception: cs = None
            if cs:
                s.sheets[sd].append({k: cs[k] for k in ('species', 'item', 'ability', 'nature', 'moves')})
                if s.started: return [f'|poke|{sd}|{sp}, L50|', s.sheet_line(sd)]
        return []
    def sheet_line(s, sd):
        return f"|showteam|{sd}|" + ']'.join(f"{st['species']}||{st['item'].replace(' ', '')}|{st['ability'].replace(' ', '')}|{','.join(m.replace(' ', '') for m in st['moves'])}|{st['nature']}||||||50|" for st in s.team(sd))
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
        if s.open and re.search(r'(hurt by|buffeted by|pelted by|restored (a little )?HP|regained health|is hurt|was hurt)', text): s.shut()   # end-of-turn damage and healing
        if re.search(r"won the battle|forfeit|\b(lost|won)!$|You won", text, re.I) and 'lost some' not in text:
            if not s.ended:
                if 'forfeit' in text: s.forfeit = True; return                  # who forfeited: the "... lost!" message that follows says
                left = {sd: 4 - len(s.fainted[sd]) for sd in ('p1', 'p2')}
                win = 'p1' if left['p1'] > left['p2'] else 'p2' if left['p2'] > left['p1'] else None
                m = re.match(r"'?(.+?) (lost|won)!$", text)
                if m and s.p2_label:                                             # "<Player 2's name> lost!": Player 2 lost; any other name: Player 1
                    side = 'p2' if difflib.SequenceMatcher(None, m.group(1).lower(), s.p2_label.lower()).ratio() > 0.75 else 'p1'
                    win = side if m.group(2) == 'won' else ('p1' if side == 'p2' else 'p2')
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
            if re.search(pat, text, re.I): s.field(line); return
        m = re.search(r'tailwind (started blowing|blew).* (your|the opposing) (side|team)', text, re.I)
        if m: s.emit(f"|-sidestart|{'p1' if m.group(2).lower() == 'your' else 'p2'}: Player|move: Tailwind"); return
        m = re.search(r"(your|the opposing) (team|side)'s tailwind petered out", text, re.I)
        if m: s.emit(f"|-sideend|{'p1' if m.group(1).lower() == 'your' else 'p2'}: Player|move: Tailwind"); return
        m = re.search(r'(Reflect|Light Screen|Aurora Veil) made (your|the opposing) (team|side)', text)
        if m: s.emit(f"|-sidestart|{'p1' if m.group(2) == 'your' else 'p2'}: Player|{'move: ' if m.group(1) != 'Reflect' else ''}{m.group(1)}"); return
        m = re.match(r'.+? withdrew (.+?)!$', text)                         # "<trainer> withdrew X!": the slot it leaves is the next send-out's
        if m:
            for sd in ('p2', 'p1'):
                sp = s.species(sd, m.group(1)); sl = s.slot_of(sd, sp) if sp else None
                if sl: s.shut(); s.slot_free[sd].append(sl); s.active.pop((sd, sl), None); break
            return
        lab = re.match(r'(.+?) (?:sent out|withdrew) ', text)
        if lab and not text.startswith('Go!'): s.p2_label = lab.group(1).strip()          # "The Trainer", or the player's name: Player 2's messages
        m = re.search(r'Go! (.+?)!$', text) or re.search(r'sent out (.+?)!$', text)
        if m:
            if ' and ' in m.group(1): s.pairs['p1' if text.startswith('Go!') else 'p2'] = s.frame
            elif s.started: s.send('p1' if text.startswith('Go!') else 'p2', m.group(1))
            return
        m = re.match(r"It doesn't affect (.+?)(?:\.\.\.|!)$", text)
        if m:
            sd, sp, _ = s.who(m.group(1)[0].upper() + m.group(1)[1:])
            if sp and s.open: s.hit((sd, s.slot_of(sd, sp)), "text: it doesn't affect")
            if sp: s.emit(f'|-immune|{s.mon(sd, sp)}')
            return
        # facts about the last move, for the rules' version of the state (evalbar/rules.py)
        m = re.match(r"(?:It's super effective|A critical hit) on (.+?)!$", text)
        if m:
            sd, sp, _ = s.who(m.group(1)[0].upper() + m.group(1)[1:])
            if sp: s.emit(f"|{'-supereffective' if text.startswith('It') else '-crit'}|{s.mon(sd, sp)}")
            return
        user, target = s.last_move()
        if text.startswith(("It's super effective", 'A critical hit')):
            if target: s.emit(f"|{'-supereffective' if text.startswith('It') else '-crit'}|{target}")
            return
        m = re.match(r'The Pok.mon was hit (\d+) times?!', text)
        if m:
            if target: s.emit(f'|-hitcount|{target}|{m.group(1)}')
            return
        if text.startswith('But it failed'):
            if user: s.emit(f'|-fail|{user}')
            return
        # about one Pokémon (or two: "A and the opposing B's Attack fell!")
        m = re.match(r"(.+?) and ((?:the opposing )?[^,']+?)'s (.+?) (harshly fell|severely fell|rose sharply|rose drastically|fell|rose)!", text)
        if m:                                                               # Intimidate on two: "A and the opposing B's Attack fell!"
            for who in (m.group(1), m.group(2)): s.about(re.sub(r'^the opposing ', 'The opposing ', who) + "'s " + m.group(3) + ' ' + m.group(4) + '!')
            return
        s.about(text)
    def about(s, text):
        sd, sp, rest = s.who(text)
        if not sp: return
        if s.team(sd) and sp not in {x['species'] for x in s.team(sd)} and sp not in [v for (x, sl), v in s.active.items() if x == sd]:   # on no sheet and not on the field: other footage
            s.foreign += 1
            if s.foreign >= 2: s.close()
            return
        me = s.mon(sd, sp); rest = rest.strip()
        k = (sd, s.slot_of(sd, sp))
        if re.match(r'is protected by the Psychic Terrain', rest):                # a priority move it blocked: a fact for the rules
            s.emit(f'|-activate|{me}|move: Psychic Terrain'); return
        if re.match(r'avoided the attack', rest):
            u, _ = s.last_move()
            if u: s.emit(f'|-miss|{u}|{me}')
        if s.open and k[1] and k != s.open['user'] and not rest.startswith('used ') and (
                s.open['status'] or re.match(r'(protected itself|avoided the attack|fainted)', rest)): s.hit(k, 'text: ' + rest)
        mv = re.match(r'used (.+?)!$', rest)
        if mv:
            st = next((x for x in s.team(sd) if x['species'] == sp), None)
            move = fuzzy(mv.group(1), 'moves', st['moves'] if st else None) or mv.group(1)
            s.emit(f'|move|{me}|{move}|'); s.aim(sd, sp, move); return
        if re.match(r'protected itself', rest): s.emit(f'|-singleturn|{me}|Protect'); return
        if re.match(r'fainted', rest):
            if sp in s.fainted[sd]: return                                     # already down: a replay of an earlier moment
            if s.open and k == s.open['user']: s.shut()
            s.emit(f'|faint|{me}'); sl = s.slot_of(sd, sp); s.fainted[sd].add(sp)
            if sl: s.slot_free[sd].append(sl); s.hp[(sd, sl)] = 0
            if len(s.fainted[sd]) >= 4:                                        # all four brought are down: the game is over
                s.emit('|', f"|win|Player {'2' if sd == 'p1' else '1'}"); s.ended = True; s.prev_end = s.frame; s.meta[-1]['end'] = s.now()
                if s.game_names: s.board = s.game_names.most_common(1)[0][0]
            return
        if re.match(r'has Mega Evolved', rest):
            mg = next(iter(E['species'].get(toid(sp), {}).get('otherFormes') or []), None)
            st = next((x for x in s.team(sd) if x['species'] == sp), {})
            mega = (E['items'].get(toid(st.get('item', '')), {}).get('megaStone') or {}).get(sp) or (sp + '-Mega')
            s.emit(f'|detailschange|{me}|{mega}, L50', f"|-mega|{me}|{sp}|{st.get('item', '')}"); s.megas[sd] = True; return
        if re.match(r'(went back to|, come back)', rest) or rest.startswith(', come back'):
            s.shut()
            sl = s.slot_of(sd, sp)
            if sl: s.slot_free[sd].append(sl); s.active.pop((sd, sl), None)
            return
        cap = re.match(r"'s (.+?) won't go any (higher|lower)", rest)
        if cap and cap.group(1).strip() in STAT:                                # the stat is at +6 or -6
            s.emit(f"|-setboost|{me}|{STAT[cap.group(1).strip()]}|{6 if cap.group(2) == 'higher' else -6}"); return
        bm = re.match(r"'s (.+?) (harshly fell|severely fell|rose sharply|rose drastically|fell|rose)", rest)
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
    # A move's target is not in the battle text, but the HP boxes show it: mid-turn the broadcast pops up the box of the Pokemon that is
    # hit, alone, so the box that drops after "X used Y!" and before the next Pokemon acts is the target. Text that names the target counts too ("protected itself", "avoided the attack", "It doesn't affect", a faint, and for
    # a status move the first thing said about another Pokemon). With one possible target, that one. Spread moves need no target.
    def aim(s, sd, sp, move):
        s.shut(); sl = s.slot_of(sd, sp); mv = E['moves'].get(toid(move), {})
        if not sl or mv.get('target') not in SINGLE: return
        foes = [k for k in s.active if k[0] != sd and s.active[k] not in s.fainted[k[0]]]
        ally = [k for k in s.active if k[0] == sd and k[1] != sl and s.active[k] not in s.fainted[sd]]
        only = ally if mv['target'] in ('adjacentAlly', 'adjacentAllyOrSelf') else foes if mv['target'] == 'adjacentFoe' or not ally else None
        cur, fr0 = s.at_msg or (dict(s.cur), s.frame)                            # as when "X used Y!" came up
        s.open = {'at': len(s.out) - 1, 'user': (sd, sl), 'status': mv.get('category') == 'Status', 'start': cur, 'seen': collections.Counter(),
                  'draining': {k for k, fr in s.changed.items() if fr0 - 1 <= fr <= fr0}}
        s.meta[-1].setdefault('targets', [0, 0])[1] += 1
        if only is not None and len(only) == 1: s.hit(only[0], 'only target')
    def hit(s, k, how):
        """the open move's target is the Pokemon in slot k; how: what showed it (kept in meta['aims'] with the VOD time, for spot checks)"""
        o = s.open
        if not o or k == o['user'] or k not in s.active: return
        s.out[o['at']] = s.out[o['at']].rstrip('|') + f"|{k[0]}{k[1]}: {s.nick(s.active[k])}"; s.meta[-1]['targets'][0] += 1; s.open = None
        s.meta[-1].setdefault('aims', []).append({'turn': s.turn, 'line': s.out[o['at']], 'how': how, 'vt': s.now()})
    def shut(s): s.open = None
    def last_move(s):
        """the user and target (as the log names them, '' if not known) of the last move this turn"""
        for l in reversed(s.out):
            if l.startswith('|turn|'): break
            if l.startswith('|move|'):
                p = l.split('|'); return p[2], (p[4] if len(p) > 4 else '')
        return '', ''
    def watch_hp(s, boxes):
        """one frame's HP boxes: track drops while a move is open"""
        for (sd, sl), (n, p) in boxes.items():
            if s.active.get((sd, sl)) != s.species(sd, n): continue
            if s.cur.get((sd, sl)) != p: s.changed[(sd, sl)] = s.frame
            s.cur[(sd, sl)] = p
        o = s.open
        if not o: return
        for k, p in s.cur.items():
            if k != o['user'] and k in o['start'] and p < o['start'][k] - 1: o['seen'][k] += 1
        sure = [k for k, c in o['seen'].items() if c >= 2]
        if len(sure) == 1 and not [k for k in o['seen'] if k != sure[0] and k not in o['draining']]: s.hit(sure[0], 'HP box')
        elif len(sure) > 1:                                                  # two boxes fell: the one not still draining from the last move
            fresh = [k for k in sure if k not in o['draining']]
            if len(fresh) == 1: s.hit(fresh[0], 'HP box, another still draining')
            else: s.shut()
    # Weather and terrain last 5 turns, 8 with the setter's rock or Terrain Extender (on its team sheet); the reader ends them itself when
    # the turns run out, so a missed "The rain stopped." does not leave rain up. The setter is the Pokemon whose move just set it, else the
    # Pokemon on the field (the latest sent out first) whose sheet ability sets it; the log line names it, so the parser's own duration
    # agrees.
    WX = {'RainDance': (('Drizzle',), ('Rain Dance',), 'Damp Rock'), 'SunnyDay': (('Drought', 'Orichalcum Pulse'), ('Sunny Day',), 'Heat Rock'),
          'Sandstorm': (('Sand Stream',), ('Sandstorm',), 'Smooth Rock'), 'Snowscape': (('Snow Warning',), ('Snowscape', 'Chilly Reception'), 'Icy Rock'),
          'Electric Terrain': (('Electric Surge', 'Hadron Engine'), ('Electric Terrain',), 'Terrain Extender'),
          'Grassy Terrain': (('Grassy Surge', 'Seed Sower'), ('Grassy Terrain',), 'Terrain Extender'),
          'Misty Terrain': (('Misty Surge',), ('Misty Terrain',), 'Terrain Extender'), 'Psychic Terrain': (('Psychic Surge',), ('Psychic Terrain',), 'Terrain Extender')}
    def field(s, line):
        p = line.split('|'); kind = 'weather' if p[1] == '-weather' else 'terrain'
        what = p[2].replace('move: ', '')
        if what == 'none' or p[1] == '-fieldend': s.timed.pop(kind, None); s.emit(line); return
        if what not in s.WX: s.emit(line); return
        abil, moves, rock = s.WX[what]
        mv = next((l for l in reversed(s.out[-12:]) if l.startswith('|move|')), None)
        setter = None; via = ''
        if mv and mv.split('|')[3] in moves: setter = mv.split('|')[2]
        else:
            for sd, sp in list(reversed(s.sent)) + [(k[0], v) for k, v in s.active.items()]:
                st = next((x for x in s.team(sd) if x['species'] == sp), None)
                if st and st['ability'] in abil and s.slot_of(sd, sp):
                    setter = s.mon(sd, sp); via = f"|[from] ability: {st['ability']}|[of] {setter}"; break
        item = ''
        if setter:
            sd, nick = setter[:2], setter.split(': ', 1)[1]
            item = next((x['item'] for x in s.team(sd) if s.nick(x['species']) == nick), '')
        s.timed[kind] = [line.split('|')[1], what, 8 if item == rock else 5]
        s.emit(line + via)
    def expire(s):
        """the end of a turn: weather and terrain count down, and end when their turns run out"""
        for kind, t in list(s.timed.items()):
            t[2] -= 1
            if t[2] <= 0:
                s.emit('|-weather|none' if kind == 'weather' else f'|-fieldend|move: {t[1]}'); del s.timed[kind]
    def send(s, sd, name):
        sp = s.species(sd, re.sub(r' the [A-Z][\w-]*(?: [A-Z][\w-]*)*$', '', name.strip()))     # "Primarina the Rank Master": a title
        if not sp: return
        s.shut(); free = s.slot_free[sd]; sl = free.pop(0) if free else next((x for x in 'ab' if (sd, x) not in s.active), None)
        if sl is None:                                                      # who went back was not shown: the HP boxes will tell which slot
            s.pending.append((sd, sp, len(s.out))); return
        s.active[(sd, sl)] = sp; s.sent.append((sd, sp)); s.emit(*s.note_seen(sd, sp))
        s.emit(f"|switch|{sd}{sl}: {s.nick(sp)}|{sp}, L50|{s.hp.get(('mon', sd, sp), 100)}/100")
    def place(s, boxes):
        """a send-out whose slot was unknown: put the switch where the battle text had it, in the slot the HP boxes now show it in"""
        keep = []
        for i, (sd, sp, at) in enumerate(s.pending):
            sl = next((x for (y, x), (n, p) in boxes.items() if y == sd and s.species(sd, n) == sp and s.active.get((sd, x)) != sp), None)
            if not sl: keep.append((sd, sp, at)); continue
            new = [f"|switch|{sd}{sl}: {s.nick(sp)}|{sp}, L50|{s.hp.get(('mon', sd, sp), 100)}/100"]
            old = s.active.get((sd, sl)); turn_start = max((j for j, l in enumerate(s.out[:at]) if l.startswith('|turn|')), default=0)
            seg = s.out[turn_start:at]; piv = max((j for j, l in enumerate(seg) if l.startswith('|move|') and l.split('|')[3] in PIVOT), default=None)
            pivot_in = piv is not None and not any(l.startswith('|switch|') for l in seg[piv + 1:])   # the switching move's own replacement
            if old and old != sp and old not in s.fainted[sd] and any(l.startswith('|move|') for l in seg) and not pivot_in:
                # sent in after this turn's moves, into a slot whose Pokemon did not go back: only a faint frees a slot then
                new.insert(0, f'|faint|{sd}{sl}: {s.nick(old)}'); s.fainted[sd].add(old); s.hp[('mon', sd, old)] = 0
            s.active[(sd, sl)] = sp; s.sent.append((sd, sp)); new = s.note_seen(sd, sp) + new
            for k, line in enumerate(new): s.out.insert(at + k, line)
            d = len(new)
            if s.open and s.open['at'] >= at: s.open['at'] += d
            s.pending[i + 1:] = [(a, b, c + d if c >= at else c) for a, b, c in s.pending[i + 1:]]; keep = [(a, b, c + d if c >= at else c) for a, b, c in keep]
        s.pending = keep
    def reconcile(s, boxes):
        """at a decision screen: the Pokémon on the field and their HP as the HP boxes show them"""
        s.pending = []
        for (sd, sl), (n, p) in sorted(boxes.items()):
            sp = s.species(sd, n)
            if not sp: continue
            if s.active.get((sd, sl)) != sp:                                  # a switch the battle text did not show
                s.active[(sd, sl)] = sp; s.emit(*s.note_seen(sd, sp)); s.emit(f"|switch|{sd}{sl}: {s.nick(sp)}|{sp}, L50|{p}/100"); s.hp[(sd, sl)] = p; continue
            if s.hp.get((sd, sl)) != p:
                s.emit(f"|{'-damage' if p < (s.hp.get((sd, sl)) or 100) else '-heal'}|{sd}{sl}: {s.nick(sp)}|{p}/100"); s.hp[(sd, sl)] = p
            s.hp[('mon', sd, sp)] = p
        for sd in ('p1', 'p2'): s.slot_free[sd] = []
    def close(s):
        """end the current game without having seen its last message: the result from who has Pokémon left, when that is clear"""
        left = {sd: 4 - len(s.fainted[sd]) for sd in ('p1', 'p2')}
        win = 'p1' if left['p2'] <= 0 < left['p1'] else 'p2' if left['p1'] <= 0 < left['p2'] else None
        if win is None and s.forfeit and left['p1'] != left['p2']: win = 'p1' if left['p1'] > left['p2'] else 'p2'   # a forfeit: the side behind
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
        if s.started and not s.ended:                                          # the players' names for the live page (memory only)
            for sd, nm in scoreboard_names(L).items():
                if nm: s.meta[-1].setdefault('who', {'p1': collections.Counter(), 'p2': collections.Counter()})[sd][nm] += 1
        sb = scoreboard(L)
        if sb:
            s.names.append((s.frame, sb))
            if s.started and not s.ended:
                s.game_names[sb] += 1
                if not s.sides_checked and sum(s.game_names.values()) >= 10:  # the players' names during this game: sheets on the right sides?
                    s.board = s.game_names.most_common(1)[0][0]; s.check_sides(); s.sides_checked = True
        boxes, decision, turn, text = battle(L)
        if s.ended and decision and len(boxes) >= 3: s.new_game()                       # the next game of the set
        # a message stays on screen for a few frames: read it once, when it leaves, in its most common reading (the first frame of a
        # message is sometimes misread: "Archaludop's Defensé rose!")
        s.gap = 0 if text else s.gap + 1                                       # one empty frame inside a message is a misread
        if s.run and (decision or s.gap >= 2 or (text and difflib.SequenceMatcher(None, text, s.run[-1]).ratio() <= 0.85)):
            best = collections.Counter(s.run).most_common(1)[0][0]; s.run = []
            if s.started and not s.ended: s.message(best)
            elif s.pre_on: s.pre.append(best)                                  # before turn 1 (Intimidate, weather, terrain): applied at the start
            s.at_msg = None
        if text and not (s.started and not s.ended) and re.search(r'^Go! .+ and .+!$|sent out .+ and .+!$', text):
            if not s.pre_on or s.frame - s.pre_frame > 60: s.pre = []          # leads coming in with no game running: a game is about to start
            s.pre_on = True; s.pre_frame = s.frame
        if text and not decision:
            if not s.run: s.at_msg = (dict(s.cur), s.frame)                     # the HP boxes and the frame when the message came up
            s.run.append(text)
        if s.started and not s.ended and boxes:                                         # mid-turn, the box of the Pokemon hit pops up alone
            if s.pending: s.place(boxes)
            s.watch_hp(boxes)
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
                if new_match: s.sheets = {}; s.seen = {'p1': [], 'p2': []}         # new players: a new match, new sheets
                if len(s.sheets) < 2: s.owners = {}; s.assign_sheets(boxes, board)
                if len(s.sheets) < 2:                                             # the broadcast showed no sheets for this match: go on without them
                    s.sheets = {}; s.closed = True
                if new_match: s.match += 1; s.game_in_match = 0
                s.board = s.board if s.board and not other else None; s.game_in_match += 1; s.meta[-1] = {'match': s.match, 'game': s.game_in_match, 'frame': s.frame, 'closed': s.closed}
                s.note = ''; s.header(boxes)
                for t in s.pre:                                                   # what happened as the leads came in: abilities
                    if PRE.search(t): s.message(t)
                s.pre = []; s.pre_on = False; s.turn = turn or 1; s.emit(f'|turn|{s.turn}'); s.in_decision = True; s.mark()
            elif decision and len(boxes) >= 3 and not s.note: s.note = 'joined mid-game: the bar starts with the next game'
            return
        if s.ended: return
        if decision and not s.in_decision and s.turn >= 2 and len(boxes) == 4 and all(p == 100 for n, p in boxes.values()) \
                and max(s.pairs.values()) > s.frame - 120:                       # new leads sent out in the last minute, everyone at full HP
            s.close(); s.prev_end = s.frame - 120
            s.new_game(); s.lead_seen = True; s.frame -= 1; return s.feed(lines)   # this frame again, as the new game's first decision
        if decision and not s.in_decision:
            # the HP bar slides in with the decision screen: its first frame can show a name over the next slot ("arizard 35%",
            # "Basculegion" at the left box). Its boxes count once two frames in a row agree (or after four frames)
            seen = {k: (s.species(k[0], n), p) for k, (n, p) in boxes.items()}; s.settle.append(seen)
            if len(s.settle) < 4 and (len(s.settle) < 2 or s.settle[-2] != seen): return
            s.shut(); s.reconcile(boxes); s.expire(); s.turn = max(s.turn + 1, turn or 0); s.emit('|upkeep', '|', f'|turn|{s.turn}'); s.mark()   # upkeep: durations count down
        if not decision: s.settle = []
        s.in_decision = decision

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
        os.makedirs(LV.OUT, exist_ok=True); s.serve(); threading.Thread(target=s.refine, daemon=True).start()
    def refine(s):
        """two reads (the user, 2026-10-13, as on the bot page): each turn read quickly as it comes (live.LIVE_SEEDS) is read again at
        live.refine_run (depth at 4x since 2026-10-16), the newest game and turn first, on one engine thread at the lowest priority; its game's page picks it up. A
        progress card counts the turns read again against the turns read so far"""
        LV = s.LV; prog = os.path.join(LV.OUT, f'{s.tag}_refined.turns'); shown = None; tried = {}   # (game, turn) -> its positions file's time
        if not os.path.exists(prog): open(prog, 'w').close()
        while True:
            todo = []
            try:
                for lv in reversed(list(s.lives)):
                    ev, rv = LV.records(lv.evf), LV.records(lv.rf)
                    for t in sorted(list(lv.weights), reverse=True):
                        names = [n + ' p1' for n in dict(lv.weights.get(t) or {})]
                        posf = os.path.join(LV.OUT, f'{lv.tag}_t{t}_pos.jsonl')
                        if not names or not os.path.exists(posf) or tried.get((lv.tag, t)) == os.path.getmtime(posf): continue
                        if all(n in ev for n in names) and not all(n in rv for n in names): todo.append((lv, t, posf))
            except RuntimeError: time.sleep(1); continue                      # a game's thread changed its turns meanwhile: look again
            total = sum(1 for _ in open(prog)) + len(todo)
            if total != shown:                                              # the card's total grows as the stream goes on
                json.dump({'title': f'Stream {s.tag}: turns read again with depth at 4x (one engine thread at the lowest priority)',
                           'out': os.path.relpath(prog, os.path.join(C.HERE, 'out')), 'total': total, 'done0': 0, 'started': time.time(), 'threads': 1,
                           'seeds': 32, 'staged': False, 'proc': 'broadcast.py', 'pid': os.getpid()}, open(prog + '.run.json', 'w')); shown = total
            if not todo: time.sleep(10); continue
            lv, t, posf = todo[0]; tried[(lv.tag, t)] = os.path.getmtime(posf)   # once a version of its positions (a correction writes them again)
            with LV.LUCK: LV.refine_run(posf, lv.rf)
            with open(prog, 'a') as fh: fh.write(f'{lv.tag} t{t}\n')
            lv.dirty = True
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
                            pl = {sd: c.most_common(1)[0][0] for sd, c in m.get('who', {}).items() if c} or None
                            g = {**lv.data['games'][0], 'title': f"M{m.get('match', '?')} G{m.get('game', '?')}", 'end': m.get('end'), 'idx': i, 'players': pl, 'refines': True,
                                 'versus': f"{pl.get('p1', 'Player 1')} vs {pl.get('p2', 'Player 2')}" if pl else None, 'sheets': not m.get('closed')}
                            g['steps'] = [{**st, 'vt': (m.get('times') or {}).get(st['turn'])} for st in g['steps']]
                            games.append(g)
                    rd = run.reader                                                  # a game being read: its status; between games: the reader's note
                    st = (run.lives[-1].status if run.lives else 'waiting for the first turn') if rd.started and not rd.ended else (rd.note or 'between games')
                    b = json.dumps({'games': games, 'video': run.video, 'live': {'url': 'data.json', 'status': st, 'format': 'Champions broadcast, open team sheets'}}).encode(); ct = 'application/json'
                elif p in ('/', '/index.html'):
                    html = open(os.path.join(C.HERE, 'page.html')).read().replace('<title>Eval Bar</title>', '<title>Champions Eval Bar</title>', 1)
                    html = html.replace('/*DATA*/null', json.dumps({'games': [], 'video': run.video, 'live': {'url': 'data.json', 'status': 'starting'}}))
                    b = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                         '<style>body{margin:0}</style></head><body>' + html + '</body></html>').encode(); ct = 'text/html; charset=utf-8'
                else: self.send_error(404); return
                self.send_response(200); self.send_header('Content-Type', ct); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)
            def do_POST(self):
                """the user's verdict on a check: {game, turn, key, choice: 'messages' or 'rules'}"""
                try:
                    q = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}'); lv = run.lives[int(q['game'])]
                    st = next(x for x in lv.data['games'][0]['steps'] if x['turn'] == int(q['turn']))
                    c = next(x for x in st['checks'] if x['key'] == q['key'])
                    if q['choice'] not in ('messages', 'rules', 'none'): raise ValueError(q['choice'])
                    lv.add_fix(int(q['turn']), q['key'], q['choice'], c); code, b = 200, b'{}'
                except Exception as e: code, b = 400, json.dumps({'error': type(e).__name__}).encode()
                self.send_response(code); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(b)
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
                closed = (s.reader.logs_meta()[i][1] if i < len(s.reader.logs_meta()) else {}).get('closed')
                lv = s.LV.Live(None, s.threads, 0, logfile=f, tag=f'{s.tag}_g{i + 1}', fmt='Champions broadcast, ' + ('no team sheets shown' if closed else 'open team sheets'))
                lv.live_seeds = s.LV.LIVE_SEEDS                                   # the quick read; refine() reads it again
                if closed: lv.bo3 = False                                          # each species' most common set, what the game shows laid on top
                s.lives.append(lv)
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
    def open_stream(n):
        """frames from number n + 1 on: a recording from n / 2 seconds after `start`, a live stream from where it is now"""
        src, hdr, _ = media(url)
        return subprocess.Popen(['nice', '-n', '10', P.exe('ffmpeg'), '-v', 'error', '-y', '-headers', hdr, '-re'] + (['-ss', str(secs(start) + n / 2)] if start else []) +
                                ['-i', src, '-vf', 'fps=2,scale=1280:-2', '-q:v', '3', '-start_number', str(n + 1), os.path.join(d, 'f_%06d.jpg')],
                                stderr=subprocess.PIPE, text=True)
    keep = os.path.join(C.HERE, 'out', 'live', tag + '.ocr.jsonl'); retries = 0; done = 0
    vid = re.search(r'(?:v=|youtu\.be/|/live/)([\w-]{11})', url)
    run = Runner(tag, threads, port, video={'id': vid.group(1), 'start': secs(start), 'live': not start} if vid else None, t0=secs(start))
    if not start and os.path.exists(keep):                                    # a live watch restarted: catch up on what it read before
        rows = sorted(map(json.loads, open(keep)), key=lambda x: x['file'])
        for row in rows: run.feed(row['lines'])
        done = int(rows[-1]['file'][2:8]) if rows else 0
        for f in os.listdir(d):
            if f.endswith('.jpg'): os.remove(os.path.join(d, f))
    ff = open_stream(done)
    while True:
        n = pump(run, d, keep, done)
        if n > done: done = n
        elif ff.poll() is not None:
            err = ff.stderr.read()
            if ('403' in err or 'Forbidden' in err or ff.returncode) and retries < 8:
                retries += 1; time.sleep(3); ff = open_stream(done); continue
            print('the stream ended', flush=True); break
        time.sleep(1)
    while True: time.sleep(60)
def pump(run, d, keep, done):
    """the frames in d numbered after `done`: Apple Vision reads them, the text is kept, the reader follows -> the last frame number"""
    files = sorted(f for f in os.listdir(d) if f.endswith('.jpg'))[:-1]              # the newest frame may still be being written
    new = [f for f in files if int(f[2:8]) > done]
    if not new: return done
    b = os.path.join(d, 'batch'); os.makedirs(b, exist_ok=True)
    for f in new: os.replace(os.path.join(d, f), os.path.join(b, f))
    out = subprocess.run([P.exe('ocr', OCR), b], capture_output=True, text=True).stdout
    with open(keep, 'a') as k: k.write(out)                                      # the text of every frame, for replaying or checking later
    for row in sorted(map(json.loads, out.splitlines()), key=lambda x: x['file']): run.feed(row['lines'])
    for f in new: os.remove(os.path.join(b, f))
    return int(new[-1][2:8])
def catch_up(run, d, keep):
    """a watch restarted: feed what it read before (kept text), clear old frames -> the last frame number"""
    if not os.path.exists(keep): return 0
    rows = sorted(map(json.loads, open(keep)), key=lambda x: x['file'])
    for row in rows: run.feed(row['lines'])
    for f in os.listdir(d):
        if f.endswith('.jpg'): os.remove(os.path.join(d, f))
    return int(rows[-1]['file'][2:8]) if rows else 0
# A live YouTube stream is also served as numbered 5-second fragments from its start (the DASH format yt-dlp lists with --live-from-start).
# Fetching them one by one follows the live edge without yt-dlp after the first call (YouTube's bot check can refuse yt-dlp after many
# requests), and can start anywhere in the stream so far.
def dash_source(url):
    """the stream's 720p fragment URL and request headers (they last about 6 hours)"""
    info = json.loads(subprocess.run(['yt-dlp', '-j', '--no-warnings', '--live-from-start', url], capture_output=True, text=True, check=True).stdout)
    f = next(x for x in info['formats'] if x.get('height') == 720 and (x.get('vcodec') or '').startswith('avc1') and 'dash' in (x.get('protocol') or ''))
    return {'url': f['url'], 'headers': f.get('http_headers') or info.get('http_headers') or {}}
def fragment(src, sq, out):
    """fragment sq -> (the file, or None if it is not there yet or failed; the stream's newest fragment number)"""
    r = subprocess.run(['curl', '-s', '--max-time', '60', '-D', '-', '-o', out] + sum((['-H', f'{k}: {v}'] for k, v in src['headers'].items()), [])
                       + [src['url'] + f'&sq={sq}'], capture_output=True, text=True)
    head = re.search(r'X-Head-Seqnum: (\d+)', r.stdout, re.I); ok = r.stdout.split('\n', 1)[0].split()[1:2] == ['200']
    return (out if ok and os.path.exists(out) and os.path.getsize(out) > 1000 else None), (int(head.group(1)) if head else None)
def follow(url, threads=2, port=8768, at=None, srcf=None):
    """a live YouTube stream through its fragments, from `at` (h:mm:ss into the stream; an earlier record of the stream is set aside) or,
    by default, from where an earlier follow of the same stream stopped (catching up on what it read), else the live edge, as they appear. srcf: a JSON file with the fragment URL and headers saved earlier,
    for when yt-dlp is refused"""
    vid = youtube(url).split('v=')[-1]; tag = 'live_' + re.sub(r'\W', '', vid)[:16]
    d = os.path.join(C.HERE, 'out', 'live', tag + '_frames'); os.makedirs(d, exist_ok=True); keep = os.path.join(C.HERE, 'out', 'live', tag + '.ocr.jsonl')
    src = json.load(open(srcf)) if srcf else dash_source(youtube(url)); tmp = os.path.join(d, 'frag.mp4')
    _, head = fragment(src, 0, tmp)
    if head is None: sys.exit('the stream did not answer: the fragment URL may have expired (about 6 hours)')
    pos = os.path.join(C.HERE, 'out', 'live', tag + '_sq.txt')               # the next fragment to fetch, so a restart carries on without a gap
    t0f = os.path.join(C.HERE, 'out', 'live', tag + '_t0.txt')               # the stream time of frame 1, so the video times survive a restart
    if at is not None:
        sq = secs(at) // 5
        for f in (keep, pos, t0f):
            if os.path.exists(f): os.replace(f, f + '.old')
    else: sq = int(open(pos).read()) if os.path.exists(pos) and os.path.exists(keep) else max(0, head - 1)
    if not (os.path.exists(t0f) and os.path.exists(keep)): open(t0f, 'w').write(str(sq * 5))
    t0 = float(open(t0f).read())
    run = Runner(tag, threads, port, video={'id': vid, 'start': 0, 'live': True}, t0=t0)   # a live stream: the page shows the newest turn
    done = catch_up(run, d, keep) if at is None else 0
    def fetch():
        nonlocal sq
        n = done; part = os.path.join(d, 'part'); os.makedirs(part, exist_ok=True)
        while True:
            fr, top = fragment(src, sq, tmp)
            if not fr: time.sleep(2 if top is None or sq > top else 5); continue
            subprocess.run([P.exe('ffmpeg'), '-v', 'error', '-y', '-i', fr, '-vf', 'fps=2,scale=1280:-2', '-q:v', '3', '-start_number', str(n + 1),
                            os.path.join(part, 'f_%06d.jpg')])
            for f in sorted(os.listdir(part)): os.replace(os.path.join(part, f), os.path.join(d, f)); n += 1
            sq += 1; open(pos, 'w').write(str(sq))
    threading.Thread(target=fetch, daemon=True).start()
    while True:
        done = max(done, pump(run, d, keep, done)); time.sleep(1)
def serve(url, threads=2, port=8768):
    """a stream read earlier (by follow or scan), on the page without fetching anything: what auto shows between streams"""
    vid = youtube(url).split('v=')[-1]; tag = 'live_' + re.sub(r'\W', '', vid)[:16]
    d = os.path.join(C.HERE, 'out', 'live', tag + '_frames'); os.makedirs(d, exist_ok=True); keep = os.path.join(C.HERE, 'out', 'live', tag + '.ocr.jsonl')
    if not os.path.exists(keep): sys.exit(f'no record of {vid} in out/live')
    t0f = os.path.join(C.HERE, 'out', 'live', tag + '_t0.txt'); t0 = float(open(t0f).read()) if os.path.exists(t0f) else 0
    run = Runner(tag, threads, port, video={'id': vid, 'start': 0, 'live': False}, t0=t0); catch_up(run, d, keep)
    print('the record is read; the page stays up until this is stopped', flush=True)
    while True: time.sleep(60)
def read(ocrf, t0=0):
    """t0: the video time of the file's first frame (a live stream read with follow: its out/live/live_<id>_t0.txt)"""
    r = Reader(); r.t0 = t0
    for row in sorted(map(json.loads, open(ocrf)), key=lambda x: x['file']): r.feed(row['lines'])
    return r
def youtube(x):
    """a YouTube link, or just its video id (no quotes needed in zsh, which reads the '?' of a link as a wildcard)"""
    return x if x.startswith('http') or os.path.exists(x) else f'https://www.youtube.com/watch?v={x}'
if __name__ == '__main__':
    P.own(); import live; live.evalbar_mode()                                # the eval bar's reading (fitted spreads, Baton Pass...)
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] in ('watch', 'scan', 'frames') and len(a) > 1: a[1] = youtube(a[1])
    if a[0] == 'frames': frames(a[1], a[2], *(a[3:5]))
    elif a[0] == 'ocr': ocr(a[1])
    elif a[0] == 'scan': scan(a[1], a[2], int(a[3]) if len(a) > 3 else 2, fetchers=int(a[4]) if len(a) > 4 else 4)
    elif a[0] == 'follow':
        kw = dict(x.split('=', 1) for x in a[2:] if '=' in x)
        follow(a[1], int(kw.get('threads', 2)), int(kw.get('port', 8768)), kw.get('at'), kw.get('src'))
    elif a[0] == 'serve':
        kw = dict(x.split('=', 1) for x in a[2:] if '=' in x)
        serve(a[1], int(kw.get('threads', 2)), int(kw.get('port', 8768)))
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
