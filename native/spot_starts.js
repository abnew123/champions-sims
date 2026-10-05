// Mid-game positions for decision review (champ spot): each spot is a moment from a recorded game (recordings/<batch>/spots.json),
// rebuilt in Showdown (teams in brought order, leads first; HP, boosts, Mega Evolution, fainted Pokemon, volatiles, field) and exported.
// My sets come from MYTEAM; theirs from Smogon's M-C sets (regionals/smogon_mc_sets.json) with what the game revealed laid on top.
// usage (from pssim/): MYTEAM=myteam_c_incin.json node ../native/spot_starts.js <spots.json> <out.jsonl>
const path = require('path'), fs = require('fs');
const {Battle, Dex} = require(path.resolve('node_modules/pokemon-showdown')); const dex = Dex.mod('champions');
const T = require(path.resolve('t1sim.js'));
const {exportState} = require(path.resolve(__dirname, 'export_state.js'));
const SM = JSON.parse(fs.readFileSync('../regionals/smogon_mc_sets.json'));
const toID = s => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const [spotf, outf] = process.argv.slice(2);
const out = fs.createWriteStream(outf);
const theirSet = x => {
  // "from": which Smogon entry to start from (e.g. Tyranitar-Mega for a Tyranitar holding its stone); the species stays the base forme
  const base = SM[x.from || x.species] || SM[x.species]; if (!base) throw new Error('no Smogon set for ' + x.species);
  const s = {...base, ...x, species: x.species};
  return T.toSet({species: s.species, item: s.item, ability: s.ability, moves: s.moves, nature: s.nature, evs: s.evs});
};
for (const sp of JSON.parse(fs.readFileSync(spotf))) {
  const mine = sp.mine.map(x => T.toSet({...T.MY[x.set], species: T.MY[x.set].species}));
  const theirs = sp.theirs.map(theirSet);
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [1, 2, 3, 4]}); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: mine}); b.setPlayer('p2', {name: 'Them', team: theirs});
  b.choose('p1', 'team 1234'.slice(0, 5 + mine.length - 1)); b.choose('p2', 'team 1234'.slice(0, 5 + theirs.length - 1));
  [sp.mine, sp.theirs].forEach((specs, si) => {
    const side = b.sides[si];
    specs.forEach((x, k) => {
      const p = side.pokemon[k];
      if (x.mega) { b.actions.runMegaEvo(p); for (const q of side.pokemon) q.canMegaEvo = false; }
      if (x.fainted) { p.hp = 0; p.fainted = true; p.status = 'fnt'; side.pokemonLeft--; side.totalFainted++; return; }
      if (x.hp !== undefined) p.hp = x.hp; else if (x.hpPct !== undefined) p.hp = Math.max(1, Math.round(p.maxhp * x.hpPct / 100));
      if (x.boosts) Object.assign(p.boosts, x.boosts);
      if (x.status) p.status = x.status;
      if (x.noItem) { p.lastItem = p.item; p.item = ''; }
      if (x.moved) { p.activeMoveActions = Math.max(1, p.activeMoveActions); p.activeTurns = Math.max(1, p.activeTurns); }
      for (const v of x.volatiles || []) p.addVolatile(v);
    });
  });
  const f = sp.field || {};
  if (f.clearTerrain) b.field.clearTerrain();
  if (f.terrain) { b.field.setTerrain(f.terrain[0], b.sides[1].active[0]); b.field.terrainState.duration = f.terrain[1]; }
  if (f.trickroom) { b.field.addPseudoWeather('trickroom', b.sides[0].active[0]); b.field.pseudoWeather.trickroom.duration = f.trickroom; }
  if (f.weather) { b.field.setWeather(f.weather[0], b.sides[1].active[0]); b.field.weatherState.duration = f.weather[1]; }
  // the choice actually made, as the engine's PChoice: [move index, target loc, mega] or ['switch', team position]
  const actual = sp.actual.map((a, i) => {
    if (a.switch) return ['switch', b.sides[0].pokemon.findIndex(p => p.species.baseSpecies === dex.species.get(a.switch).baseSpecies)];
    const p = b.sides[0].active[i]; const k = p.moveSlots.findIndex(m => m.id === toID(a.move));
    if (k < 0) throw new Error(`${sp.name}: ${p.name} has no ${a.move}`);
    const t = a.target ? 1 + b.sides[1].active.findIndex(q => q.species.baseSpecies === dex.species.get(a.target).baseSpecies) : 0;
    return [k, t, !!a.mega];
  });
  // what the opponent actually clicked (optional): always among the replies the review plays out
  const theirActual = sp.their_actual ? sp.their_actual.map((a, i) => {
    if (a.switch) return ['switch', b.sides[1].pokemon.findIndex(p => p.species.baseSpecies === dex.species.get(a.switch).baseSpecies)];
    const p = b.sides[1].active[i]; const k = p.moveSlots.findIndex(m => m.id === toID(a.move));
    if (k < 0) throw new Error(`${sp.name}: their ${p.name} has no ${a.move}`);
    const t = a.target ? 1 + b.sides[0].active.findIndex(q => q.species.baseSpecies === dex.species.get(a.target).baseSpecies) : a.ally ? (i === 0 ? -2 : -1) : 0;
    return [k, t, !!a.mega];
  }) : null;
  const st = exportState(b);
  out.write(JSON.stringify({name: sp.name, note: sp.note || '', actual, their_actual: theirActual, state: st}) + '\n');
  const desc = s => s.pokemon.map(p => `${p.species.name}${p.isActive ? '*' : ''} ${p.hp}/${p.maxhp}${Object.entries(p.boosts).filter(e => e[1]).map(e => ` ${e[0]}${e[1] > 0 ? '+' : ''}${e[1]}`).join('')}`).join(', ');
  console.log(`${sp.name}: me ${desc(b.sides[0])} | them ${desc(b.sides[1])} | terrain ${b.field.terrain || '-'} weather ${b.field.weather || '-'} TR ${b.field.pseudoWeather.trickroom ? b.field.pseudoWeather.trickroom.duration : '-'} | actual ${JSON.stringify(actual)}`);
}
out.end();
