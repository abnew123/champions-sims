// Showdown bot client (2026-10-10, the user: "let's make the bot and just make sure the play nice"): logs in as the bot account,
// searches the Reg M-C Bo3 ladder (and accepts challenges in that format), keeps each room's log, and on every |request| asks the
// brain (bot/brain.py, one long-lived process) what to click. Plays at a human pace, never starts the timer, answers PMs with one
// canned line, and stops searching when bot/limits.json says so: paused, the hourly / daily game caps, our rating at or above the stop,
// or an opponent whose rating is in the top band of the public ladder (the user: do not warp the top of the standings).
// usage (from the repo root): node --experimental-websocket --no-warnings bot/client.js [--dry]     (--dry: log in, no searching)
// bot/account.json {"name": ..., "password": ...} is git-ignored; so are the logs in bot/out/.
const fs = require('fs'), path = require('path'), {spawn} = require('child_process');
const HERE = __dirname, ROOT = path.join(HERE, '..'), OUT = path.join(HERE, 'out'); fs.mkdirSync(OUT, {recursive: true});
// --server <ws url> --name <guest name> --format <id> --challenge <user> --tag <label>: a local test server (pokemon-showdown start
// --no-security), a guest login, another format, challenge that user once instead of searching, and a label for this client's log
const ARG = k => { const i = process.argv.indexOf(k); return i >= 0 ? process.argv[i + 1] : null; };
const DRY = process.argv.includes('--dry'), LOCAL = !!ARG('--server');
const acct = ARG('--name') ? {name: ARG('--name'), password: null} : JSON.parse(fs.readFileSync(path.join(HERE, 'account.json')));
const limits = () => JSON.parse(fs.readFileSync(path.join(HERE, 'limits.json')));
const L0 = limits(); const FORMAT = ARG('--format') || L0.format; const CHALLENGE = ARG('--challenge'); const TAG = ARG('--tag') || acct.name;
// --secondary (2026-10-12, the user: a Bo1 bot beside the Bo3 one, same account): a second client for another format. Showdown sends an
// account's battles to all its connections, so every client handles only its own format's rooms, searches and games; only the primary
// one answers private messages and challenges (and records PMs), so nobody gets the canned reply twice.
const SECONDARY = process.argv.includes('--secondary');
const MINE = room => room.startsWith(`battle-${FORMAT}-`) || room.startsWith(`game-bestof3-${FORMAT}-`);
const WS = ARG('--server') || 'wss://sim3.psim.us/showdown/websocket';
const ACTION = LOCAL ? null : 'https://play.pokemonshowdown.com/action.php';
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), TAG + ':', ...a);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const rnd = (a, b) => a + Math.random() * (b - a);

// ---- the brain: one python process, JSON lines both ways, one request at a time
const brain = spawn(path.join(ROOT, '.venv', 'bin', 'python3'), [path.join(HERE, 'brain.py')], {cwd: ROOT, stdio: ['pipe', 'pipe', 'inherit']});
let brainBuf = '', brainQueue = [];
brain.stdout.on('data', d => { brainBuf += d; let i; while ((i = brainBuf.indexOf('\n')) >= 0) { const line = brainBuf.slice(0, i); brainBuf = brainBuf.slice(i + 1); if (!line.trim()) continue;
  const w = brainQueue.shift(); if (w) { try { w(JSON.parse(line)); } catch (e) { w({error: String(e)}); } } } });
brain.on('exit', c => { log('brain exited', c); process.exit(1); });
let brainChain = Promise.resolve();
function ask(msg) { return brainChain = brainChain.then(() => new Promise(res => { brainQueue.push(res); brain.stdin.write(JSON.stringify(msg) + '\n'); })); }

// ---- the public ladder: the rating of the N-th ranked player, refreshed hourly (the stop band)
let topBand = {elo: Infinity, at: 0};
async function refreshTop() {
  const L = limits(); if (LOCAL || Date.now() - topBand.at < 3600e3) return;
  try { const r = await fetch(`https://pokemonshowdown.com/ladder/${FORMAT}.json`); const j = await r.json(); const t = j.toplist || [];
    const n = Math.min(L.stop_if_opponent_in_top, t.length); topBand = {elo: n ? t[n - 1].elo : Infinity, at: Date.now()}; log(`ladder top ${n}: ${topBand.elo.toFixed(0)}+`); }
  catch (e) { log('ladder fetch failed', String(e)); topBand.at = Date.now(); }
}

// ---- our own rating: the public user JSON (the room's rating lines do not name a Bo3 rating reliably), refreshed after each match
async function refreshMyRating() {
  if (LOCAL || !me) return;
  try { const r = await fetch(`https://pokemonshowdown.com/users/${me.toLowerCase().replace(/[^a-z0-9]/g, '')}.json`); const j = await r.json();
    const x = (j.ratings || {})[FORMAT]; if (x && x.elo != null) { myRating = +x.elo; log(`rating ${myRating.toFixed(0)} (${x.w}-${x.l})`); } }
  catch (e) { log('rating fetch failed', String(e)); }
}
// ---- the record: bot/out/games.jsonl (no usernames: ratings and results only)
const GAMES = path.join(OUT, LOCAL ? `games_${TAG}.jsonl` : 'games.jsonl');
const allGames = () => fs.existsSync(GAMES) ? fs.readFileSync(GAMES, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l)) : [];
const games = () => allGames().filter(x => (x.format || 'gen9championsvgc2026regmcbo3') === FORMAT);   // this client's format (caps, stops, experiment)
let myRating = null;
function mayPlay(reason) {
  const L = limits(); const g = games(); const now = Date.now();
  if (LOCAL) return null;
  if (L.paused) return 'paused';
  if (g.filter(x => now - Date.parse(x.when) < 3600e3).length >= L.max_games_per_hour) return 'hourly cap';
  if (L.max_games_per_day != null && g.filter(x => now - Date.parse(x.when) < 86400e3).length >= L.max_games_per_day) return 'daily cap';
  if (myRating != null && L.stop_if_rating_at_least != null && myRating >= L.stop_if_rating_at_least) return `our rating ${myRating.toFixed(0)} is at the stop`;
  const tb = topBandShare(); if (tb && tb.top >= (L.top_band_max || 3)) return `${tb.top} of the last ${tb.n} matches were against the top ${L.stop_if_opponent_in_top}`;
  return null;
}
let stoppedForTop = false;
// the stop near the top (the user, 2026-10-12: no single match is safe to stop on, since a top player who has waited long enough is
// matched with anyone): stop once top_band_max (3) of the last top_band_window (20) matches were against a player rated at or above the
// ladder's stop_if_opponent_in_top-th (50th). Matches, not games: a best-of-3 against one top player is two or three games. Games are
// grouped into matches by their best-of-3 room (games.jsonl 'match'), or, for older records, by consecutive games against the same rating.
function topBandShare() {
  const L = limits(); if (!isFinite(topBand.elo)) return null;
  const M = []; let prev = null;
  for (const x of games()) {
    const key = x.match || `${x.oppRating}`;
    if (!prev || key !== prev.key || Date.parse(x.when) - prev.t > 30 * 60e3) { prev = {key, opp: x.oppRating || 0, t: Date.parse(x.when)}; M.push(prev); }
    else { prev.opp = Math.max(prev.opp, x.oppRating || 0); prev.t = Date.parse(x.when); }
  }
  const last = M.slice(-(L.top_band_window || 20));
  return {n: last.length, top: last.filter(m => m.opp >= topBand.elo).length};
}

// ---- the connection
let searchStart = 0;   // when our current ladder search began (limits.json max_search_seconds cancels a longer one)
let ws, me = null, searching = false, inGames = 0, pmReplied = new Set(), loginAt = 0, joinSent = new Set(), lastIdleLog = 0;
const rooms = {};   // room id -> {lines, side, req, done, oppRating, turn}
function send(s) {   // a send while the socket is down (a reconnect after the Mac slept, 2026-10-13) is dropped, not thrown: it crashed the Bo3 client
  if (!ws || ws.readyState !== WebSocket.OPEN) { log('not connected, dropped:', s.split('|').slice(-1)[0].slice(0, 40)); return; }
  ws.send(s); }
function connect() {
  ws = new WebSocket(WS);
  ws.onmessage = e => { for (const m of String(e.data).split('\n>').map((x, i) => i ? '>' + x : x)) onMessage(m); };
  // me = null: a new connection starts as a guest, which is not a logout (relogin would count it toward its three-an-hour stop)
  ws.onclose = () => { log('socket closed; reconnecting in 10 s'); searching = false; me = null; setTimeout(connect, 10000); };
  ws.onerror = () => {};
}
async function login(challstr) {
  if (!acct.password) { send(`|/trn ${acct.name},0,`); return; }   // a guest name on a local --no-security server
  const body = new URLSearchParams({act: 'login', name: acct.name, pass: acct.password, challstr});
  const r = await fetch(ACTION, {method: 'POST', body});
  const t = await r.text(); const j = JSON.parse(t.slice(1));
  if (!j.assertion) { log('login failed', JSON.stringify(j).slice(0, 200)); process.exit(1); }
  send(`|/trn ${acct.name},0,${j.assertion}`);
}
// logged out from elsewhere (2026-10-14: a logout of the account anywhere, a browser tab included, logs out every connection of it; both
// clients then played two games as a guest name, unable to find their side, slow to the timer each turn): log back in on this
// connection, so the next search is ours again. A game in progress cannot be saved: a rated battle forfeits a player whose name changes
// ("forfeited by changing their name", room-battle onRename), logging out included. More than three logouts within an hour stop the
// client instead (the watcher reports it).
let lastChallstr = null; const logouts = [];
function relogin(name) {
  me = null; searching = false; const now = Date.now(); logouts.push(now);
  const recent = logouts.filter(t => now - t < 3600e3).length;
  log(`logged out (now ${name}); ${recent > 3 ? 'more than three logouts this hour: stopping' : 'logging back in'}`);
  if (recent > 3) process.exit(1);
  setTimeout(() => login(lastChallstr).catch(e => log('login again failed', String(e).slice(0, 120))), 5000);
}
async function onMessage(m) {
  const lines = m.split('\n'); let room = '';
  if (lines[0].startsWith('>')) { room = lines[0].slice(1); lines.shift(); }
  for (const line of lines) {
    const p = line.split('|');
    if (process.env.BOT_DEBUG && !['challstr', 'formats', 'customgroups', 'queryresponse', 'updateuser', 'c', 'c:', 'chat', 'pm'].includes(p[1])) log(room ? '[' + room.slice(-14) + ']' : '[global]', line.slice(0, 160));
    if (!room) {   // global
      if (p[1] === 'challstr') { lastChallstr = p.slice(2).join('|'); await login(lastChallstr); }
      else if (p[1] === 'updateuser') { const name = p[2].replace(/^[^A-Za-z0-9]/, '').trim(); if (p[3] === '1' && name.toLowerCase() === acct.name.toLowerCase()) { me = name; loginAt = Date.now(); joinSent = new Set(); log('logged in as', me); send('|/cmd rooms'); onReady(); }
        else if (me && name.toLowerCase() !== acct.name.toLowerCase()) relogin(name); }
      else if (p[1] === 'pm') { onPM(p[2], p[3], p.slice(4).join('|')); }
      else if (p[1] === 'updatesearch') { try { const s = JSON.parse(p[2]); searching = (s.searching || []).includes(FORMAT); inGames = Object.keys(s.games || {}).filter(MINE).length;
        // after a (re)connect only: games already in progress at login are joined once (a new match's rooms also show up here a
        // moment before the server joins us to them, which is not a rejoin)
        // A room we already track counts as joined only if it has had a line since this login: a socket reconnect keeps `rooms`, and
        // the old test (any lines at all) sent no /join, so the bot could wait on it forever (the outside review, 2026-10-14)
        if (Date.now() - loginAt < 15000) for (const g of Object.keys(s.games || {}).filter(MINE)) if (!joinSent.has(g) && !(rooms[g] && (rooms[g].last || 0) > loginAt)) {
          joinSent.add(g); rooms[g] = rooms[g] || {lines: [], side: null, req: null, done: false, oppRating: null, turn: 0}; send(`|/join ${g}`); log('rejoining', g.slice(-16)); }
      } catch (e) {} }
      else if (p[1] === 'updatechallenges') { if (!SECONDARY) onChallenges(p[2]); }
      else if (p[1] === 'popup') { const t = p.slice(2).join('|'); log('popup:', t.slice(0, 200));
        // a team Showdown will not accept: never use it again. Not "requires you to use your own team": that is the search sent in a
        // reconnect's gap (2026-10-13), not the team; the search just goes again
        if (t.includes('Your team was rejected') && t.includes('use your own team')) { searching = false; }
        else if (t.includes('Your team was rejected') && currentTeam) {
          const rf = path.join(OUT, 'rejected_teams.json'); const r = fs.existsSync(rf) ? JSON.parse(fs.readFileSync(rf)) : [];
          if (!r.includes(currentTeam.name)) { r.push(currentTeam.name); fs.writeFileSync(rf, JSON.stringify(r)); }
          log('team rejected, will not use it again:', currentTeam.name); currentTeam = null; searching = false; } }
    } else {
      if (p[1] === 'deinit' || p[1] === 'noinit') { delete rooms[room]; continue; }   // we left the room (or it is gone): forget it
      if (!rooms[room] && !((room.startsWith('battle-') || room.startsWith('game-')) && (MINE(room) || LOCAL))) continue;   // only this format's battle and match rooms
      const R = rooms[room] || (rooms[room] = {lines: [], side: null, req: null, done: false, oppRating: null, turn: 0});
      R.last = Date.now();
      if (p[1] === 'init') { R.lines = []; }
      // chat lines go to bot/out/chat.jsonl only, not into the room log (see noteChat)
      if (p[1] === 'c' || p[1] === 'c:' || p[1] === 'chat') {
        if (p[1] === 'c' && p.length > 3) noteChat(room, p[2].replace(/^[^A-Za-z0-9]/, '').trim(), p.slice(3).join('|'));
        if (p[1] === 'c:' && p.length > 4) noteChat(room, p[3].replace(/^[^A-Za-z0-9]/, '').trim(), p.slice(4).join('|'));
        continue;
      }
      R.lines.push(line);
      if (p[1] === 'player' && p[3] && me && p[3].toLowerCase() === me.toLowerCase()) R.side = p[2];
      if (p[1] === 'player' && p[3] && me && p[3].toLowerCase() !== me.toLowerCase() && p[5]) R.oppRating = +p[5];
      if (p[1] === 'turn') R.turn = +p[2];
      if (p[1] === 'turn' && LOCAL && process.env.BOT_TEST_DROP && +p[2] === +process.env.BOT_TEST_DROP && !R.dropped) { R.dropped = true; log('test: closing the socket at turn', p[2]); setTimeout(() => ws.close(), 500); }   // reconnect test, local server only
      if (room.startsWith('game-bestof')) {   // the match room: confirm each game's start when asked, note the match result
        if (line.includes('/confirmready') || (p[1] === 'inactive' && me && line.includes(me) && line.includes('confirm'))) { if (!R.confirmed) { R.confirmed = true; setTimeout(() => { send(`${room}|/confirmready`); R.confirmed = false; }, 2000); } }
        if (p[1] === 'win' && !R.done) { R.done = true; const won = me && p[2].toLowerCase() === me.toLowerCase(); log('match over', room.slice(-16), won ? 'won' : 'lost'); fs.appendFileSync(path.join(OUT, LOCAL ? `matches_${TAG}.jsonl` : 'matches.jsonl'), JSON.stringify({when: new Date().toISOString(), room, won: !!won, games: R.lines.filter(l => l.startsWith('|uhtml|game')).length, team: currentTeam && currentTeam.name, arm: currentTeam && currentTeam.arm}) + '\n'); setTimeout(() => { send(`${room}|/leave`); delete rooms[room]; refreshMyRating(); }, 8000); }
        continue;
      }
      // Bo1's optional open team sheets (2026-10-12, the user: accept them): when both players accept, the server shows both sheets and the
      // bot plays on the real ones instead of guesses
      if (p[1] === 'uhtml' && p[2] === 'otsrequest' && line.includes('/acceptopenteamsheets') && !R.otsSent) {
        R.otsSent = true; setTimeout(() => { send(`${room}|/acceptopenteamsheets`); log(room.slice(-12), 'accepted open team sheets'); }, rnd(1500, 4000)); }
      if (p[1] === 'request' && p[2]) { try { R.req = JSON.parse(p[2]); } catch (e) { R.req = null; } if (R.req && R.req.side && R.req.side.id) R.side = R.req.side.id; if (R.req && !R.req.wait) handleRequest(room, R).catch(e => log('request error', room, String(e))); }
      // a rejected choice: Showdown re-sends a request when the rejection taught it something (a trap revealed: [Unavailable choice]),
      // and the bot answers that; otherwise it falls back to Showdown's default choice at once instead of letting the turn timer run
      if (p[1] === 'error' && /\[(Invalid|Unavailable) choice\]/.test(line) && R.req && !R.req.wait) {
        const rq = R.req; setTimeout(() => { if (R.req === rq && !R.done) { send(`${room}|/choose default|${rq.rqid}`); R.lines.push(`|bot-choice|${rq.rqid}|default`); log(room.slice(-12), `T${R.turn}`, 'choice rejected, sent default'); } }, 1500); }
      if ((p[1] === 'request' || p[1] === 'turn') && room.startsWith('battle-')) {   // the room log as the game goes (the Eval bar follows it live)
        try { fs.writeFileSync(path.join(OUT, room + '.log'), R.lines.join('\n') + '\n'); } catch (e) {} }
      if (p[1] === 'raw' && me && line.includes(me) && line.includes('rating:')) { const mm = /rating: (\d+)[^0-9]+(\d+)/.exec(line); if (mm) myRating = +mm[2]; }
      if (p[1] === 'win' || p[1] === 'tie') { onEnd(room, R, p[1] === 'win' ? p[2] : null); }
    }
  }
}
// every chat line addressed to the bot (battle-room chat and PMs) goes to bot/out/chat.jsonl and the console, so the user can see
// how opponents take it and stop the bot if people are unhappy
const CHAT = path.join(OUT, LOCAL ? `chat_${TAG}.jsonl` : 'chat.jsonl');
// chat text is written to the file only, never to the console or the room logs: an assistant reads the console and the room logs, and
// people's messages must not reach it (the user, 2026-10-11: a perfect prompt-injection avenue); the user reads bot/out/chat.jsonl
function noteChat(room, who, text) {
  if (!me || who.toLowerCase() === me.toLowerCase() || who === '~' || who === '&' || !text.trim() || text.startsWith('/')) return;
  fs.appendFileSync(CHAT, JSON.stringify({when: new Date().toISOString(), room, from: who, text}) + '\n');
  log(`chat message recorded (${room ? 'battle room' : 'private message'}); text in bot/out/chat.jsonl, for the user`);
  // anyone can stop the bot by writing "pause" in any case (the user, 2026-10-14): the text is matched here, never shown or logged
  if (/pause/i.test(text)) autoPause(room);
}
// set limits.json "paused" (both bots read it: no new searches; games in progress finish), and note when and where, without the text
function autoPause(room) {
  if (LOCAL) return;
  const f = path.join(HERE, 'limits.json'); const L = JSON.parse(fs.readFileSync(f));
  if (!L.paused) { L.paused = true; fs.writeFileSync(f, JSON.stringify(L, null, 2) + '\n'); }
  fs.appendFileSync(path.join(OUT, 'auto_pause.jsonl'), JSON.stringify({when: new Date().toISOString(), room: room || 'private message'}) + '\n');
  log(`auto-paused: a chat message asked for a pause (${room ? 'battle room' : 'private message'}); no new searches until the user unpauses`);
}
function onPM(from, to, text) {
  const who = from.replace(/^[^A-Za-z0-9]/, '').trim(); if (!me || who.toLowerCase() === me.toLowerCase() || SECONDARY) return;
  noteChat('', who, text);
  if (text.startsWith('/challenge')) return;   // handled by updatechallenges
  if ('~&@%#'.includes(from.trim()[0])) return;   // no canned "I'm a bot" reply to staff (the registration ticket's ~Staff, moderators)
  if (pmReplied.has(who.toLowerCase())) return; pmReplied.add(who.toLowerCase());
  send(`|/pm ${who}, ${limits().pm_reply}`);
}
function onChallenges(json) {
  let c; try { c = JSON.parse(json); } catch (e) { return; }
  for (const [user, fmt] of Object.entries(c.challengesFrom || {})) {
    const L = limits(); const why = mayPlay();
    if (!L.accept_challenges || fmt !== FORMAT || why || (DRY && !LOCAL)) { send(`|/reject ${user}`); log('rejected challenge', fmt, why || ''); continue; }
    pickTeam().then(t => { if (!t) { send(`|/reject ${user}`); return; } searchWithTeam(`|/accept ${user}`); log('accepted a challenge'); });
  }
}
let teams = null, teamIdx = 0;
// bot/experiment.json (2026-10-11): the sheet arm (each sheet team up to games_per_team) and the regional arm (random pool teams, no
// sheet, up to games) alternate match by match, the arm with fewer games first; when both are done the bot pauses itself
function experimentTeam() {
  const ef = path.join(HERE, 'experiment.json'); if (!fs.existsSync(ef) || LOCAL) return undefined;
  const E = JSON.parse(fs.readFileSync(ef)); const since = Date.parse(E.start);
  const g = games().filter(x => Date.parse(x.when) >= since && (x.format || 'gen9championsvgc2026regmcbo3') === FORMAT);   // this format's games only
  const rejected = fs.existsSync(path.join(OUT, 'rejected_teams.json')) ? JSON.parse(fs.readFileSync(path.join(OUT, 'rejected_teams.json'))) : [];
  // by_format (2026-10-12 evening, the user): a fixed role per format, no counts and no pause: Bo3 the exploiter (the Trick Room six with
  // its sheet), Bo1 the generalist (random regional teams, no sheet)
  const F = (E.by_format || {})[FORMAT];
  if (F) {
    if (F.arm === 'sheet') {
      const all = JSON.parse(fs.readFileSync(ARG('--teams') || path.join(HERE, 'teams.json'))); const open = F.teams.filter(t => !rejected.includes(t));
      if (!open.length) return null; const name = open[Math.floor(Math.random() * open.length)]; return {...all.find(t => t.name === name), arm: 'sheet'};
    }
    const pool = JSON.parse(fs.readFileSync(path.join(ROOT, F.pool))).filter(t => !rejected.includes(t.name));
    return {...pool[Math.floor(Math.random() * pool.length)], arm: 'regional'};
  }
  const per = t => g.filter(x => x.team === t).length; const reg = g.filter(x => x.arm === 'regional').length;
  const sheetOpen = E.sheet.teams.filter(t => per(t) < E.sheet.games_per_team && !rejected.includes(t));
  const sheetN = g.filter(x => x.arm === 'sheet').length;
  const regOpen = reg < E.regional.games;
  if (!sheetOpen.length && !regOpen) return null;
  const arm = !regOpen ? 'sheet' : !sheetOpen.length ? 'regional' : sheetN < reg ? 'sheet' : reg < sheetN ? 'regional' : (Math.random() < 0.5 ? 'sheet' : 'regional');
  const all = JSON.parse(fs.readFileSync(ARG('--teams') || path.join(HERE, 'teams.json')));
  if (arm === 'sheet') {
    const lo = Math.min(...sheetOpen.map(per)); const pick = sheetOpen.filter(t => per(t) === lo);
    const name = pick[Math.floor(Math.random() * pick.length)]; return {...all.find(t => t.name === name), arm};
  }
  const pool = JSON.parse(fs.readFileSync(path.join(ROOT, E.regional.pool))).filter(t => !rejected.includes(t.name));
  return {...pool[Math.floor(Math.random() * pool.length)], arm};
}
async function pickTeam() {
  const ex = experimentTeam();
  if (ex === null) {   // both arms done
    const L = limits(); if (!L.paused) { L.paused = true; fs.writeFileSync(path.join(HERE, 'limits.json'), JSON.stringify(L, null, 2)); log('experiment complete: paused'); }
    return null;
  }
  if (ex) { pendingPacked = (await ask({type: 'pack', sets: ex.sets})).packed; currentTeam = ex; log(`team for this match: ${ex.name} (${ex.arm})`); return ex; }
  if (!teams) teams = JSON.parse(fs.readFileSync(ARG('--teams') || path.join(HERE, 'teams.json')));   // --teams <file>: another team list (local tests)
  // which six this match: drawn by the teams' weights (bot/teams.json "weight"), re-read each time so weights can change live
  teams = JSON.parse(fs.readFileSync(ARG('--teams') || path.join(HERE, 'teams.json')));
  const tw = teams.map(x => x.weight == null ? 1 : x.weight); let r = Math.random() * tw.reduce((a, b) => a + b, 0), k = 0;
  while (k < teams.length - 1 && (r -= tw[k]) > 0) k++;
  const t = teams[k]; teamIdx++;
  pendingPacked = (await ask({type: 'pack', sets: t.sets})).packed; currentTeam = t; return t;
}
let currentTeam = null, pendingPacked = null;
// the team belongs to the account, not to the connection (2026-10-12: the Bo3 client's /utm became the Bo1 client's team), and Showdown
// takes it when the search starts: so the team is sent right before the search, under a lock file the other client respects
// the team is the account's, shared by every connection, so only one client at a time may go from /utm to /search: the lock is taken
// with an exclusive create and released only by its owner once its search is out; one older than 8 s is stale (a client that died
// holding it). Before 2026-10-14 (the outside review) both clients could read an expired lock, both /utm, and search with the second team.
const LOCK_ID = `${process.pid}-${TAG}`;
async function searchWithTeam(cmd) {
  const lf = path.join(OUT, 'search.lock');
  for (let i = 0; i < 30; i++) {
    try { fs.writeFileSync(lf, `${Date.now()} ${LOCK_ID}`, {flag: 'wx'}); break; }
    catch (e) {
      if (e.code !== 'EEXIST') break;
      let held = ''; try { held = fs.readFileSync(lf, 'utf8'); } catch (e2) { continue; }
      if (Date.now() - +held.split(' ')[0] > 8000) { try { if (fs.readFileSync(lf, 'utf8') === held) fs.unlinkSync(lf); } catch (e3) {} continue; }
      await sleep(1000);
    }
  }
  if (pendingPacked) send(`|/utm ${pendingPacked}`);
  await sleep(1500); send(cmd);
  await sleep(1500);
  try { if (fs.readFileSync(lf, 'utf8').split(' ')[1] === LOCK_ID) fs.unlinkSync(lf); } catch (e) {}
}
let loopOn = false;
async function onReady() {
  await refreshTop(); await refreshMyRating();
  if (loopOn) return; loopOn = true;   // a later login (reconnect, logged back in) keeps the one loop
  if (CHALLENGE) { await pickTeam(); await sleep(3000); await searchWithTeam(`|/challenge ${CHALLENGE}, ${FORMAT}`); log('challenged', CHALLENGE); }
  for (;;) {
    await sleep(5000);
    if (DRY || CHALLENGE) continue;
    // busy: Showdown lists a game of ours, or a tracked room is unfinished and was active in the last 15 minutes (a room whose last
    // line is older is stale: the bot would otherwise wait on it forever)
    const open = Object.entries(rooms).filter(([k, r]) => !r.done && Date.now() - (r.last || 0) < 15 * 60e3);
    const busy = inGames > 0 || open.length > 0;
    const why = mayPlay();
    if (Date.now() - (lastIdleLog || 0) > 5 * 60e3 && !open.some(([k, r]) => r.req)) { lastIdleLog = Date.now();
      if (busy || searching) log(`idle: ${searching ? 'searching' : ''}${inGames ? ` ${inGames} game(s) listed by the server` : ''}${open.length ? ` waiting on ${open.map(([k]) => k.slice(-16)).join(', ')}` : ''}`); }
    // a search that runs longer than limits.json max_search_seconds is cancelled (the user, 2026-10-12: Showdown's rating window starts at
    // 100 and widens by 1 every 0.3 s of waiting, so 30 s keeps our side of it near 200; an opponent who has waited longer can still be
    // matched at their wider window). The loop searches again after its usual pause.
    const maxs = limits().max_search_seconds;
    if (searching && !busy && maxs && searchStart && Date.now() - searchStart > maxs * 1e3) { send(`|/cancelsearch ${FORMAT}`); searchStart = 0; searching = false; log(`search cancelled after ${maxs} s`); await sleep(3000); continue; }
    if (!busy && !searching && limits().search_ladder && !why) { const t = await pickTeam(); if (!t) continue; await sleep(LOCAL ? 1000 : rnd(30e3, 120e3)); if (!searching && !mayPlay()) { await searchWithTeam(`|/search ${FORMAT}`); searching = true; searchStart = Date.now(); log('searching'); } }
    else if (why && !busy && !searching) { log('not searching:', why); await sleep(60e3); }
    await refreshTop();
  }
}
async function handleRequest(room, R) {
  const req = R.req; const L = limits();
  // the request's species, a Mega under its base forme's name: Floette-Eternal Mega Evolves into "Floette-Mega" (2026-10-13: read as
  // another team, recovered the wrong six and the brain had no set for it), so a Mega also matches a set whose species shares its base
  const reqSp = req.side ? [...new Set(req.side.pokemon.map(x => x.details.split(',')[0]))] : [];
  const fits = (x, s) => x.species === s || x.species.replace(/-Mega.*$/, '') === s.replace(/-Mega.*$/, '') ||
    (/-Mega/.test(s) && !/-Mega/.test(x.species) && x.species.split('-')[0] === s.split('-')[0]);
  const holds = t => t && reqSp.every(s => t.sets.some(x => fits(x, s)));
  if (req.side && !holds(currentTeam)) {   // after a restart mid-game, or a request showing another six: the team whose species it lists
    if (!teams) teams = JSON.parse(fs.readFileSync(ARG('--teams') || path.join(HERE, 'teams.json')));
    const sp = reqSp;
    const covers = t => sp.filter(s => t.sets.some(x => fits(x, s))).length;
    const rejected = fs.existsSync(path.join(OUT, 'rejected_teams.json')) ? JSON.parse(fs.readFileSync(path.join(OUT, 'rejected_teams.json'))) : [];
    let cands = teams.map(t => ({...t, arm: 'sheet'}));
    try { const E = JSON.parse(fs.readFileSync(path.join(HERE, 'experiment.json'))); cands = cands.concat(JSON.parse(fs.readFileSync(path.join(ROOT, E.regional.pool))).map(t => ({...t, arm: 'regional'}))); } catch (e) {}
    cands = cands.filter(t => !rejected.includes(t.name));   // a team Showdown refused is never the one in play
    const sz = t => t.sets.length;   // the team holding every Pokemon the request lists (fewest extras first)
    // regional teams often share their six species: the request's items and moves pick the one in play (2026-10-13: f194 #4 was read as f192 #51)
    const tid = x => String(x || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    const same = t => req.side.pokemon.reduce((n, p) => { const x = t.sets.find(x => fits(x, p.details.split(',')[0])); if (!x) return n;
      return n + (tid(x.item) === tid(p.item) ? 1 : 0) + (p.moves || []).filter(m => (x.moves || []).some(y => tid(y) === tid(m))).length; }, 0);
    currentTeam = cands.filter(t => covers(t) === sp.length).sort((a, b) => same(b) - same(a) || sz(a) - sz(b))[0] || cands.sort((a, b) => covers(b) - covers(a) || same(b) - same(a))[0];
    log('team recovered after a restart:', currentTeam.name);
  }
  if (R.oppRating != null && R.oppRating >= topBand.elo && !R.topNoted) { R.topNoted = true; log(`opponent rated ${R.oppRating} is in the ladder's top ${limits().stop_if_opponent_in_top} (counts toward the stop)`); }
  const think = LOCAL ? 300 : req.teamPreview ? rnd(8e3, 20e3) : rnd(L.think_seconds[0] * 1e3, L.think_seconds[1] * 1e3);
  const t0 = Date.now();
  if (req.teamPreview) {   // the open sheets (|showteam|) follow the preview request by a moment: wait for the opponent's, up to 8 s
    const opp = R.side === 'p1' ? 'p2' : 'p1';
    if (/bo\d$/.test(FORMAT)) for (let i = 0; i < 40 && !R.lines.some(l => l.startsWith('|showteam|' + opp + '|')); i++) await sleep(200);   // Bo1 has no open sheets: nothing to wait for
  }
  const ans = await ask({type: req.teamPreview ? 'preview' : 'turn', room, side: R.side, log: R.lines, request: req, team: currentTeam});
  if (ans.error) { log('brain error', room, ans.error); return; }
  if (ans.forfeit) {   // a lost game: say gg and forfeit this game (in a best-of-3 only this game; the match goes on)
    await sleep(LOCAL ? 300 : rnd(3e3, 6e3)); if (R.req !== req || R.done) return;
    send(`${room}|gg`); await sleep(1500); send(`${room}|/forfeit`); R.lines.push(`|bot-choice|${req.rqid}|forfeit`); log(room.slice(-12), `T${R.turn}`, ans.note); return;
  }
  const wait = Math.max(0, think - (Date.now() - t0)); await sleep(wait);
  if (R.req !== req) return;   // superseded
  const cmd = req.teamPreview ? `/team ${ans.order.join('')}` : `/choose ${ans.choice}`;
  send(`${room}|${cmd}|${req.rqid}`); log(room.slice(-12), `T${R.turn}`, cmd, ans.note || '');
  // the bot's own choice in its room log (the Eval bar, 2026-10-12: a choice the battle never shows, e.g. a Pokemon that fainted before
  // acting, still tells the Speed order): |bot-choice|<rqid>|<choose string, or team 1234, or forfeit>
  R.lines.push(`|bot-choice|${req.rqid}|${cmd.replace(/^\//, '').replace(/^choose /, '')}`);
}
function onEnd(room, R, winner) {
  if (R.done) return; R.done = true;
  const won = winner && me && winner.toLowerCase() === me.toLowerCase();
  const mm = R.lines.map(l => /game-bestof\d-[a-z0-9]+-(\d+)/.exec(l)).find(Boolean);   // the best-of-3 this game belongs to (Bo1: the game itself)
  const g = {when: new Date().toISOString(), room, side: R.side, won: winner ? !!won : null, turns: R.turn, oppRating: R.oppRating, myRating, team: currentTeam && currentTeam.name, arm: currentTeam && currentTeam.arm, match: mm ? mm[1] : room, format: FORMAT,
    ots: R.lines.some(l => l.startsWith('|showteam|'))};   // open team sheets shown (Bo3 always; Bo1 when both accepted: the user compares at 100 Bo1 games)
  fs.appendFileSync(GAMES, JSON.stringify(g) + '\n'); fs.writeFileSync(path.join(OUT, room + '.log'), R.lines.join('\n') + '\n');
  log('game over', room.slice(-12), won ? 'won' : winner ? 'lost' : 'tie', 'turns', R.turn, 'opp', R.oppRating, 'me', myRating);
  setTimeout(() => { send(`${room}|/leave`); delete rooms[room]; }, 5000);
}
connect();
