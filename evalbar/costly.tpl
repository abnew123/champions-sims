<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600&display=swap">
<style>
/* Layout: a broadcast-desk review. Index of plays on the left, the chosen turn's board on the right; the two players keep their sides
   (Player 1 left and blue, Player 2 right and red) everywhere, as on the stream. */
:root {
  --bg: #eef1f4; --surface: #fbfcfd; --sunk: #e4e8ec; --ink: #141c24; --ink-2: #46535f; --muted: #75828e; --line: #d5dce2;
  --p1: #2369b0; --p1-soft: #dde8f4; --p2: #cf4f2f; --p2-soft: #f6e1dc;
  --hp-hi: #2f9a58; --hp-mid: #c99613; --hp-lo: #cc4433; --focus: #2369b0;
  --display: "Barlow Condensed", "Arial Narrow", "Roboto Condensed", system-ui, sans-serif;
  --body: "Barlow", "Segoe UI", system-ui, -apple-system, sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0f151b; --surface: #161e26; --sunk: #1d2731; --ink: #e5ebf1; --ink-2: #a7b3be; --muted: #7c8996; --line: #2a3541;
  --p1: #4b95dc; --p1-soft: #1b2c3e; --p2: #de6446; --p2-soft: #3a211b;
  --hp-hi: #3fb56c; --hp-mid: #dcaa2a; --hp-lo: #e05a48; --focus: #4b95dc; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #0f151b; --surface: #161e26; --sunk: #1d2731; --ink: #e5ebf1; --ink-2: #a7b3be; --muted: #7c8996; --line: #2a3541;
  --p1: #4b95dc; --p1-soft: #1b2c3e; --p2: #de6446; --p2-soft: #3a211b;
  --hp-hi: #3fb56c; --hp-mid: #dcaa2a; --hp-lo: #e05a48; --focus: #4b95dc; color-scheme: dark }
* { box-sizing: border-box }
body { background: var(--bg); color: var(--ink); font: 15px/1.45 var(--body); font-variant-numeric: tabular-nums; }
.wrap { max-width: 1320px; margin: 0 auto; padding-inline: 16px; padding-block: 20px 48px; }
h1, h2, h3, .cond { font-family: var(--display); font-weight: 600; letter-spacing: .01em; text-wrap: balance; margin: 0 }
h1 { font-size: 30px; line-height: 1.1 }
.intro { color: var(--ink-2); max-width: 70ch; margin: 6px 0 0 }
.intro b { color: var(--ink); font-weight: 600 }
.eyebrow { font-family: var(--display); font-weight: 600; font-size: 12.5px; letter-spacing: .09em; text-transform: uppercase; color: var(--muted) }
a { color: inherit }
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px }

.layout { display: grid; grid-template-columns: 340px minmax(0, 1fr); gap: 20px; margin-top: 18px; align-items: start }
@media (max-width: 900px) { .layout { grid-template-columns: minmax(0, 1fr) } }

/* index */
.index { position: sticky; top: calc(env(safe-area-inset-top, 0px) + 12px); display: flex; flex-direction: column; gap: 10px; min-width: 0 }
@media (max-width: 900px) { .index { position: static } }
.seg { display: flex; background: var(--sunk); border-radius: 8px; padding: 3px; gap: 3px }
.seg button { flex: 1; border: 0; background: transparent; color: var(--ink-2); font: 600 13.5px var(--display); letter-spacing: .03em; padding: 6px 4px; border-radius: 6px; cursor: pointer }
.seg button[aria-pressed="true"] { background: var(--surface); color: var(--ink); box-shadow: 0 1px 2px rgb(0 0 0 / .12) }
.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; max-height: calc(100vh - 170px); overflow: auto; border-top: 1px solid var(--line) }
@media (max-width: 900px) { .list { max-height: 46vh } }
.item { width: 100%; text-align: left; border: 0; background: transparent; color: inherit; font: inherit; cursor: pointer; padding: 9px 10px 9px 12px;
  display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 10px; border-left: 3px solid transparent; border-bottom: 1px solid var(--line) }
.item:hover { background: var(--sunk) }
.item[aria-current="true"] { background: var(--surface); border-left-color: var(--ink) }
.item .where { font: 600 12.5px var(--display); letter-spacing: .06em; text-transform: uppercase; color: var(--muted) }
.item .what { grid-column: 1; font-weight: 500; min-width: 0 }
.item .cost { grid-row: 1 / span 3; grid-column: 2; align-self: center; text-align: right; font: 600 20px var(--display) }
.item .cost small { display: block; font: 500 11px var(--body); color: var(--muted); letter-spacing: 0 }
.item .want { grid-column: 1; color: var(--ink-2); font-size: 13.5px }
.tag { display: inline-block; font: 600 11px var(--display); letter-spacing: .07em; text-transform: uppercase; padding: 1px 6px; border-radius: 4px; border: 1px solid var(--line); color: var(--ink-2); vertical-align: 1px }
.who { font-weight: 600 }
.who.p1 { color: var(--p1) } .who.p2 { color: var(--p2) }

/* detail */
.detail { min-width: 0; display: flex; flex-direction: column; gap: 16px }
.head { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; display: flex; flex-direction: column; gap: 10px }
.head h2 { font-size: 26px; line-height: 1.15 }
.facts { display: flex; flex-wrap: wrap; gap: 8px 22px; color: var(--ink-2) }
.facts b { color: var(--ink); font-weight: 600 }
.watch { font-weight: 600; text-decoration: none; border-bottom: 1px solid currentColor }
.note { color: var(--ink-2); font-size: 13.5px; background: var(--sunk); border-radius: 6px; padding: 8px 10px; max-width: 80ch }

/* the game's eval bars, one per turn */
.strip { display: flex; gap: 6px; align-items: flex-end; overflow-x: auto; padding-bottom: 2px }
.bar { flex: 0 0 auto; width: 34px; display: flex; flex-direction: column; align-items: center; gap: 3px; border: 0; background: none; padding: 0; cursor: pointer; color: var(--muted); font: 600 12px var(--display) }
.bar .col { width: 18px; height: 64px; border-radius: 4px; overflow: hidden; display: flex; flex-direction: column; position: relative; background: var(--p2) }
.bar .col i { display: block; margin-top: auto; background: var(--p1); border-top: 2px solid var(--surface) }
.bar .col::after { content: ""; position: absolute; left: 0; right: 0; top: 50%; border-top: 1px dashed rgb(255 255 255 / .7) }
.bar[aria-current="true"] { color: var(--ink) }
.bar[aria-current="true"] .col { outline: 2px solid var(--ink); outline-offset: 2px }
.bar.flag::before { content: "▲"; font-size: 9px; line-height: 1; color: var(--ink); order: 3 }
.stripwrap { display: flex; flex-direction: column; gap: 6px }
.legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12.5px; color: var(--ink-2) }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px }

.field { display: flex; flex-wrap: wrap; gap: 6px }
.chip { font-size: 13px; padding: 3px 9px; border-radius: 999px; background: var(--sunk); color: var(--ink-2) }
.chip b { color: var(--ink); font-weight: 600 }
.chip.p1 { background: var(--p1-soft) } .chip.p2 { background: var(--p2-soft) }

.board { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px }
@media (max-width: 640px) { .board { grid-template-columns: minmax(0, 1fr) } }
.side { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 10px; min-width: 0; border-top: 4px solid var(--p1) }
.side.p2 { border-top-color: var(--p2) }
.side > header { display: flex; justify-content: space-between; align-items: baseline; gap: 8px }
.side > header h3 { font-size: 20px }
.side.p1 > header h3 { color: var(--p1) } .side.p2 > header h3 { color: var(--p2) }
.side > header span { color: var(--ink-2); font-size: 13.5px }
.mon { border: 1px solid var(--line); border-radius: 8px; padding: 9px 10px; display: flex; flex-direction: column; gap: 5px }
.mon.acting { border-color: var(--ink); box-shadow: inset 0 0 0 1px var(--ink) }
.mon .top { display: flex; justify-content: space-between; gap: 8px; align-items: baseline }
.mon .nm { font: 600 17px var(--display) }
.mon .hpn { font-weight: 600 }
.hp { height: 7px; background: var(--sunk); border-radius: 4px; overflow: hidden }
.hp i { display: block; height: 100%; border-radius: 4px }
.meta { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 13px; color: var(--ink-2) }
.meta .st { font: 700 11px var(--display); letter-spacing: .08em; padding: 1px 5px; border-radius: 3px; background: var(--ink); color: var(--surface) }
.boost { font-weight: 600 } .boost.up { color: var(--hp-hi) } .boost.down { color: var(--hp-lo) }
.moves { display: flex; flex-wrap: wrap; gap: 4px }
.moves span { font-size: 12.5px; padding: 1px 7px; border-radius: 4px; background: var(--sunk); color: var(--ink-2) }
.moves span.used { background: var(--ink); color: var(--surface) }
.back { display: flex; flex-direction: column; gap: 4px; margin: 0; padding: 0; list-style: none }
.back li { display: grid; grid-template-columns: minmax(0, 1fr) 64px 40px; gap: 8px; align-items: center; font-size: 14px }
.back li .hp { height: 5px }
.back li.fnt { color: var(--muted); text-decoration: line-through }
.back li.pool { grid-template-columns: minmax(0, 1fr); color: var(--ink-2); font-style: italic }
.back li .r { text-align: right; color: var(--ink-2); font-size: 13px }
details.sheet summary { cursor: pointer; font: 600 13px var(--display); letter-spacing: .07em; text-transform: uppercase; color: var(--muted) }
.sets { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 8px; margin-top: 8px }
.set { font-size: 13px; color: var(--ink-2); border-left: 2px solid var(--line); padding-left: 8px }
.set b { color: var(--ink); font-weight: 600; font-size: 14px }

.panel { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 12px; min-width: 0 }
.panel > h3 { font-size: 19px }
.choices { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px }
@media (max-width: 640px) { .choices { grid-template-columns: minmax(0, 1fr) } }
.choice { min-width: 0; display: flex; flex-direction: column; gap: 6px }
.choice h4 { margin: 0; font: 600 16px var(--display) }
.choice h4 .did { font: 400 14px var(--body); color: var(--ink-2) }
.tbl { overflow-x: auto }
table { border-collapse: collapse; width: 100%; font-size: 13.5px }
th { text-align: left; font: 600 11.5px var(--display); letter-spacing: .07em; text-transform: uppercase; color: var(--muted); padding: 3px 6px; border-bottom: 1px solid var(--line) }
th.n, td.n { text-align: right; white-space: nowrap }
td { padding: 4px 6px; border-bottom: 1px solid var(--line); vertical-align: middle }
tr.played td { background: var(--sunk); font-weight: 600 }
td .pb { display: inline-block; height: 6px; border-radius: 3px; background: var(--ink-2); vertical-align: middle; margin-right: 6px; opacity: .55 }
.mk { font: 600 10.5px var(--display); letter-spacing: .07em; text-transform: uppercase; padding: 0 5px; border-radius: 3px; margin-left: 6px; white-space: nowrap }
.mk.pl { background: var(--ink); color: var(--surface) }
.mk.tp { border: 1px solid var(--ink-2); color: var(--ink-2) }
.events { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px }
.events li { padding-left: 12px; border-left: 3px solid var(--line) }
.events li.p1 { border-left-color: var(--p1) } .events li.p2 { border-left-color: var(--p2) }
.events li.key { background: var(--sunk); border-radius: 0 6px 6px 0; padding-block: 3px }
.events ul { list-style: none; margin: 1px 0 0; padding: 0; font-size: 13.5px; color: var(--ink-2) }
.events .n1 { color: var(--p1); font-weight: 600 } .events .n2 { color: var(--p2); font-weight: 600 }
.pp { font: 700 10px var(--display); letter-spacing: .05em; margin-right: 3px; vertical-align: 1px; opacity: .8 }
details.turn { border-top: 1px solid var(--line); padding-top: 6px }
details.turn summary { cursor: pointer; font: 600 14px var(--display); letter-spacing: .03em }
details.turn summary span { color: var(--muted); font: 400 13px var(--body); margin-left: 8px }
details.turn .events { margin: 6px 0 4px }
.empty { color: var(--muted); font-size: 13.5px }
.read { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr); gap: 14px 22px; align-items: start }
@media (max-width: 760px) { .read { grid-template-columns: minmax(0, 1fr) } }
.read table td.n b { font-weight: 600 }
.verdict { font: 600 18px var(--display); letter-spacing: .01em }
.verdict.good { color: var(--hp-hi) } .verdict.bad { color: var(--hp-lo) }
.read p { margin: 0; color: var(--ink-2); max-width: 70ch }
.read p b { color: var(--ink); font-weight: 600 }
.tag.good { border-color: var(--hp-hi); color: var(--hp-hi) }
@media (prefers-reduced-motion: no-preference) { .item, .bar .col { transition: background-color .12s } }
</style>

<div class="wrap">
  <header>
    <div class="eyebrow">__EVENT__ · Engine review</div>
    <h1>__TITLE__</h1>
    <p class="intro" id="intro"></p>
  </header>
  <div class="layout">
    <nav class="index" aria-label="Costly plays">
      <div class="seg" role="group" aria-label="Filter">
        <button id="f-all" data-f="all" aria-pressed="true">All</button>
        <button id="f-other" data-f="other" aria-pressed="false">Not Protect</button>
        <button id="f-protect" data-f="protect" aria-pressed="false">Protect</button>
        <button id="f-paid" data-f="paid" aria-pressed="false">Paid off</button>
      </div>
      <ul class="list" id="list"></ul>
    </nav>
    <main class="detail" id="detail"></main>
  </div>
</div>

<script>
const D = /*DATA*/null;
const SIDE = { p1: 'Player 1', p2: 'Player 2' };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const toid = s => String(s).toLowerCase().replace(/[^a-z0-9]/g, '');
const pct = v => Math.round(v * 100) + '%';
const pts = v => (v * 100).toFixed(1);
const hms = s => { s = Math.max(0, Math.floor(s)); return `${Math.floor(s / 3600)}:${String(Math.floor(s % 3600 / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}` };
const gameName = g => { const m = g.match(/m(\d+)g(\d+)/); return `Match ${m[1]}, Game ${m[2]}` };
const keyOf = c => `${c.game}-t${c.turn}-${c.side}-${toid(c.mon)}`;
const STAT = { atk: 'Atk', def: 'Def', spa: 'SpA', spd: 'SpD', spe: 'Spe', accuracy: 'Acc', evasion: 'Eva' };
const STATUS = { brn: 'BRN', par: 'PAR', slp: 'SLP', psn: 'PSN', tox: 'TOX', frz: 'FRZ' };
const hpColor = h => h > 50 ? 'var(--hp-hi)' : h > 20 ? 'var(--hp-mid)' : 'var(--hp-lo)';
const did = a => a.startsWith('switch to ') ? 'switched to ' + a.slice(10) : 'used ' + a;
let filter = 'all', current = null, viewTurn = null;
try { filter = localStorage.getItem('costly-filter') || 'all' } catch (e) {}

document.getElementById('intro').innerHTML =
  `<b>${D.scenarios.length} plays</b> from the __WHERE__. The engine gave each one under a 5% chance and rated it more than 5 win-chance points worse than its own top pick. ` +
  `Each board shows the position as the players knew it when the turn started. Back Pokémon not yet seen are averaged over. ` +
  `Targets come from the HP box that pops up on the broadcast when a Pokémon is hit. The costs compare moves by move, each with its best target. <b>Protect plays are probably engine errors</b>: the one-turn engine undervalues Protect, and those plays mostly came from the side that won. ` +
  `${D.reads ? `<b>${D.scenarios.filter(paid).length} of them paid off</b> against what the opponent actually did that turn. Each play shows how far the opponent would have had to lean for it to break even.` : ''}`;

function renderList() {
  const items = D.scenarios.filter(c => filter === 'all' || (filter === 'paid' ? paid(c) : (filter === 'protect') === c.protect));
  document.querySelectorAll('.seg button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.f === filter)));
  document.getElementById('list').innerHTML = items.map(c => {
    const res = c.side_won === true ? 'won' : c.side_won === false ? 'lost' : '';
    return `<li><button class="item" data-k="${keyOf(c)}" aria-current="${current && keyOf(current) === keyOf(c)}">
      <span class="where">${gameName(c.game).replace('Match ', 'M').replace(', Game ', ' · G')} · Turn ${c.turn}${res ? ` · ${SIDE[c.side].replace('Player ', 'P')} ${res}` : ''}</span>
      <span class="what"><span class="who ${c.side}">${SIDE[c.side].replace('Player ', 'P')}</span> ${esc(monName(c))} ${esc(did(c.played))} ${c.protect ? '<span class="tag">Protect</span>' : ''}${paid(c) ? ' <span class="tag good">Paid off</span>' : ''}</span>
      <span class="want">Engine: ${esc(c.planner_top)}</span>
      <span class="cost">−${pts(c.cost)}<small>points</small></span></button></li>`;
  }).join('') || '<li class="empty">No plays in this view.</li>';
}
function readOf(c) { return (D.reads || {})[keyOf(c)] }
function paid(c) { const r = readOf(c); return r && r.post_played >= r.post_top }
const act = a => a == null ? 'something the broadcast did not show' : a.startsWith('switch to ') ? 'a switch to ' + a.slice(10) : a;
function readHtml(c) {
  const r = readOf(c); if (!r) return '';
  const who = SIDE[c.side], opp = SIDE[c.side === 'p1' ? 'p2' : 'p1'];
  const good = r.post_played >= r.post_top, diff = Math.abs(r.post_played - r.post_top);
  const did = r.opp.map(([m, a]) => `${esc(m)} ${a ? esc(a.startsWith('switch to ') ? 'switched to ' + a.slice(10) : 'used ' + a) : '(not shown)'}`).join(', ');
  const lines = r.lines.filter(l => l.gain > 0.005).slice(0, 3);
  return `<section class="panel"><h3>Was it a read?</h3><div class="read">
    <div class="tbl"><table><thead><tr><th>${who} win chance</th><th class="n">vs a perfect opponent</th><th class="n">vs what ${opp} did</th></tr></thead><tbody>
      <tr><td>Engine's pick: ${esc(c.planner_top)}</td><td class="n">${pct(r.ante_top)}</td><td class="n">${pct(r.post_top)}</td></tr>
      <tr class="played"><td>The play: ${esc(c.played)}</td><td class="n">${pct(r.ante_played)}</td><td class="n">${pct(r.post_played)}</td></tr>
      <tr><td>Best answer to what ${opp} did: ${esc(r.post_best_action)}</td><td class="n"></td><td class="n">${pct(r.post_best)}</td></tr></tbody></table></div>
    <div style="display:flex;flex-direction:column;gap:8px;min-width:0">
      <div class="verdict ${good ? 'good' : 'bad'}">${good ? `Paid off: ${pts(diff)} points better than the engine's pick` : `Still cost ${pts(diff)} points against what ${opp} did`}</div>
      <p>${opp}: ${did}.</p>
      ${lines.length ? `<p>It beats the engine's pick when ${opp} plays ${lines.map(l => `<b>${esc(l.line).replace(/ -&gt; /g, ' → ')}</b> (+${pts(l.gain)} points; the engine expected this ${l.mix < 0.005 ? 'under 1%' : pct(l.mix)} of the time)`).join(', or ')}.</p>` : `<p>No line by ${opp} makes it better than the engine's pick.</p>`}
      ${r.shift == null ? (lines.length ? '<p>Even leaning all the way into those lines would not make up the difference.</p>' : '') : `<p>To break even, ${opp} would have to move <b>${pct(r.shift)}</b> of their choices toward its best case${r.shift < 0.2 ? ': a small lean, so a believable read' : r.shift < 0.45 ? ': a real lean, possible if they had a habit' : ': a big lean, more a gamble than a read'}.</p>`}
    </div></div>
    <p class="empty">Both rows hold the partner to what it actually did. ${r.exact ? 'Targets are as the HP boxes on the broadcast showed them.' : 'Where the broadcast did not show a target, the play and the pick take their best target and the opponent\'s move counts every target, weighted as the engine expected.'} Averaged over ${r.hypotheses} combination${r.hypotheses === 1 ? '' : 's'} of unseen back Pokémon.</p></section>`;
}
function stepOf(g, t) { return D.games[g].steps.find(s => s.turn === t) }
function monName(c) {
  const st = stepOf(c.game, c.turn); const m = st && st.state[c.side].mons.find(m => m.pos && !m.f && toid(m.sp) === toid(c.mon));
  return m ? m.n : c.mon;
}
function seg(x) { return Array.isArray(x) ? `<span class="n${x[0][1]}"><span class="pp">${x[0].toUpperCase()}</span>${esc(x[1])}</span>` : esc(x) }
function events(list, mark) {
  if (!list.length) return '<p class="empty">Nothing was read for this turn.</p>';
  return `<ul class="events">${list.map(e => {
    const key = mark && e.head.some(x => Array.isArray(x) && x[0] === mark.side && toid(x[1]).includes(toid(mark.mon)));
    return `<li class="${e.side || ''}${key ? ' key' : ''}">${e.head.map(seg).join('')}${e.notes.length ? `<ul>${e.notes.map(n => `<li>${n.map(seg).join('')}</li>`).join('')}</ul>` : ''}</li>`;
  }).join('')}</ul>`;
}
function sheetFor(g, side, m) { const sh = D.games[g].sheets[side] || {}; return sh[toid(m.sp || m.n)] || Object.values(sh).find(s => toid(s.species) === toid(m.sp || m.n)) }
function monCard(g, side, m, used, acting) {
  const s = sheetFor(g, side, m) || {};
  const boosts = Object.entries(m.b || {}).filter(([, v]) => v).map(([k, v]) => `<span class="boost ${v > 0 ? 'up' : 'down'}">${v > 0 ? '+' : '−'}${Math.abs(v)} ${STAT[k] || k}</span>`).join(' ');
  const item = m.item || s.item;
  return `<div class="mon${acting ? ' acting' : ''}">
    <div class="top"><span class="nm">${esc(m.n)}</span><span class="hpn">${m.hp}%</span></div>
    <div class="hp" role="img" aria-label="${m.hp}% HP"><i style="width:${m.hp}%;background:${hpColor(m.hp)}"></i></div>
    <div class="meta">${m.st ? `<span class="st">${STATUS[m.st] || esc(m.st)}</span>` : ''}${boosts}
      ${item ? `<span>${m.gone ? '<s>' + esc(item) + '</s> (used up)' : esc(item)}</span>` : ''}${s.ability ? `<span>${esc(s.ability)}</span>` : ''}
      ${(m.vol || []).map(v => `<span>${esc(v)}</span>`).join('')}</div>
    ${s.moves ? `<div class="moves">${s.moves.map(mv => `<span class="${used && toid(used) === toid(mv) ? 'used' : ''}">${esc(mv)}</span>`).join('')}</div>` : ''}
  </div>`;
}
function sideHtml(c, st, side, playedBy) {
  const mons = st.state[side].mons;
  const act = ['a', 'b'].map(p => mons.find(m => m.pos === p && !m.f));
  const back = mons.filter(m => !act.includes(m));
  const wp = side === 'p1' ? st.wp : 1 - st.wp;
  const sh = D.games[c.game].sheets[side] || {};
  return `<section class="side ${side}"><header><h3>${SIDE[side]}</h3><span>Win chance <b>${pct(wp)}</b></span></header>
    <div class="eyebrow">On the field</div>
    ${act.map(m => m ? monCard(c.game, side, m, playedBy[side + '|' + toid(m.sp)], viewTurn === c.turn && side === c.side && toid(m.sp) === toid(c.mon)) : '<div class="mon empty">Empty slot</div>').join('')}
    <div class="eyebrow">In the back</div>
    <ul class="back">${back.map(m => m.pool ? `<li class="pool">${esc(m.n)}, not seen yet</li>` :
      `<li class="${m.f ? 'fnt' : ''}"><span>${esc(m.n)}${m.st && !m.f ? ` <span class="tag">${STATUS[m.st] || esc(m.st)}</span>` : ''}</span><span class="hp"><i style="width:${m.hp}%;background:${hpColor(m.hp)}"></i></span><span class="r">${m.f ? 'out' : m.hp + '%'}</span></li>`).join('') || '<li class="pool">None</li>'}</ul>
    ${Object.keys(sh).length ? `<details class="sheet"><summary>Team sheet</summary><div class="sets">${Object.values(sh).map(s =>
      `<div class="set"><b>${esc(s.species)}</b><br>${esc(s.item)} · ${esc(s.ability)}${s.nature ? ' · ' + esc(s.nature) : ''}<br>${s.moves.map(esc).join(', ')}</div>`).join('')}</div></details>` : ''}
  </section>`;
}
function fieldHtml(st) {
  const f = st.state.field, out = [];
  if (f.weather) out.push(`<span class="chip"><b>${esc(f.weather)}</b>${f.wturns ? `, ${f.wturns} turns left` : ''}</span>`);
  if (f.terrain) out.push(`<span class="chip"><b>${esc(f.terrain)} Terrain</b>${f.tturns ? `, ${f.tturns} turns left` : ''}</span>`);
  if (f.tr) out.push(`<span class="chip"><b>Trick Room</b>, ${f.tr} turns left</span>`);
  for (const sd of ['p1', 'p2']) {
    const s = st.state[sd];
    if (s.tailwind) out.push(`<span class="chip ${sd}"><b>Tailwind</b> (${SIDE[sd]}), ${s.tailwind} turns left</span>`);
    for (const [k, v] of Object.entries(s.screens || {})) out.push(`<span class="chip ${sd}"><b>${esc(k)}</b> (${SIDE[sd]}), ${v} turns left</span>`);
    for (const h of s.hazards || []) out.push(`<span class="chip ${sd}"><b>${esc(h)}</b> (${SIDE[sd]})</span>`);
  }
  return out.length ? `<div class="field">${out.join('')}</div>` : '<div class="field"><span class="chip">No weather, terrain, Trick Room, Tailwind or screens</span></div>';
}
function choiceTable(st, side, m) {
  const k = side + '|' + m.sp, T = st.tables[k];
  let rows, played = null, top = null, note = '', target = null;
  if (T) { rows = Object.entries(T.table).map(([a, [p, v]]) => ({ a, p, v })); played = T.played; top = T.top; target = T.target }
  else {
    const sl = (st.opt[side] || []).find(s => toid(s.mon).includes(toid(m.sp)));
    if (!sl) return null;
    const acc = {};
    for (const o of sl.options) { const a = o.l.split(' → ')[0].replace(/^Switch to /, 'switch to ').replace(/ \(Mega\)$/, ''); const r = acc[a] ||= { a, p: 0, v: 0 }; r.p += o.w; r.v = Math.max(r.v, o.v) }
    rows = Object.values(acc); top = rows.reduce((x, y) => y.p > x.p ? y : x).a; note = 'The broadcast text did not show what it did.';
  }
  rows.sort((x, y) => y.p - x.p);
  return { played, target, note, html: `<div class="tbl"><table><thead><tr><th>Option</th><th class="n">Engine picks it</th><th class="n">${SIDE[side]} win chance</th></tr></thead><tbody>${rows.map(r =>
    `<tr class="${r.a === played ? 'played' : ''}"><td>${esc(r.a.replace(/^switch to /, 'Switch to '))}${r.a === played ? '<span class="mk pl">played</span>' : ''}${r.a === top ? '<span class="mk tp">engine pick</span>' : ''}</td>
     <td class="n"><span class="pb" style="width:${Math.max(1, Math.round(r.p * 60))}px"></span>${r.p < 0.005 && r.p > 0 ? '<1%' : pct(r.p)}</td><td class="n">${pct(r.v)}</td></tr>`).join('')}</tbody></table></div>` };
}
function render() {
  const c = current, g = D.games[c.game], st = stepOf(c.game, viewTurn), here = viewTurn === c.turn;
  const idx = g.steps.indexOf(st), next = g.steps[idx + 1];
  const wpS = s => c.side === 'p1' ? s.wp : 1 - s.wp;
  const vt = st.vt ?? (here ? c.video_s : null);
  const res = g.winner ? `${SIDE[g.winner]} won the game` : 'The winner was not read from the broadcast';
  const actives = ['p1', 'p2'].flatMap(sd => ['a', 'b'].map(p => [sd, st.state[sd].mons.find(m => m.pos === p && !m.f)]).filter(x => x[1]));
  const playedBy = {}; const tables = actives.map(([sd, m]) => { const t = choiceTable(st, sd, m); if (t && t.played) playedBy[sd + '|' + toid(m.sp)] = t.played; return [sd, m, t] });
  const D_ = document.getElementById('detail');
  D_.innerHTML = `
  <section class="head">
    <div class="eyebrow">${gameName(c.game)} · Turn ${viewTurn}${here ? '' : ` · the costly play was on turn ${c.turn}`}</div>
    <h2>${here ? `<span class="who ${c.side}">${SIDE[c.side]}</span>'s ${esc(monName(c))} ${esc(did(c.played))}` : `Turn ${viewTurn} of the same game`}</h2>
    ${here ? `<div class="facts"><span>Engine's pick <b>${esc(c.planner_top)}</b></span><span>Engine gave this play <b>${c.p_played < 0.01 ? 'under 1%' : pct(c.p_played)}</b></span>
      <span>Cost <b>${pts(c.cost)} points</b> (${pct(c.v_top)} → ${pct(c.v_played)} for ${SIDE[c.side]})</span></div>` : ''}
    <div class="facts"><span>${SIDE[c.side]} win chance <b>${pct(wpS(st))}</b> at the start of turn ${viewTurn}${next ? `, <b>${pct(wpS(next))}</b> at the start of turn ${next.turn}` : ''}</span><span>${res}</span>
      ${vt != null ? `<a class="watch" href="https://www.youtube.com/watch?v=${D.video}&t=${Math.max(0, Math.floor(vt) - 3)}s" target="_blank" rel="noopener">Watch turn ${viewTurn} at ${hms(vt)} ↗</a>` : ''}</div>
    ${here && c.protect ? '<p class="note">A Protect play. The engine looks one turn ahead and undervalues Protect, so this is more likely an engine error than a mistake.</p>' : ''}
    <div class="stripwrap"><div class="strip" role="group" aria-label="Win chance by turn">${g.steps.map(s =>
      `<button class="bar${s.turn === c.turn ? ' flag' : ''}" data-t="${s.turn}" aria-current="${s.turn === viewTurn}" title="Turn ${s.turn}: Player 1 ${pct(s.wp)}, Player 2 ${pct(1 - s.wp)}"><span class="col"><i style="height:${Math.round(s.wp * 100)}%"></i></span>T${s.turn}</button>`).join('')}</div>
      <div class="legend"><span><span class="sw" style="background:var(--p1)"></span>Player 1 win chance</span><span><span class="sw" style="background:var(--p2)"></span>Player 2</span><span>▲ the costly play's turn. Click a turn to see its board.</span></div></div>
  </section>
  ${here ? readHtml(c) : ''}
  ${fieldHtml(st)}
  <div class="board">${sideHtml(c, st, 'p1', playedBy)}${sideHtml(c, st, 'p2', playedBy)}</div>
  <section class="panel"><h3>Choices this turn</h3><div class="choices">${tables.map(([sd, m, t]) => `<div class="choice">
    <h4><span class="who ${sd}">${SIDE[sd].replace('Player ', 'P')}</span> ${esc(m.n)} <span class="did">${t && t.played ? esc(did(t.played)) + (t.target ? ' on ' + esc(t.target) : '') : ''}</span></h4>
    ${t ? t.html + (t.note ? `<p class="empty">${t.note}</p>` : '') : '<p class="empty">The engine had no options for it this turn.</p>'}</div>`).join('')}</div>
    <p class="empty">Win chance is the engine's estimate for that option, with its best target, against the other side's likely choices. The averages cover ${st.hyp} combination${st.hyp === 1 ? '' : 's'} of back Pokémon not seen yet.</p></section>
  <section class="panel"><h3>What happened on turn ${viewTurn}</h3>${events(st.events, here ? c : null)}</section>
  <section class="panel"><h3>The game so far</h3>${g.steps.filter(s => s.turn < viewTurn).map(s =>
    `<details class="turn"><summary>Turn ${s.turn}<span>Player 1 ${pct(s.wp)}</span></summary>${events(s.events)}</details>`).join('') || '<p class="empty">This is the first turn.</p>'}</section>`;
  D_.querySelectorAll('.bar').forEach(b => b.addEventListener('click', () => { viewTurn = +b.dataset.t; render() }));
}
function select(c, scroll) {
  current = c; viewTurn = c.turn; renderList(); render();
  try { history.replaceState(null, '', '#' + keyOf(c)) } catch (e) {}
  if (scroll && window.matchMedia('(max-width: 900px)').matches) document.getElementById('detail').scrollIntoView({ block: 'start' });
}
document.getElementById('list').addEventListener('click', e => { const b = e.target.closest('.item'); if (b) select(D.scenarios.find(c => keyOf(c) === b.dataset.k), true) });
document.querySelectorAll('.seg button').forEach(b => b.addEventListener('click', () => { filter = b.dataset.f; try { localStorage.setItem('costly-filter', filter) } catch (e) {} renderList() }));
const fromHash = D.scenarios.find(c => '#' + keyOf(c) === location.hash);
const first = fromHash || D.scenarios[0];
select(first, false);
</script>
