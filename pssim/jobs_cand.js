// Stage-one jobs for a sixth-slot candidate: every lead pair that includes it, vs each archetype's top-6 opposing leads.
// node jobs_cand.js <Name> <isSetter 0/1> <out.json>   (run with MYTEAM pointing at the candidate team)
const T = require('./t1sim.js'); const fs = require('fs');
const [X, isSet, outf] = process.argv.slice(2);
const SET = ['Indeedee-F', 'Farigiraf'].concat(isSet === '1' ? [X] : []);
const ATK0 = {'Rain': ['Blastoise', 'Kingambit', 'Torkoal'], 'Rain + sun': ['Kingambit', 'Blastoise', 'Torkoal'], 'Sun': ['Torkoal', 'Kingambit', 'Blastoise'],
  'Indeedee TR / Psychic Terrain': ['Kingambit', 'Torkoal', 'Blastoise'], 'Trick Room without Indeedee': ['Kingambit', 'Torkoal', 'Blastoise']};
const OTHERS = Object.keys(T.MY).filter(x => x !== X);                   // the five it would join (MYTEAM's other members)
const jobs = [];
for (const arch of Object.keys(T.OPP)) {
  const atk = (ATK0[arch] || ['Torkoal', 'Kingambit', 'Blastoise']).concat(isSet === '1' ? [] : [X]);
  for (const Y of OTHERS) {
    const lead = [X, Y]; const ns = lead.filter(x => SET.includes(x)).length;
    const back = ns === 2 ? atk.filter(x => !lead.includes(x)).slice(0, 2) : ns === 0 ? SET.filter(x => !lead.includes(x)).slice(0, 2)
      : [SET.find(x => !lead.includes(x)), atk.find(x => !lead.includes(x))];
    const npairs = Math.min(6, T.OPP[arch].pairs.length);
    for (let k = 0; k < npairs; k++) { const B = T.build(arch, k, lead, back); jobs.push({arch, k, lead, back, pair: B.P.pair, cells: B.myActs.length * B.thActs.length}); }
  }
}
fs.writeFileSync(outf, JSON.stringify(jobs)); console.log(X, jobs.length, 'jobs', jobs.reduce((a, j) => a + j.cells, 0), 'cells');
console.log(jobs.slice(0, 3).map(j => `${j.arch} | ${j.pair} | ${j.lead} back ${j.back}`).join('\n'));
