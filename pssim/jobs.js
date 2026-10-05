// build the job list: every lead pair from each archetype's bring pool vs that archetype's top-6 opposing lead pairs
const T = require('./t1sim.js'); const fs = require('fs');
const POOL = {  // bring pool, ordered by that archetype's grid score (back row = best two of the rest)
  'Tailwind goodstuffs': ['Gholdengo', 'Kingambit', 'Salamence', 'Incineroar', 'Rillaboom'],
  'Sun': ['Gholdengo', 'Salamence', 'Incineroar', 'Sneasler'],
  'Indeedee TR / Psychic Terrain': ['Gholdengo', 'Kingambit', 'Rillaboom', 'Incineroar'],
  'Rain': ['Gholdengo', 'Salamence', 'Rillaboom', 'Incineroar'],
  'Balance, no speed control': ['Salamence', 'Sneasler', 'Gholdengo', 'Incineroar', 'Rillaboom'],
  'Sand': ['Kingambit', 'Gholdengo', 'Sneasler', 'Rillaboom'],
  'Snow': ['Gholdengo', 'Sneasler', 'Kingambit', 'Incineroar'],
  'Trick Room without Indeedee': ['Incineroar', 'Rillaboom', 'Kingambit', 'Gholdengo'],
  'Rain + sun': ['Gholdengo', 'Salamence', 'Incineroar', 'Rillaboom'],
  'Perish trap': ['Salamence', 'Incineroar', 'Kingambit', 'Gholdengo'],
};
const jobs = []; let cells = 0;
for (const [arch, pool] of Object.entries(POOL)) {
  const npairs = Math.min(6, T.OPP[arch].pairs.length);
  for (let i = 0; i < pool.length; i++) for (let j = i + 1; j < pool.length; j++) {
    const lead = [pool[i], pool[j]]; const back = pool.filter(x => !lead.includes(x)).slice(0, 2);
    for (let k = 0; k < npairs; k++) { const B = T.build(arch, k, lead, back); const c = B.myActs.length * B.thActs.length; cells += c;
      jobs.push({arch, k, lead, back, cells: c, pair: B.P.pair}); }
  }
}
fs.writeFileSync('jobs.json', JSON.stringify(jobs));
console.log(jobs.length, 'jobs', cells, 'cells; est min per seed on 2 cores', (cells * 4.4 / 1000 / 60 / 2).toFixed(1));
const by = {}; for (const j of jobs) by[j.arch] = (by[j.arch] || 0) + j.cells; console.log(by);
console.log(jobs.sort((a, b) => b.cells - a.cells).slice(0, 5).map(j => `${j.arch} ${j.pair} ${j.lead} ${j.cells}`));
