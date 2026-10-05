// Every lead pair from the six that stage 1 never simulated, per archetype (back row = first two of the archetype's pool, then the rest of the six)
const T = require('./t1sim.js'); const fs = require('fs');
const SIX = ['Salamence', 'Kingambit', 'Rillaboom', 'Incineroar', 'Gholdengo', 'Sneasler'];
const POOL = {
  'Tailwind goodstuffs': ['Gholdengo', 'Kingambit', 'Salamence', 'Incineroar', 'Rillaboom'], 'Sun': ['Gholdengo', 'Salamence', 'Incineroar', 'Sneasler'],
  'Indeedee TR / Psychic Terrain': ['Gholdengo', 'Kingambit', 'Rillaboom', 'Incineroar'], 'Rain': ['Gholdengo', 'Salamence', 'Rillaboom', 'Incineroar'],
  'Balance, no speed control': ['Salamence', 'Sneasler', 'Gholdengo', 'Incineroar', 'Rillaboom'], 'Sand': ['Kingambit', 'Gholdengo', 'Sneasler', 'Rillaboom'],
  'Snow': ['Gholdengo', 'Sneasler', 'Kingambit', 'Incineroar'], 'Trick Room without Indeedee': ['Incineroar', 'Rillaboom', 'Kingambit', 'Gholdengo'],
  'Rain + sun': ['Gholdengo', 'Salamence', 'Incineroar', 'Rillaboom'], 'Perish trap': ['Salamence', 'Incineroar', 'Kingambit', 'Gholdengo'],
};
const done = [...JSON.parse(fs.readFileSync('jobs_s1.json')), ...JSON.parse(fs.readFileSync('jobs_sal.json'))];
const have = new Set(done.map(j => `${j.arch}|${[...j.lead].sort().join('+')}|${j.k}`));
const jobs = []; let cells = 0; const by = {};
for (const [arch, pool] of Object.entries(POOL)) {
  const order = [...pool, ...SIX.filter(x => !pool.includes(x))];
  for (let a = 0; a < 6; a++) for (let b = a + 1; b < 6; b++) {
    const lead = [SIX[a], SIX[b]]; const back = order.filter(x => !lead.includes(x)).slice(0, 2);
    for (let k = 0; k < 6; k++) {
      if (have.has(`${arch}|${[...lead].sort().join('+')}|${k}`)) continue;
      const B = T.build(arch, k, lead, back); const c = B.myActs.length * B.thActs.length; cells += c;
      jobs.push({arch, k, lead, back, pair: B.P.pair, cells: c});
      by[arch] = by[arch] || new Set(); by[arch].add(lead.join('+'));
    }
  }
}
fs.writeFileSync('jobs_miss.json', JSON.stringify(jobs));
console.log(jobs.length, 'jobs,', cells, 'cells -> ~', (cells * 5.8 / 1000 / 60 / 2).toFixed(0), 'min at 1 seed on 2 cores');
for (const [a, s] of Object.entries(by)) console.log(a.padEnd(30), s.size, [...s].join(', '));
