const P = 'pokemon-showdown/dist/data/';
const npm = {abilities: require(P + 'mods/champions/abilities.js').Abilities, items: require(P + 'mods/champions/items.js').Items, moves: require(P + 'mods/champions/moves.js').Moves,
  scripts: require(P + 'mods/champions/scripts.js').Scripts, rulesets: require(P + 'mods/champions/rulesets.js').Rulesets, fdata: require(P + 'mods/champions/formats-data.js').FormatsData,
  pokedex: require(P + 'pokedex.js').Pokedex, basemoves: require(P + 'moves.js').Moves};
const live = {abilities: require('./live/data_mods_champions_abilities.js').Abilities, items: require('./live/data_mods_champions_items.js').Items, moves: require('./live/data_mods_champions_moves.js').Moves,
  scripts: require('./live/data_mods_champions_scripts.js').Scripts, rulesets: require('./live/champ_rulesets.js').Rulesets, fdata: require('./live/champ_formats-data.js').FormatsData,
  pokedex: require('./live/pokedex.js').Pokedex, basemoves: require('./live/moves.js').Moves};
const ser = v => typeof v === 'function' ? v.toString().replace(/\s+/g, ' ') : JSON.stringify(v);
for (const k of Object.keys(npm)) {
  const a = npm[k] || {}, b = live[k] || {};
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]); const diffs = [];
  for (const key of keys) { if (!(key in a)) { diffs.push('+live only: ' + key); continue; } if (!(key in b)) { diffs.push('-npm only: ' + key); continue; }
    const fa = a[key], fb = b[key];
    if (typeof fa === 'object' && fa && typeof fb === 'object' && fb) { const sub = new Set([...Object.keys(fa), ...Object.keys(fb)]); const d = [];
      for (const s of sub) if (ser(fa[s]) !== ser(fb[s])) d.push(s + ': ' + (ser(fa[s]) || '').slice(0, 90) + ' => ' + (ser(fb[s]) || '').slice(0, 90));
      if (d.length) diffs.push(key + ' {' + d.join(' | ') + '}'); }
    else if (ser(fa) !== ser(fb)) diffs.push(key + ': changed'); }
  const rel = k === 'pokedex' ? diffs.filter(x => /mega|raichu|froslass|golisopod|floette|garchomp|salamence|staraptor|sneasler|kingambit|gholdengo|rillaboom|incineroar|farigiraf|indeedee|torkoal|pelipper|arcanine|archaludon|basculegion|charizard|tyranitar|excadrill|gengar|politoed|whimsicott|metagross|gardevoir|sylveon|milotic|venusaur|swampert|aerodactyl/.test(x)) : k === 'basemoves' ? diffs.filter(x => /^(fakeout|protect|perishsong|trickroom|tailwind|followme|electroshot|expandingforce|kowtowcleave|makeitrain|grassyglide|suckerpunch|auroraveil|partingshot|uturn|hypervoice|heatwave|eruption|weatherball|blizzard|zapcannon|nastyplot|closecombat|direclaw|woodhammer|flareblitz|throatchop|doubleedge|drillrun|firstimpression)\b/.test(x)) : diffs;
  console.log(`== ${k}: ${diffs.length} diffs` + (rel.length !== diffs.length ? ` (${rel.length} relevant shown)` : '')); rel.slice(0, 40).forEach(x => console.log('  ' + x.slice(0, 400)));
}
