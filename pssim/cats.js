const {Dex} = require('pokemon-showdown'); const d = Dex.mod('champions');
const ids = process.argv[2].split(',');
const P = [], S = [];
for (const id of ids) { const m = d.moves.get(id); if (!m.exists) continue; if (m.category === 'Physical') P.push(id); else if (m.category === 'Special') S.push(id); }
console.log(JSON.stringify({P: P.join(','), S: S.join(',')}));
