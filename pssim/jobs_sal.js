// Salamence + partner leads not yet simulated, every archetype (back row = best two of the archetype's pool that aren't leading)
const T = require('./t1sim.js'); const fs = require('fs');
const POOL = {
  'Tailwind goodstuffs': ['Gholdengo', 'Kingambit', 'Salamence', 'Incineroar', 'Rillaboom'], 'Sun': ['Gholdengo', 'Salamence', 'Incineroar', 'Sneasler'],
  'Indeedee TR / Psychic Terrain': ['Gholdengo', 'Kingambit', 'Rillaboom', 'Incineroar'], 'Rain': ['Gholdengo', 'Salamence', 'Rillaboom', 'Incineroar'],
  'Balance, no speed control': ['Salamence', 'Sneasler', 'Gholdengo', 'Incineroar', 'Rillaboom'], 'Sand': ['Kingambit', 'Gholdengo', 'Sneasler', 'Rillaboom'],
  'Snow': ['Gholdengo', 'Sneasler', 'Kingambit', 'Incineroar'], 'Trick Room without Indeedee': ['Incineroar', 'Rillaboom', 'Kingambit', 'Gholdengo'],
  'Rain + sun': ['Gholdengo', 'Salamence', 'Incineroar', 'Rillaboom'], 'Perish trap': ['Salamence', 'Incineroar', 'Kingambit', 'Gholdengo'],
};
const have = new Set(JSON.parse(fs.readFileSync('jobs_s1.json')).map(j => `${j.arch}|${[...j.lead].sort().join('+')}|${j.k}`));
const jobs = []; let cells = 0;
for (const [arch, pool] of Object.entries(POOL)) {
  for (const partner of ['Kingambit', 'Rillaboom', 'Incineroar', 'Gholdengo', 'Sneasler']) {
    const lead = ['Salamence', partner]; const back = pool.filter(x => !lead.includes(x)).slice(0, 2);
    for (let k = 0; k < 6; k++) {
      if (have.has(`${arch}|${[...lead].sort().join('+')}|${k}`)) continue;
      const B = T.build(arch, k, lead, back); const c = B.myActs.length * B.thActs.length; cells += c;
      jobs.push({arch, k, lead, back, pair: B.P.pair, cells: c});
    }
  }
}
fs.writeFileSync('jobs_sal.json', JSON.stringify(jobs));
console.log(jobs.length, 'jobs,', cells, 'cells -> ~', (cells * 5.8 / 1000 / 60 / 2).toFixed(0), 'min at 1 seed on 2 cores');
const by = {}; for (const j of jobs) { const key = j.arch + ' | ' + j.lead.join('+'); by[key] = (by[key] || 0) + 1; } console.log(Object.keys(by).join('\n'));
