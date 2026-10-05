// Pull method bodies out of Showdown's compiled sim for reference while porting. usage (from pssim/): node ../native/extract_ref.js out.js file:method ...
const fs = require('fs'), path = require('path'); const D = path.resolve('node_modules/pokemon-showdown/dist/sim');
const out = [];
for (const spec of process.argv.slice(3)) {
  const [file, name] = spec.split(':'); const src = fs.readFileSync(path.join(D, file), 'utf8').split('\n');
  const re = new RegExp(`^  (static |get )?${name}\\(`); const i = src.findIndex(l => re.test(l));
  if (i < 0) { out.push(`// NOT FOUND ${spec}`); continue; }
  let j = i + 1; while (j < src.length && !/^  }$/.test(src[j])) j++;
  out.push(`// ===== ${spec}`, ...src.slice(i, j + 1));
}
fs.writeFileSync(process.argv[2], out.join('\n') + '\n'); console.log(out.filter(l => l.startsWith('// N')).join('\n') || 'all found');
