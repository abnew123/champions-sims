// The owner account's chat listener (2026-10-14, the user: Showdown's bot registration needs an owner account, abnew123; "make sure all
// chat messages to abnew123 also go to the chat export"). Logs in as the owner (--user, default abnew123) with the password in the
// git-ignored bot/account.json (the user: the same as the bot's), never searches, joins nothing and never replies: it only records the
// private messages others send it into bot/out/chat.jsonl (with to: the owner, so the export shows which account got them) and, as the
// bot clients do, pauses both bots when one contains "pause" (limits.json paused; when and where go to bot/out/auto_pause.jsonl).
// Chat text goes to the file only, never to the console (the user's rule against prompt injection through chat).
//   node --experimental-websocket --no-warnings bot/listen.js [--user abnew123]
const fs = require('fs'), path = require('path');
const HERE = __dirname, OUT = path.join(HERE, 'out');
const ARG = k => { const i = process.argv.indexOf(k); return i >= 0 ? process.argv[i + 1] : null; };
const USER = ARG('--user') || 'abnew123';
const PASS = JSON.parse(fs.readFileSync(path.join(HERE, 'account.json'))).password;
const WS = 'wss://sim3.psim.us/showdown/websocket', ACTION = 'https://play.pokemonshowdown.com/action.php';
const CHAT = path.join(OUT, 'chat.jsonl');
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), 'owner:', ...a);
let ws, me = null, lastChallstr = null; const logouts = [];
function send(s) { if (ws && ws.readyState === WebSocket.OPEN) ws.send(s); }
function connect() {
  ws = new WebSocket(WS);
  ws.onmessage = e => { for (const line of String(e.data).split('\n')) onLine(line).catch(err => log('error', String(err).slice(0, 120))); };
  ws.onclose = () => { log('socket closed; reconnecting in 10 s'); me = null; setTimeout(connect, 10000); };
  ws.onerror = () => {};
}
async function onLine(line) {
  const p = line.split('|');
  if (p[1] === 'challstr') { lastChallstr = p.slice(2).join('|'); await login(); }
  else if (p[1] === 'updateuser') {
    const name = p[2].replace(/^[^A-Za-z0-9]/, '').trim();
    if (p[3] === '1' && name.toLowerCase() === USER.toLowerCase()) { if (!me) { me = name; log('logged in as', me, '(listening for private messages only)'); } }
    else if (me) {   // logged out from elsewhere (a logout anywhere logs out every connection): log back in, as bot/client.js does
      me = null; const now = Date.now(); logouts.push(now); const recent = logouts.filter(t => now - t < 3600e3).length;
      log(`logged out (now ${name}); ${recent > 3 ? 'more than three logouts this hour: stopping' : 'logging back in'}`);
      if (recent > 3) process.exit(1);
      setTimeout(() => login().catch(e => log('login again failed', String(e).slice(0, 120))), 5000);
    }
  } else if (p[1] === 'pm') {
    PM(p);
  }
}
async function login() {
  const body = new URLSearchParams({act: 'login', name: USER, pass: PASS, challstr: lastChallstr});
  const t = await (await fetch(ACTION, {method: 'POST', body})).text(); const j = JSON.parse(t.slice(1));
  if (!j.assertion) { log('login failed'); process.exit(1); }
  send(`|/trn ${USER},0,${j.assertion}`);
}
function PM(p) {
  const from = p[2], who = from.replace(/^[^A-Za-z0-9]/, '').trim(), text = p.slice(4).join('|');
  if (!me || who.toLowerCase() === me.toLowerCase() || !text.trim() || text.startsWith('/')) return;
  fs.appendFileSync(CHAT, JSON.stringify({when: new Date().toISOString(), room: '', from: who, to: me, text}) + '\n');
  log(`private message recorded (to ${me}); text in bot/out/chat.jsonl, for the user`);
  if (/pause/i.test(text)) {
    const f = path.join(HERE, 'limits.json'); const L = JSON.parse(fs.readFileSync(f));
    if (!L.paused) { L.paused = true; fs.writeFileSync(f, JSON.stringify(L, null, 2) + '\n'); }
    fs.appendFileSync(path.join(OUT, 'auto_pause.jsonl'), JSON.stringify({when: new Date().toISOString(), room: `private message to ${me}`}) + '\n');
    log(`auto-paused: a private message to ${me} asked for a pause; no new searches until the user unpauses`);
  }
}
connect();
