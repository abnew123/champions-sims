// New team (Blastoise / Torkoal / Indeedee-F / Farigiraf / Kingambit / Hatterene): every lead pair vs each archetype's top-6 opposing leads.
// Back row (not simulated beyond turn-one switches): fill to two Trick Room setters + two attackers, by archetype preference.
const T = require('./t1sim.js'); const fs = require('fs');
const SET = ['Indeedee-F', 'Hatterene', 'Farigiraf'];
const ATK = {'Rain': ['Blastoise', 'Kingambit', 'Torkoal'], 'Rain + sun': ['Kingambit', 'Blastoise', 'Torkoal'], 'Sun': ['Torkoal', 'Kingambit', 'Blastoise'],
  'Indeedee TR / Psychic Terrain': ['Kingambit', 'Torkoal', 'Blastoise'], 'Trick Room without Indeedee': ['Kingambit', 'Torkoal', 'Blastoise']};
const SIX = ['Indeedee-F', 'Hatterene', 'Farigiraf', 'Torkoal', 'Kingambit', 'Blastoise'];
const jobs = []; let cells = 0; const by = {};
for (const arch of Object.keys(T.OPP)) {
  const atk = ATK[arch] || ['Torkoal', 'Kingambit', 'Blastoise'];
  for (let a = 0; a < 6; a++) for (let b = a + 1; b < 6; b++) {
    const lead = [SIX[a], SIX[b]]; const ns = lead.filter(x => SET.includes(x)).length;
    const back = ns === 2 ? atk.slice(0, 2) : ns === 0 ? SET.slice(0, 2) : [SET.find(x => !lead.includes(x)), atk.find(x => !lead.includes(x))];
    const npairs = Math.min(6, T.OPP[arch].pairs.length);
    for (let k = 0; k < npairs; k++) { const B = T.build(arch, k, lead, back); const c = B.myActs.length * B.thActs.length; cells += c; by[arch] = (by[arch] || 0) + c;
      jobs.push({arch, k, lead, back, pair: B.P.pair, cells: c}); }
  }
}
fs.writeFileSync('jobs_tr1.json', JSON.stringify(jobs));
console.log(jobs.length, 'jobs', cells, 'cells -> ~', (cells * 4.0 / 1000 / 60 / 2).toFixed(0), 'min per seed on 2 cores');
console.log(by);
console.log(jobs.sort((x, y) => y.cells - x.cells).slice(0, 4).map(j => `${j.arch} | ${j.pair} | ${j.lead} ${j.cells}`));
const B2 = T.build('Rain', 0, ['Blastoise', 'Farigiraf'], ['Torkoal', 'Kingambit']); console.log(B2.myActs.slice(20, 24).map(a => a.label + ' => ' + a.choice));
