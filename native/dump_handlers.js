const path = require('path'), fs = require('fs'); const {Dex} = require(path.resolve('node_modules/pokemon-showdown')); const dex = Dex.mod('champions');
const D = JSON.parse(fs.readFileSync('../native/champions_data.json'));
const H = /^on(BasePower|ModifyAtk|ModifySpA|ModifyDef|ModifySpD|ModifyDamage|SourceModifyDamage|AnyModifyDamage|ModifyType|ModifyMove|WeatherModifyDamage|ModifySTAB|SourceModifyAtk|SourceModifySpA|SourceBasePower|AnyBasePower|AllyBasePower|Effectiveness|Immunity|SourceModifyAccuracy|ModifyCritRatio|CriticalHit|AnyModifyAtk|AnyModifyDef|AnyModifySpA|AnyModifySpD|AllyModifyAtk|AllyModifySpA|FoeBasePower)$|^basePowerCallback$/;
let out = '';
const dump = (kind, id, obj) => { for (const k of Object.keys(obj)) if (H.test(k) && typeof obj[k] === 'function') out += `// ${kind} ${id}.${k} (prio ${obj[k + 'Priority'] ?? obj[k.replace(/^on/, 'on') + 'Priority'] ?? ''} / ${obj[k + 'Order'] ?? ''})\n${obj[k].toString()}\n\n`; };
for (const id of Object.keys(D.abilities)) dump('ability', id, dex.abilities.get(id));
for (const id of Object.keys(D.items)) dump('item', id, dex.items.get(id));
for (const id of Object.keys(D.moves)) { const m = dex.moves.get(id); dump('move', id, m); if (m.condition) dump('movecond', id, m.condition); }
for (const id of Object.keys(D.conditions)) dump('cond', id, dex.conditions.get(id));
fs.writeFileSync('../native/handlers_ref.js', out); console.log(out.length, 'chars;', (out.match(/^\/\/ /gm) || []).length, 'handlers');
