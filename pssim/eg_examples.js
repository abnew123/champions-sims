// Example 2v2 endgames for sanity checks: one game per archetype, the sheet's main-lead back pair vs the archetype's likeliest
// back pair, Trick Room up (3 turns) if the lead sets it at least half the time, otherwise none. Writes readable turn logs.
//   usage: MYTEAM=myteam_c_incin.json node eg_examples.js ../tr_leads_data.json eg_jobs1.json <out.json> [gameIndex=0]
const E = require(process.env.EG_ENGINE || './endgame.js'); const fs = require('fs');
const [dataf, jobsf, outf, gi = '0'] = process.argv.slice(2);
const TAB = {'Tailwind': 'Tailwind goodstuffs', 'Indeedee TR': 'Indeedee TR / Psychic Terrain', 'Balance': 'Balance, no speed control',
  'Trick Room': 'Trick Room without Indeedee', 'Rain + Sun': 'Rain + sun', 'Perish': 'Perish trap'};
const full = n => n === 'Indeedee' ? 'Indeedee-F' : n;
const jobs = JSON.parse(fs.readFileSync(jobsf));
function topPair(arch) { const f = j => j.freq ?? j.w; let best = null; for (const j of jobs) if (j.arch === arch && (!best || f(j) > f(best))) best = j; return best; }

// Showdown protocol -> readable lines, one list per turn
function readable(log) {
  const turns = [[]]; const hp = {}; const who = s => { const [pos, n] = s.split(': '); return (pos.startsWith('p1') ? 'your ' : 'their ') + n; };
  let skip = false, last = '';
  for (const l of log) {
    if (skip) { skip = false; continue; }
    if (l.startsWith('|split|')) { continue; }
    if (l === last) continue; last = l;
    const p = l.split('|'); const T = turns[turns.length - 1]; const tag = p[1];
    const from = (l.match(/\[from\] (?:item: |ability: )?([^|]+)/) || [])[1];
    if (tag === 'turn') { turns.push([]); continue; }
    if (tag === 'switch') { const [cur, max] = p[4].split(' ')[0].split('/').map(Number); hp[p[2].split(': ')[0].slice(0, 3)] = 100 * cur / max; T.push(`${who(p[2])} is out (${p[3].split(',')[0]})`); }
    else if (tag === 'move') T.push(`<b>${who(p[2])}</b> uses <b>${p[3]}</b>${p[4] && !l.includes('[spread]') && p[4] !== p[2] ? ' on ' + who(p[4]) : ''}${l.includes('[still]') ? ' (fails)' : ''}`);
    else if (tag === '-damage' || tag === '-heal') {
      const k = p[2].split(': ')[0].slice(0, 3); const st = p[3].split(' ')[0];
      const now = st === '0' ? 0 : (([c, m]) => 100 * c / m)(st.split('/').map(Number)); const d = now - (hp[k] ?? 100); hp[k] = now;
      T.push(`&nbsp;&nbsp;${who(p[2])} ${d < 0 ? '&minus;' : '+'}${Math.abs(d).toFixed(0)}% &rarr; ${now.toFixed(0)}%${from ? ' (' + from + ')' : ''}`);
    }
    else if (tag === 'faint') T.push(`&nbsp;&nbsp;<b>${who(p[2])} faints</b>`);
    else if (tag === '-activate' && p[3] && p[3].includes('Protect')) T.push(`&nbsp;&nbsp;${who(p[2])} protects itself`);
    else if (tag === '-activate' && p[3]) T.push(`&nbsp;&nbsp;${who(p[2])}: ${p[3].replace('move: ', '').replace('ability: ', '')}`);
    else if (tag === '-fail') T.push(`&nbsp;&nbsp;but it fails (${who(p[2])})`);
    else if (tag === '-immune') T.push(`&nbsp;&nbsp;${who(p[2])} is immune`);
    else if (tag === '-miss') T.push(`&nbsp;&nbsp;it misses ${p[3] ? who(p[3]) : ''}`);
    else if (tag === 'cant') T.push(`&nbsp;&nbsp;${who(p[2])} can&rsquo;t move (${p[3]})`);
    else if (tag === '-crit') T.push(`&nbsp;&nbsp;critical hit on ${who(p[2])}`);
    else if (tag === '-supereffective') T.push(`&nbsp;&nbsp;super effective on ${who(p[2])}`);
    else if (tag === '-resisted') T.push(`&nbsp;&nbsp;resisted by ${who(p[2])}`);
    else if (tag === '-boost' || tag === '-unboost') T.push(`&nbsp;&nbsp;${who(p[2])} ${p[3]} ${tag === '-boost' ? '+' : '&minus;'}${p[4]}${from ? ' (' + from + ')' : ''}`);
    else if (tag === '-mega') T.push(`${who(p[2])} Mega Evolves`);
    else if (tag === '-enditem') T.push(`&nbsp;&nbsp;${who(p[2])} uses up its ${p[3]}`);
    else if (tag === '-fieldstart') T.push(`Trick Room is up`);
    else if (tag === '-fieldend') T.push(`<b>Trick Room ends</b>`);
    else if (tag === '-weather' && !l.includes('[upkeep]')) T.push(p[2] === 'none' ? 'the weather ends' : `${p[2].replace('SunnyDay', 'sun').replace('RainDance', 'rain').replace('Sandstorm', 'sand').replace('Snowscape', 'snow')} starts${from ? ' (' + from + ')' : ''}`);
    else if (tag === '-fieldstart' || tag === '-terrain' ) T.push(l);
    else if (tag === 'win') T.push(`<b>${p[2] === 'Me' ? 'You win' : 'They win'}</b>`);
  }
  return turns;
}

const data = JSON.parse(fs.readFileSync(dataf)); const out = [];
for (const tab of data) {
  const arch = TAB[tab.tab] || tab.tab; const pk = tab.picks[0]; const tp = topPair(arch); if (!tp) continue;
  const mine = pk.back.split(', ').map(full); const K = (pk.tr || 0) >= 50 ? 3 : 0;
  const [ms, ts] = E.sets(arch, mine, tp.theirs); const log = [];
  const v = E.playGame(ms, ts, +gi, K, log);
  out.push({tab: tab.tab, lead: pk.lead.join(' + '), tr: pk.tr, mine, theirs: tp.theirs, w: tp.w, K, v, turns: log.turns || [], events: readable(log.full),
    sets: [...ms, ...ts].map(s => `${s.species} @ ${s.item} · ${s.ability} · ${s.nature} · ${s.moves.join(' / ')}`), w: tp.freq ?? tp.w});
  console.log(tab.tab, mine.join('+'), 'vs', tp.theirs.join('+'), 'K' + K, '->', v.toFixed(2));
}
for (const spec of (process.env.EG_EXTRA || '').split(';').filter(Boolean)) {
  const [arch, m, t, K] = spec.split('|'); const mine = m.split(','), theirs = t.split(',');
  const [ms, ts] = E.sets(arch, mine, theirs); const log = []; const v = E.playGame(ms, ts, +gi, +K, log);
  out.push({tab: 'Extra: ' + arch, lead: '(chosen example)', tr: +K ? 100 : 0, mine, theirs, w: 0, K: +K, v, turns: log.turns || [], events: readable(log.full),
    sets: [...ms, ...ts].map(s => `${s.species} @ ${s.item} · ${s.ability} · ${s.nature} · ${s.moves.join(' / ')}`)});
  console.log('extra', arch, mine.join('+'), 'vs', theirs.join('+'), 'K' + K, '->', v.toFixed(2));
}
fs.writeFileSync(outf, JSON.stringify(out, null, 1));
