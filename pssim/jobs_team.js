// Stage-one jobs for a whole six: every lead pair vs each archetype's six most common opposing leads.
// Back row (only used for turn-one switches and the Trick Room speed credit): fill the four to both setters plus attackers,
// in each archetype's attacker preference; the same rule as jobs_tr.js and jobs_cand.js.
// usage: MYTEAM=myteam_X.json node jobs_team.js <setters, comma-separated> <out.json>
//   e.g. MYTEAM=myteam_c_incin.json node jobs_team.js Indeedee-F,Farigiraf jobs_inc1.json
const T = require('./t1sim.js'); const fs = require('fs');
const [setArg, outf] = process.argv.slice(2);
const SET = setArg.split(',');
const CORE = ['Indeedee-F', 'Hatterene', 'Farigiraf', 'Torkoal', 'Kingambit', 'Blastoise'];     // lead names keep this order ("Farigiraf+Blastoise")
const SIX = Object.keys(T.MY).filter(x => !CORE.includes(x)).concat(CORE.filter(x => x in T.MY));  // newcomers first ("Incineroar+Farigiraf")
const ATK0 = {'Rain': ['Blastoise', 'Kingambit', 'Torkoal'], 'Rain + sun': ['Kingambit', 'Blastoise', 'Torkoal'], 'Sun': ['Torkoal', 'Kingambit', 'Blastoise'],
  'Indeedee TR / Psychic Terrain': ['Kingambit', 'Torkoal', 'Blastoise'], 'Trick Room without Indeedee': ['Kingambit', 'Torkoal', 'Blastoise']};
const jobs = [];
for (const arch of Object.keys(T.OPP)) {
  const pref = (ATK0[arch] || ['Torkoal', 'Kingambit', 'Blastoise']).filter(x => SIX.includes(x) && !SET.includes(x));
  const atk = pref.concat(SIX.filter(x => !SET.includes(x) && !pref.includes(x)));
  for (let a = 0; a < 6; a++) for (let b = a + 1; b < 6; b++) {
    const lead = [SIX[a], SIX[b]]; const ns = lead.filter(x => SET.includes(x)).length;
    const back = ns >= 2 ? atk.filter(x => !lead.includes(x)).slice(0, 2) : ns === 0 ? SET.filter(x => !lead.includes(x)).slice(0, 2)
      : [SET.find(x => !lead.includes(x)), atk.find(x => !lead.includes(x))];
    const npairs = Math.min(6, T.OPP[arch].pairs.length);
    for (let k = 0; k < npairs; k++) { const B = T.build(arch, k, lead, back); jobs.push({arch, k, lead, back, pair: B.P.pair, cells: B.myActs.length * B.thActs.length}); }
  }
}
fs.writeFileSync(outf, JSON.stringify(jobs));
console.log(SIX.join(', '), '|', jobs.length, 'jobs', jobs.reduce((a, j) => a + j.cells, 0), 'cells');
