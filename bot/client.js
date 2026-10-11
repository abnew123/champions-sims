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
const games = () => fs.existsSync(GAMES) ? fs.readFileSync(GAMES, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l)) : [];
let myRating = null;
function mayPlay(reason) {
  const L = limits(); const g = games(); const now = Date.now();
  if (LOCAL) return null;
  if (L.paused) return 'paused';
  if (g.filter(x => now - Date.parse(x.when) < 3600e3).length >= L.max_games_per_hour) return 'hourly cap';
  if (g.filter(x => now - Date.parse(x.when) < 86400e3).length >= L.max_games_per_day) return 'daily cap';
  if (myRating != null && myRating >= L.stop_if_rating_at_least) return `our rating ${myRating.toFixed(0)} is at the stop`;
  if (stoppedForTop) return 'met a top-of-ladder opponent';
  return null;
}
let stoppedForTop = false;

// ---- the connection
let ws, me = null, searching = false, inGames = 0, pmReplied = new Set();
const rooms = {};   // room id -> {lines, side, req, done, oppRating, turn}
function send(s) { ws.send(s); }
function connect() {
  ws = new WebSocket(WS);
  ws.onmessage = e => { for (const m of String(e.data).split('\n>').map((x, i) => i ? '>' + x : x)) onMessage(m); };
  ws.onclose = () => { log('socket closed; reconnecting in 10 s'); searching = false; setTimeout(connect, 10000); };
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
async function onMessage(m) {
  const lines = m.split('\n'); let room = '';
  if (lines[0].startsWith('>')) { room = lines[0].slice(1); lines.shift(); }
  for (const line of lines) {
    const p = line.split('|');
    if (process.env.BOT_DEBUG && !['challstr', 'formats', 'customgroups', 'queryresponse', 'updateuser'].includes(p[1])) log(room ? '[' + room.slice(-14) + ']' : '[global]', line.slice(0, 160));
    if (!room) {   // global
      if (p[1] === 'challstr') { await login(p.slice(2).join('|')); }
      else if (p[1] === 'updateuser') { const name = p[2].replace(/^[^A-Za-z0-9]/, '').trim(); if (p[3] === '1' && name.toLowerCase() === acct.name.toLowerCase()) { me = name; log('logged in as', me); send('|/cmd rooms'); onReady(); } }
      else if (p[1] === 'pm') { onPM(p[2], p[3], p.slice(4).join('|')); }
      else if (p[1] === 'updatesearch') { try { const s = JSON.parse(p[2]); searching = (s.searching || []).length > 0; inGames = Object.keys(s.games || {}).length; } catch (e) {} }
      else if (p[1] === 'updatechallenges') { onChallenges(p[2]); }
      else if (p[1] === 'popup') { log('popup:', p.slice(2).join('|').slice(0, 200)); }
    } else {
      const R = rooms[room] || (rooms[room] = {lines: [], side: null, req: null, done: false, oppRating: null, turn: 0});
      if (p[1] === 'init') { R.lines = []; }
      R.lines.push(line);
      if (p[1] === 'c' && p.length > 3) noteChat(room, p[2].replace(/^[^A-Za-z0-9]/, '').trim(), p.slice(3).join('|'));
      if (p[1] === 'c:' && p.length > 4) noteChat(room, p[3].replace(/^[^A-Za-z0-9]/, '').trim(), p.slice(4).join('|'));
      if (p[1] === 'player' && p[3] && me && p[3].toLowerCase() === me.toLowerCase()) R.side = p[2];
      if (p[1] === 'player' && p[3] && me && p[3].toLowerCase() !== me.toLowerCase() && p[5]) R.oppRating = +p[5];
      if (p[1] === 'turn') R.turn = +p[2];
      if (room.startsWith('game-bestof')) {   // the match room: confirm each game's start when asked, note the match result
        if (line.includes('/confirmready') || (p[1] === 'inactive' && me && line.includes(me) && line.includes('confirm'))) { if (!R.confirmed) { R.confirmed = true; setTimeout(() => { send(`${room}|/confirmready`); R.confirmed = false; }, 2000); } }
        if (p[1] === 'win' && !R.done) { R.done = true; const won = me && p[2].toLowerCase() === me.toLowerCase(); log('match over', room.slice(-16), won ? 'won' : 'lost'); fs.appendFileSync(path.join(OUT, LOCAL ? `matches_${TAG}.jsonl` : 'matches.jsonl'), JSON.stringify({when: new Date().toISOString(), room, won: !!won, games: R.lines.filter(l => l.startsWith('|uhtml|game')).length}) + '\n'); setTimeout(() => { send(`${room}|/leave`); delete rooms[room]; refreshMyRating(); }, 8000); }
        continue;
      }
      if (p[1] === 'request' && p[2]) { try { R.req = JSON.parse(p[2]); } catch (e) { R.req = null; } if (R.req && !R.req.wait) handleRequest(room, R).catch(e => log('request error', room, String(e))); }
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
function noteChat(room, who, text) {
  if (!me || who.toLowerCase() === me.toLowerCase() || who === '~' || who === '&' || !text.trim() || text.startsWith('/')) return;
  fs.appendFileSync(CHAT, JSON.stringify({when: new Date().toISOString(), room, from: who, text}) + '\n');
  log('CHAT', room ? room.slice(-14) : 'pm', who + ':', text.slice(0, 200));
}
function onPM(from, to, text) {
  const who = from.replace(/^[^A-Za-z0-9]/, '').trim(); if (!me || who.toLowerCase() === me.toLowerCase()) return;
  noteChat('', who, text);
  if (text.startsWith('/challenge')) return;   // handled by updatechallenges
  if (pmReplied.has(who.toLowerCase())) return; pmReplied.add(who.toLowerCase());
  send(`|/pm ${who}, ${limits().pm_reply}`);
}
function onChallenges(json) {
  let c; try { c = JSON.parse(json); } catch (e) { return; }
  for (const [user, fmt] of Object.entries(c.challengesFrom || {})) {
    const L = limits(); const why = mayPlay();
    if (!L.accept_challenges || fmt !== FORMAT || why || (DRY && !LOCAL)) { send(`|/reject ${user}`); log('rejected challenge', fmt, why || ''); continue; }
    pickTeam().then(() => { send(`|/accept ${user}`); log('accepted a challenge'); });
  }
}
let teams = null, teamIdx = 0;
async function pickTeam() {
  if (!teams) teams = JSON.parse(fs.readFileSync(ARG('--teams') || path.join(HERE, 'teams.json')));   // --teams <file>: another team list (local tests)
  const t = teams[teamIdx % teams.length]; teamIdx++;
  const packed = (await ask({type: 'pack', sets: t.sets})).packed;
  send(`|/utm ${packed}`); currentTeam = t; return t;
}
let currentTeam = null;
async function onReady() {
  await refreshTop(); await refreshMyRating();
  if (CHALLENGE) { await pickTeam(); await sleep(3000); send(`|/challenge ${CHALLENGE}, ${FORMAT}`); log('challenged', CHALLENGE); }
  for (;;) {
    await sleep(5000);
    if (DRY || CHALLENGE) continue;
    const busy = inGames > 0 || Object.values(rooms).some(r => !r.done);
    const why = mayPlay();
    if (!busy && !searching && limits().search_ladder && !why) { await pickTeam(); await sleep(LOCAL ? 1000 : rnd(30e3, 120e3)); if (!searching && !mayPlay()) { send(`|/search ${FORMAT}`); searching = true; log('searching'); } }
    else if (why && !busy && !searching) { log('not searching:', why); await sleep(60e3); }
    await refreshTop();
  }
}
async function handleRequest(room, R) {
  const req = R.req; const L = limits();
  if (R.oppRating != null && R.oppRating >= topBand.elo && !stoppedForTop) { stoppedForTop = true; log(`opponent rated ${R.oppRating} is in the ladder's top band: this is the last game`); }
  const think = LOCAL ? 300 : req.teamPreview ? rnd(8e3, 20e3) : rnd(L.think_seconds[0] * 1e3, L.think_seconds[1] * 1e3);
  const t0 = Date.now();
  if (req.teamPreview) {   // the open sheets (|showteam|) follow the preview request by a moment: wait for the opponent's, up to 8 s
    const opp = R.side === 'p1' ? 'p2' : 'p1';
    for (let i = 0; i < 40 && !R.lines.some(l => l.startsWith('|showteam|' + opp + '|')); i++) await sleep(200);
  }
  const ans = await ask({type: req.teamPreview ? 'preview' : 'turn', room, side: R.side, log: R.lines, request: req, team: currentTeam});
  if (ans.error) { log('brain error', room, ans.error); return; }
  const wait = Math.max(0, think - (Date.now() - t0)); await sleep(wait);
  if (R.req !== req) return;   // superseded
  const cmd = req.teamPreview ? `/team ${ans.order.join('')}` : `/choose ${ans.choice}`;
  send(`${room}|${cmd}|${req.rqid}`); log(room.slice(-12), `T${R.turn}`, cmd, ans.note || '');
}
function onEnd(room, R, winner) {
  if (R.done) return; R.done = true;
  const won = winner && me && winner.toLowerCase() === me.toLowerCase();
  const g = {when: new Date().toISOString(), room, side: R.side, won: winner ? !!won : null, turns: R.turn, oppRating: R.oppRating, myRating, team: currentTeam && currentTeam.name};
  fs.appendFileSync(GAMES, JSON.stringify(g) + '\n'); fs.writeFileSync(path.join(OUT, room + '.log'), R.lines.join('\n') + '\n');
  log('game over', room.slice(-12), won ? 'won' : winner ? 'lost' : 'tie', 'turns', R.turn, 'opp', R.oppRating, 'me', myRating);
  setTimeout(() => { send(`${room}|/leave`); delete rooms[room]; }, 5000);
}
connect();
