// Live battle feed for the eval bar's spectator mode. Connects to Showdown as a guest (no account), joins a battle room as a spectator
// and keeps a file with the room's battle log (rewritten whole when the server resends it, appended otherwise); exits once the battle
// has ended. Also lists the ongoing battles of a format: room id and the lower of the two ratings, one per line (no player names).
// usage: node --experimental-websocket evalbar/live_feed.js list <format>
//        node --experimental-websocket evalbar/live_feed.js watch <room> <out.log>
const fs = require('fs');
const URL = 'wss://sim3.psim.us/showdown/websocket';
const [cmd, arg, outf] = process.argv.slice(2);
function connect(onmsg, onclose) {
  const ws = new WebSocket(URL);
  ws.onmessage = e => { for (const m of String(e.data).split('\n>').map((x, i) => i ? '>' + x : x)) onmsg(ws, m); };
  ws.onclose = onclose || (() => {}); ws.onerror = () => {};
  return ws;
}
if (cmd === 'list') {
  const t = setTimeout(() => { console.error('no answer from the server'); process.exit(1); }, 15000);
  connect((ws, m) => {
    if (m.includes('|challstr|')) ws.send('|/cmd roomlist ' + arg);
    else if (m.includes('|queryresponse|roomlist|')) {
      const rooms = JSON.parse(m.split('|queryresponse|roomlist|')[1]).rooms || {};
      for (const [id, r] of Object.entries(rooms)) console.log(JSON.stringify({room: id, elo: r.minElo || null}));
      clearTimeout(t); process.exit(0);
    }
  });
} else if (cmd === 'watch') {
  const room = arg; let ended = false, lines = [];
  const write = () => fs.writeFileSync(outf, lines.join('\n') + '\n');
  const open = () => connect((ws, m) => {
    if (m.includes('|challstr|')) { ws.send('|/join ' + room); return; }
    if (!m.startsWith('>' + room)) return;
    const body = m.split('\n').slice(1);
    if (body.some(l => l.startsWith('|noinit|') || l.startsWith('|deinit'))) { if (!ended) { console.error('the room is gone: ' + room); process.exit(2); } return; }
    if (body[0] === '|init|battle') lines = body; else lines.push(...body);       // on (re)joining, the server sends the whole log again
    write();
    if (body.some(l => l.startsWith('|win|') || l === '|tie')) { ended = true; setTimeout(() => process.exit(0), 2000); }
  }, () => { if (!ended) setTimeout(open, 3000); });
  open();
} else { console.error('usage: live_feed.js list <format> | watch <room> <out.log>'); process.exit(1); }
