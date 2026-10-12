// Turn-1 payoff matrices: the player's lead pair vs an archetype's common lead pair, scored by the replay-fitted
// post-turn-1 win-probability model. Exact mechanics from Pokemon Showdown's Champions mod.
'use strict';
const {Battle, Dex, Teams} = require('pokemon-showdown');
const dex = Dex.mod('champions');
const fs = require('fs');
// pokemon-showdown 0.11.11's champions mod gives three Megas an outdated ability (Golisopod-Mega Emergency Exit, Garchomp-Mega-Z Sand
// Force, Absol-Mega-Z Magic Bounce; real games: Tough Claws, Levitate, Sharpness; found by Eval bar, 2026-10-11). Its species data is
// frozen, so each battle's Mega Evolution is wrapped to give the Mega the engine data's ability (as evalbar/positions.js does).
const MEGA_ABILITY = {};
for (const [id, s] of Object.entries(JSON.parse(fs.readFileSync(__dirname + '/../native/engine_data_full.json')).species)) {
  const sp = dex.species.get(id);
  if (/mega/.test(id) && s.abilities && s.abilities['0'] && sp.exists && sp.abilities['0'] !== s.abilities['0']) MEGA_ABILITY[id] = s.abilities['0'];
}
function fixMegas(b) {
  const run = b.actions.runMegaEvo.bind(b.actions);
  b.actions.runMegaEvo = (p) => { const r = run(p); const ab = MEGA_ABILITY[p.species.id];
    if (r && ab && dex.toID(ab) !== p.ability) { p.setAbility(ab, null, null, true); p.baseAbility = dex.toID(ab); } return r; };
  return b;
}
const foes = JSON.parse(fs.readFileSync(__dirname + '/../foes.json'));
// OPP_MODEL=<file>: another opponent model in the same shape (e.g. the sheet kit's per-group models built from real teams); default the archetypes
const OPP = process.env.OPP_MODEL ? JSON.parse(fs.readFileSync(process.env.OPP_MODEL))
  : Object.assign({}, JSON.parse(fs.readFileSync(__dirname + '/opp_model_a.json')), JSON.parse(fs.readFileSync(__dirname + '/opp_model_b.json')));
// post-turn-1 win model (logistic, 7,781 Reg M-C Bo3 games): per unit of each "lead" feature
const W = {hp: 0.808, ko: 0.259, rel: 0.239, spe: 0.056, tw: 0.436, tr: 0.598, scr: 0.531, stat: 0.441};
// refit: [hp, ko, relPos, relNegOther, relNegSelf, irr, spe, tw, tr, scr, stat] (all 'my lead' differences)
const W2 = [0.815, 0.235, 0.326, 0.222, 0.016, -0.010, 0.036, 0.465, 0.638, 0.566, 0.444, 0.723];  // last: a Perish Song that went off on turn 1 (refit, +/-0.20)
const SELFDROP = new Set(['Make It Rain', 'Draco Meteor', 'Overheat', 'Leaf Storm', 'Psycho Boost', 'Fleur Cannon', 'Superpower', 'Armor Cannon', 'Clanging Scales', 'Spin Out', 'Hammer Arm']);
const toID = s => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '');

const MY_DEFAULT = {
  Rillaboom: {species: 'Rillaboom', item: 'Miracle Seed', ability: 'Grassy Surge', moves: ['Fake Out', 'Grassy Glide', 'Wood Hammer', 'U-turn'], nature: 'Adamant', evs: [18, 25, 5, 0, 10, 8]},
  Incineroar: {species: 'Incineroar', item: 'Sitrus Berry', ability: 'Intimidate', moves: ['Fake Out', 'Throat Chop', 'Flare Blitz', 'Parting Shot'], nature: 'Careful', evs: [32, 0, 20, 0, 14, 0]},
  Sneasler: {species: 'Sneasler', item: 'Grassy Seed', ability: 'Unburden', moves: ['Close Combat', 'Dire Claw', 'Acrobatics', 'Protect'], nature: 'Adamant', evs: [14, 20, 0, 0, 0, 32]},
  Gholdengo: {species: 'Gholdengo', item: 'Focus Sash', ability: 'Good as Gold', moves: ['Make It Rain', 'Shadow Ball', 'Power Gem', 'Protect'], nature: 'Modest', evs: [2, 0, 0, 32, 0, 32]},
  Kingambit: {species: 'Kingambit', item: 'Chople Berry', ability: 'Defiant', moves: ['Kowtow Cleave', 'Sucker Punch', 'Iron Head', 'Low Kick'], nature: 'Adamant', evs: [32, 14, 20, 0, 0, 0]},
  Salamence: {species: 'Salamence', item: 'Salamencite', ability: 'Intimidate', moves: ['Hyper Voice', 'Double-Edge', 'Tailwind', 'Protect'], nature: 'Naive', evs: [1, 21, 0, 15, 0, 29]},
};
const MY = process.env.MYTEAM ? JSON.parse(fs.readFileSync(process.env.MYTEAM)) : MY_DEFAULT;
const FALLBACK = {  // sets for back-row Pokemon the archetype table didn't list (Baltimore/ladder modal sets)
  Sylveon: 'fairyfeather|pixilate|Modest|hypervoice/hyperbeam/detect/quickattack', Staraptor: 'staraptite|intimidate|Jolly|closecombat/bravebird/tailwind/protect',
  Incineroar: 'sitrusberry|intimidate|Careful|fakeout/flareblitz/partingshot/throatchop', Kingambit: 'chopleberry|defiant|Adamant|kowtowcleave/suckerpunch/ironhead/protect',
  Dragonite: 'dragoninite|multiscale|Modest|dragonpulse/heatwave/protect/tailwind', Camerupt: 'cameruptite|solidrock|Quiet|ancientpower/earthpower/heatwave/protect',
  Basculegion: 'choicescarf|adaptability|Jolly|aquajet/flipturn/lastrespects/wavecrash', Metagross: 'metagrossite|clearbody|Adamant|psychicfangs/steelroller/protect/bodypress',
  Torkoal: 'charcoal|drought|Quiet|eruption/heatwave/protect/weatherball', Hatterene: 'lifeorb|magicbounce|Quiet|dazzlinggleam/expandingforce/protect/trickroom',
  Swampert: 'swampertite|damp|Adamant|earthquake/icepunch/protect/wavecrash', Golisopod: 'golisopite|emergencyexit|Adamant|ironhead/leechlife/protect/swordsdance',
  'Indeedee-F': 'rockyhelmet|psychicsurge|Bold|followme/helpinghand/psychic/trickroom', Farigiraf: 'sitrusberry|armortail|Bold|helpinghand/protect/psychic/trickroom',
  Politoed: 'sitrusberry|drizzle|Calm|encore/perishsong/protect/weatherball', Archaludon: 'leftovers|stamina|Modest|dragonpulse/electroshot/flashcannon/protect',
  Pelipper: 'focussash|drizzle|Timid|hurricane/tailwind/weatherball/wideguard', Rillaboom: 'miracleseed|grassysurge|Adamant|fakeout/grassyglide/highhorsepower/woodhammer',
  'Arcanine-Hisui': 'focussash|rockhead|Jolly|extremespeed/flareblitz/headsmash/protect', Salamence: 'salamencite|intimidate|Timid|dracometeor/hypervoice/protect/tailwind',
  Sneasler: 'grassyseed|unburden|Adamant|closecombat/direclaw/protect/fakeout', Gholdengo: 'lifeorb|goodasgold|Timid|makeitrain/nastyplot/protect/shadowball',
  Raichu: 'raichunitey|lightningrod|Timid|fakeout/focusblast/protect/zapcannon', Garchomp: 'garchompitez|roughskin|Modest|dracometeor/flamethrower/powergem/protect',
  Indeedee: 'choicescarf|psychicsurge|Modest|expandingforce/mysticalfire/protect/trick', Excadrill: 'focussash|sandrush|Jolly|highhorsepower/ironhead/protect/rockslide',
  Tyranitar: 'tyranitarite|sandstream|Jolly|knockoff/lowkick/protect/rockslide', Corviknight: 'psychicseed|mirrorarmor|Careful|bravebird/bulkup/powertrip/roost',
  Froslass: 'froslassite|cursedbody|Timid|auroraveil/blizzard/protect/shadowball', Charizard: 'charizarditey|blaze|Modest|heatwave/protect/solarbeam/weatherball',
  Venusaur: 'focussash|chlorophyll|Modest|leafstorm/protect/sleeppowder/sludgebomb', Grimmsnarl: 'lightclay|prankster|Careful|lightscreen/partingshot/reflect/spiritbreak',
  Mawile: 'mawilite|hypercutter|Brave|playrough/rockslide/suckerpunch/swordsdance', Gardevoir: 'gardevoirite|trace|Modest|expandingforce/hypervoice/protect/thunderbolt',
  Armarouge: 'lifeorb|flashfire|Modest|armorcannon/expandingforce/protect/trickroom', Gengar: 'gengarite|cursedbody|Modest|perishsong/protect/shadowball/sludgebomb',
  Vivillon: 'focussash|compoundeyes|Timid|hurricane/protect/ragepowder/sleeppowder', Sinistcha: 'colburberry|hospitality|Bold|matchagotcha/protect/ragepowder/trickroom',
  'Floette-Eternal': 'floettite|flowerveil|Modest|calmmind/dazzlinggleam/moonblast/protect', Volcarona: 'grassyseed|flamebody|Modest|flamethrower/gigadrain/protect/quiverdance',
  Delphox: 'delphoxite|blaze|Timid|heatwave/nastyplot/protect/psychic', Aerodactyl: 'aerodactylite|unnerve|Jolly|dualwingbeat/rockslide/tailwind/wideguard',
  Milotic: 'leftovers|competitive|Calm|scald/icebeam/icywind/protect', Whimsicott: 'focussash|prankster|Timid|moonblast/tailwind/encore/protect',
};
const FOEKEY = {Raichu: 'M-Raichu Y', Salamence: 'M-Salamence', 'Arcanine-Hisui': 'Arcanine-H', Golisopod: 'M-Golisopod', 'Floette-Eternal': 'M-Floette',
  Tyranitar: 'M-Tyranitar', Gardevoir: 'M-Gardevoir', Metagross: 'M-Metagross', Charizard: 'M-Charizard Y', Staraptor: 'M-Staraptor', Baxcalibur: 'M-Baxcalibur'};
function defaultEVs(nature) {
  if (['Adamant', 'Jolly', 'Naughty', 'Lonely'].includes(nature)) return [2, 32, 0, 0, 0, 32];
  if (['Modest', 'Timid', 'Mild', 'Rash', 'Hasty', 'Naive'].includes(nature)) return [2, 0, 0, 32, 0, 32];
  if (nature === 'Brave') return [32, 32, 2, 0, 0, 0];
  if (nature === 'Quiet') return [32, 0, 2, 32, 0, 0];
  if (['Calm', 'Careful', 'Sassy'].includes(nature)) return [32, 0, 14, 0, 20, 0];
  return [32, 0, 20, 0, 14, 0];
}
function evsFor(species, item, nature) {
  const mega = /ite( [xyz])?$/.test(item) && !['whiteherb', 'lightclay'].includes(item);
  let key = species;
  if (mega && species === 'Garchomp') key = 'M-Garchomp Z'; else if (FOEKEY[species] && (mega || !species.startsWith('M-'))) key = FOEKEY[species];
  const f = foes[key] || foes[species];
  if (f && f[3] && f[3][0]) { const sp = f[3][0]; return sp.slice(0, 6); }
  return defaultEVs(nature);
}
function parseDist(s) {
  const out = [];
  for (const part of s.split(', ')) { const i = part.lastIndexOf(':'); const mv = part.slice(0, i), p = +part.slice(i + 1); if (mv === '(flinched)' || mv === '(none)') continue; out.push([mv, p]); }
  const tot = out.reduce((a, b) => a + b[1], 0); return out.map(([m, p]) => [m, p / tot]);
}
function oppSet(arch, sp, extraMoves) {
  const A = OPP[arch]; const raw = (A.sets[sp] || FALLBACK[sp] || '').replace(/ \(.*\)$/, '');
  if (!raw) throw new Error('no set for ' + sp);
  let [item, ability, nature, mv] = raw.split('|');
  for (const o of (process.env.ITEM_OVERRIDE || '').split(',').filter(Boolean)) { const [k, v] = o.split('='); if (k === sp) item = v; }
  const moves = [...new Set([...mv.split('/'), ...(extraMoves || []).map(toID)])];
  return {species: sp, item, ability, moves, nature, evs: evsFor(sp, item, nature), level: 50};
}
function toSet(o) { return {name: o.species, species: o.species, item: o.item, ability: o.ability, moves: o.moves, nature: o.nature, gender: '',
  evs: {hp: o.evs[0], atk: o.evs[1], def: o.evs[2], spa: o.evs[3], spd: o.evs[4], spe: o.evs[5]}, ivs: {hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31}, level: 50}; }
const isMega = (set) => { const it = dex.items.get(set.item); return !!(it.megaStone && (it.megaStone[set.species] || Object.keys(it.megaStone).some(k => set.species.startsWith(k)))); };
function primary(set) { let p = 0, s = 0; for (const m of set.moves) { const mv = dex.moves.get(m); if (mv.id === 'fakeout') continue; if (mv.category === 'Physical') p++; else if (mv.category === 'Special') s++; } return p > s ? 'atk' : s > p ? 'spa' : 'both'; }
// ---- action generation ----
const FOE_TARGETS = new Set(['normal', 'any', 'adjacentFoe']);
function typeMult(moveType, species) { const t = dex.species.get(species).types; return dex.getEffectiveness ? t.reduce((m, x) => m * (dex.getImmunity(moveType, x) ? Math.pow(2, dex.getEffectiveness(moveType, x)) : 0), 1) : 1; }
const MEGA_CHOICE = process.env.MEGA_CHOICE === '1';                  // a stone holder's moves both with and without the Mega (else always with)
function myOptions(name, pos, foeSpecies, allySpecies, backs) {
  const set = MY[name]; const out0 = [];
  const out = {push: (o) => { if (MEGA_CHOICE && o.choice.endsWith(' mega')) out0.push({label: o.label + ' (Mega)', choice: o.choice}, {label: o.label, choice: o.choice.slice(0, -5)}); else out0.push(o); }};
  if (backs) backs.forEach((bn, k) => out.push({label: `${name}: switch -> ${bn}`, choice: `switch ${3 + k}`}));
  set.moves.forEach((m, i) => { const mv = dex.moves.get(m); const slot = i + 1; const it = dex.items.get(set.item); const mega = it.megaStone && Object.keys(it.megaStone).some(k => set.species.startsWith(k)) ? ' mega' : '';
    if (mv.id === 'uturn' || mv.id === 'healingwish' || mv.id === 'memento') return;
    if (mv.target === 'adjacentAlly') { out.push({label: `${name}: ${mv.name}`, choice: `move ${slot} ${pos === 1 ? -2 : -1}${mega}`}); return; }
    if (FOE_TARGETS.has(mv.target)) {
      for (let t = 1; t <= 2; t++) { const fs = foeSpecies[t - 1]; const mt = mv.type === 'Normal' && name === 'Salamence' ? 'Flying' : mv.id === 'weatherball' && set.ability === 'Drought' ? 'Fire' : mv.type;
        const eff = typeMult(mt, dex.species.get(fs).name.replace(/-Mega.*/, '') ? fs : fs);
        if (eff === 0) continue;                                             // never click into an immunity
        if (mv.id === 'powergem' && eff < 2) continue;                       // Power Gem only where it's super effective
        if (mv.id === 'ironhead' && eff < 2) continue;
        if (mv.id === 'lowkick' && eff < 2) continue;
        if (mv.id === 'acrobatics' && eff < 1) continue;
        out.push({label: `${name}: ${mv.name} -> ${fs}`, choice: `move ${slot} ${t}${mega}`}); }
    } else out.push({label: `${name}: ${mv.name}`, choice: `move ${slot}${mega}`});
  });
  return out0;
}
function theirOptions(arch, sp, dist, foeSpecies, pos, set, megaOK) {
  // dist: [[moveName|(switch), p]] ; returns [{label, choice, group, p}] (targets are the free part of each group)
  const out = [];
  for (const [mvName, p] of dist) {
    if (p < 0.045) continue;
    if (mvName === '(switch)') { out.push({label: `${sp}: switch`, choice: 'switch 3', group: `${sp}:switch`, p}); continue; }
    const id = toID(mvName); const slot = set.moves.indexOf(id) + 1; if (slot <= 0) continue;
    const mv = dex.moves.get(id); const mega = megaOK && isMega(set) ? ' mega' : '';
    if (FOE_TARGETS.has(mv.target)) { let n = 0;
      for (let t = 1; t <= 2; t++) { const eff = typeMult(mv.type === 'Normal' && /pixilate|aerilate/.test(set.ability) ? (set.ability === 'pixilate' ? 'Fairy' : 'Flying') : mv.type, foeSpecies[t - 1]);
        if (eff === 0 && dex.moves.get(id).category !== 'Status') continue; n++;
        out.push({label: `${sp}: ${mv.name} -> ${foeSpecies[t - 1]}`, choice: `move ${slot} ${t}${mega}`, group: `${sp}:${mv.name}`, p}); }
      if (!n) out.push({label: `${sp}: ${mv.name} -> ${foeSpecies[0]}`, choice: `move ${slot} 1${mega}`, group: `${sp}:${mv.name}`, p});
    } else if (mv.target === 'adjacentAlly') out.push({label: `${sp}: ${mv.name}`, choice: `move ${slot} ${pos === 1 ? -2 : -1}${mega}`, group: `${sp}:${mv.name}`, p});
    else out.push({label: `${sp}: ${mv.name}`, choice: `move ${slot}${mega}`, group: `${sp}:${mv.name}`, p});
  }
  // renormalise group probabilities over what survived
  const groups = {}; out.forEach(o => groups[o.group] = o.p); const tot = Object.values(groups).reduce((a, b) => a + b, 0);
  out.forEach(o => o.p = o.p / tot);
  return out;
}
// ---- evaluation ----
function feats(b, prim) {
  const selfUsers = new Set(); const perish = {p1: 0, p2: 0};
  let started = false;
  for (const l of b.log) { if (l === '|turn|1') { started = true; continue; } if (!started) continue; if (l.startsWith('|move|')) { const p = l.split('|'); if (SELFDROP.has(p[3])) selfUsers.add(p[2].slice(0, 2) + ':' + p[2].slice(5)); if (p[3] === 'Perish Song') perish[p[2].slice(0, 2)] = 1; } }
  const f = {};
  for (const side of b.sides) {
    let hpLoss = 0, ko = 0, pos = 0, negO = 0, negS = 0, irr = 0, spe = 0, stat = 0;
    for (const p of side.pokemon) { hpLoss += 1 - p.hp / p.maxhp; if (p.fainted || p.hp <= 0) ko++; }
    for (const p of side.active) { if (!p || p.fainted || p.hp <= 0) continue; const pr = prim[side.id][p.set.species] || prim[side.id][p.species.baseSpecies] || 'both';
      const rel = pr === 'atk' ? p.boosts.atk : pr === 'spa' ? p.boosts.spa : Math.max(p.boosts.atk, p.boosts.spa);
      const ir = pr === 'atk' ? p.boosts.spa : pr === 'spa' ? p.boosts.atk : 0;
      if (rel > 0) pos += rel; else if (rel < 0) { if (selfUsers.has(side.id + ':' + p.name)) negS += rel; else negO += rel; }
      irr += ir; spe += p.boosts.spe; if (['par', 'slp', 'frz'].includes(p.status)) stat++; }
    const sc = side.sideConditions;
    f[side.id] = {hpLoss, ko, pos, negO, negS, irr, spe, stat, tw: sc.tailwind ? 1 : 0, scr: (sc.reflect ? 1 : 0) + (sc.lightscreen ? 1 : 0) + (sc.auroraveil ? 1 : 0), tr: 0};
  }
  if (b.field.pseudoWeather.trickroom) { const src = b.field.pseudoWeather.trickroom.source; const sid = src && src.side ? src.side.id : null;
    if (sid) f[sid].tr = 1; else { const l = b.log.filter(x => x.startsWith('|move|') && x.includes('|Trick Room|')).pop(); if (l) f[l.split('|')[2].slice(0, 2)].tr = 1; } }
  if (process.env.TW_UNDER_TR === 'zero' && b.field.pseudoWeather.trickroom) { f.p1.tw = 0; f.p2.tw = 0; }
  const a = f.p1, o = f.p2;
  const x = [o.hpLoss - a.hpLoss, o.ko - a.ko, a.pos - o.pos, a.negO - o.negO, a.negS - o.negS, a.irr - o.irr, a.spe - o.spe, a.tw - o.tw, a.tr - o.tr, a.scr - o.scr, o.stat - a.stat, perish.p1 - perish.p2];
  const z = x.reduce((t, v, k) => t + v * W2[k], 0);
  return {wp: 1 / (1 + Math.exp(-z)), f, x};
}
function sig(b) {  // battle state signature, mega formes folded into base species
  const parts = [];
  for (const side of b.sides) { for (const p of side.pokemon) parts.push(p.species.baseSpecies + ':' + p.hp + ':' + p.status + ':' + (p.isActive ? 1 : 0));
    for (const p of side.active) if (p) parts.push(JSON.stringify(p.boosts)); parts.push(Object.keys(side.sideConditions).sort().join(',')); }
  parts.push(Object.keys(b.field.pseudoWeather).sort().join(','), b.field.weather, b.field.terrain);
  return parts.join('|');
}
function runCell(myTeam, oppTeam, prim, c1, c2, seed) {
  const b = fixMegas(new Battle({formatid: 'gen9championsdoublescustomgame', seed})); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: myTeam}); b.setPlayer('p2', {name: 'Them', team: oppTeam});
  b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
  const s0 = sig(b);
  const ok1 = b.choose('p1', c1), ok2 = b.choose('p2', c2);
  if (!ok1 || !ok2) return null;
  // mid-turn (U-turn/Parting Shot/Emergency Exit) and end-of-turn (KO) replacements: first healthy bench Pokemon
  for (let guard = 0; b.turn < 2 && !b.ended && guard < 8; guard++) {
    for (const side of b.sides) if (side.requestState === 'switch' && !side.isChoiceDone()) side.autoChoose();
    if (b.allChoicesDone()) b.commitChoices(); else break;
  }
  if (b.turn < 2 && !b.ended) return null;
  const r = feats(b, prim); r.nul = sig(b) === s0; return r;
}
function build(arch, pairIdx, myLead, myBack) {
  const P = OPP[arch].pairs[pairIdx]; const theirLead = P.pair.split(' + ');
  const backs = P.back.split(', ').map(x => x.split(':')[0]).filter(x => !theirLead.includes(x));
  const dists = theirLead.map(sp => parseDist(P.t1[sp]));
  const sets = theirLead.map((sp, i) => oppSet(arch, sp, dists[i].map(x => x[0]).filter(x => !x.startsWith('('))));
  const bsets = []; for (const sp of backs) { try { bsets.push(oppSet(arch, sp, [])); } catch (e) {} if (bsets.length === 2) break; }
  const oppTeam = [...sets, ...bsets].map(toSet);
  const myTeam = [...myLead, ...myBack].map(n => toSet({...MY[n], species: MY[n].species}));
  const prim = {p1: {}, p2: {}};
  for (const n of [...myLead, ...myBack]) prim.p1[n] = primary(toSet(MY[n]));
  for (const s of [...sets, ...bsets]) prim.p2[s.species] = primary(s);
  const mine = [myOptions(myLead[0], 1, theirLead, myLead[1], myBack), myOptions(myLead[1], 2, theirLead, myLead[0], myBack)];
  const mc = theirLead.map(sp => (P.mega || {})[sp] || 0); const mi = mc[0] >= mc[1] ? 0 : 1;
  const megaOK = [0, 1].map(i => i === mi && mc[i] >= 0.3 * P.n && isMega(sets[i]));
  const theirs = [theirOptions(arch, theirLead[0], dists[0], myLead, 1, sets[0], megaOK[0]), theirOptions(arch, theirLead[1], dists[1], myLead, 2, sets[1], megaOK[1])];
  const myActs = [], thActs = [];
  for (const a of mine[0]) for (const b of mine[1]) { if (a.choice.startsWith('switch') && a.choice === b.choice) continue;
    if (a.label.endsWith(': Trick Room') && b.label.endsWith(': Trick Room')) continue;  // the second one would undo the first
    if (MEGA_CHOICE && a.choice.endsWith(' mega') && b.choice.endsWith(' mega')) continue;     // one Mega per battle
    if (a.choice.endsWith(' mega') && b.choice.endsWith(' mega')) {        // both leads hold a stone: one Mega per battle, so one or the other
      const no = (o) => o.choice.slice(0, -5), mg = (o) => o.label + ' (Mega)';   // (not Mega Evolving at all on turn one is left out)
      myActs.push({label: mg(a) + ' | ' + b.label, choice: a.choice + ', ' + no(b)}, {label: a.label + ' | ' + mg(b), choice: no(a) + ', ' + b.choice});
      continue; }
    myActs.push({label: a.label + ' | ' + b.label, choice: a.choice + ', ' + b.choice}); }
  for (const a of theirs[0]) for (const b of theirs[1]) thActs.push({label: a.label + ' | ' + b.label, choice: a.choice + ', ' + (a.choice.startsWith('switch') && b.choice.startsWith('switch') ? 'switch 4' : b.choice), group: a.group + ' | ' + b.group, p: a.p * b.p});
  return {arch, P, myLead, myBack, myActs, thActs, myTeam, oppTeam, prim, megaOK, sets, bsets};
}
function run(B, seeds) {
  const A = [], N = [], F = []; let bad = 0, wp0 = null; const koMine = [], koTheirs = [], tw = [], tr = [];
  for (const ma of B.myActs) { const row = [], nr = [], kr = [], kt = [], twr = [], trr = [], fr = [];
    for (const ta of B.thActs) { let s = 0, n = 0, k1 = 0, k2 = 0, nul = 0, a1 = 0, a2 = 0;
      const fx = [];
      for (const seed of seeds) { const r = runCell(B.myTeam, B.oppTeam, B.prim, ma.choice, ta.choice, seed); if (!r) { bad++; continue; }
        if (r.nul && wp0 === null) wp0 = r.wp;
        s += r.wp; n++; k1 += r.f.p1.ko; k2 += r.f.p2.ko; nul += r.nul ? 1 : 0; a1 += r.f.p1.tw - r.f.p2.tw; a2 += r.f.p2.tr; fx.push(r.x.map(v => +v.toFixed(3)).concat([r.nul ? 1 : 0])); }
      row.push(n ? +(s / n).toFixed(4) : null); nr.push(n ? +(nul / n).toFixed(2) : null); kr.push(n ? +(k1 / n).toFixed(2) : null); kt.push(n ? +(k2 / n).toFixed(2) : null);
      twr.push(n ? +(a1 / n).toFixed(2) : null); trr.push(n ? +(a2 / n).toFixed(2) : null); fr.push(fx); }
    A.push(row); N.push(nr); koMine.push(kr); koTheirs.push(kt); tw.push(twr); tr.push(trr); F.push(fr); }
  const P = B.P;
  return {arch: B.arch, pair: P.pair, share: P.share, n: P.n, megaOK: B.megaOK, myLead: B.myLead, myBack: B.myBack, myActs: B.myActs.map(x => x.label),
    thActs: B.thActs.map(x => ({label: x.label, group: x.group, p: +x.p.toFixed(4)})), A, N, F, wp0, koMine, koTheirs, tw, tr, bad, seeds: seeds.length,
    oppTeam: B.oppTeam.map(s => `${s.species} @ ${s.item} (${s.ability}) ${s.nature} [${s.moves.join(',')}] ${Object.values(s.evs).join('/')}`)};
}
function matchup(arch, pairIdx, myLead, myBack, seeds) { return run(build(arch, pairIdx, myLead, myBack), seeds); }
module.exports = {matchup, build, run, myOptions, theirOptions, MY, OPP, oppSet, parseDist, runCell, toSet, feats, primary, fixMegas, MEGA_ABILITY};
if (require.main === module) {
  const [arch, idx, l1, l2, b1, b2, nseed, out] = process.argv.slice(2);
  const seeds = Array.from({length: +nseed}, (_, k) => require('./seedmix.js')(k + 1));
  const t0 = Date.now();
  const r = matchup(arch, +idx, [l1, l2], [b1, b2], seeds);
  r.ms = Date.now() - t0;
  fs.writeFileSync(out, JSON.stringify(r));
  console.log(`${arch} | ${r.pair} | ${l1}+${l2}: ${r.myActs.length} x ${r.thActs.length} x ${seeds.length} in ${(r.ms / 1000).toFixed(1)}s, bad ${r.bad}`);
}
