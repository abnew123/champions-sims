// Well-mixed Gen5 seeds. Varying only the first 16-bit word (as [k, c1, c2, c3]) leaves the low 48 bits of the LCG
// state identical across "seeds", so some draws barely vary between runs. Hash all four words instead.
const crypto = require('crypto');
module.exports = s => { const h = crypto.createHash('sha256').update('pssim-seed-' + s).digest(); return [h.readUInt16BE(0), h.readUInt16BE(2), h.readUInt16BE(4), h.readUInt16BE(6)]; };
