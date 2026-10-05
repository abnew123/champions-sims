// v4 checks: leads tabs still work; Coverage and Matchups render, toggle, expand; no page overflow; screenshots of the new sections.
const {chromium} = require('playwright'); const fs = require('fs');
(async () => {
  const src = process.argv[2] || 'tr-sheet.html'; const body = fs.readFileSync(src, 'utf8');
  fs.writeFileSync('verify.html', '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>[hidden]{display:none!important}</style></head><body>' + body + '</body></html>');
  const b = await chromium.launch(); const errs = [];
  for (const [w, h, scheme, name] of [[1200, 900, 'light', 'v4-desk-light'], [390, 844, 'dark', 'v4-phone-dark'], [340, 740, 'light', 'v4-narrow-light']]) {
    const p = await b.newPage({viewport: {width: w, height: h}, colorScheme: scheme});
    p.on('pageerror', e => errs.push(name + ': ' + e)); p.on('console', m => { if (m.type() === 'error' && !/fonts|ERR_TUNNEL|net::/.test(m.text())) errs.push(name + ': ' + m.text()); });
    await p.goto('file://' + process.cwd() + '/verify.html'); await p.waitForTimeout(400);
    const ov = () => p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    const tabs = await p.$$eval('.lseg', xs => xs.map(x => x.dataset.k)); let bad = [];
    for (const k of tabs) { await p.click(`.lseg[data-k="${k}"]`); if (!(await p.$$eval('#lpanel .lline, #lpanel .lgen', xs => xs.length))) bad.push(k); }
    const info = await p.evaluate(() => {
      const q = s => document.querySelector(s), box = el => el.closest('.tscroll');
      const cov = q('#covbody'), mx = q('#mxbody');
      return {covRows: cov.querySelectorAll('tr.xrow').length, covDet: cov.querySelectorAll('tr.xdet[hidden]').length,
        mxRows: mx.querySelectorAll('tr.xrow').length, mxCells: mx.querySelectorAll('tr.xrow .mx').length,
        covScroll: box(cov).scrollWidth - box(cov).clientWidth, mxScroll: box(mx).scrollWidth - box(mx).clientWidth,
        tally: q('#mxtally').textContent, jump: [...document.querySelectorAll('.jump a')].map(a => a.textContent).join(','),
        firstCov: cov.querySelector('tr.xrow').textContent, attackers: !!q('#attackers')};
    });
    await p.click('#covbody tr.xrow'); const covOpen = await p.$eval('#cd0', d => !d.hidden && d.textContent);
    await p.click('#mxbody tr.xrow:nth-of-type(3)'); const mxOpen = await p.$$eval('#mxbody tr.xdet', ds => ds.filter(d => !d.hidden).map(d => d.id + ': ' + d.textContent.slice(0, 160)));
    const trCounts = await p.$$eval('#mxbody .mx', xs => xs.map(x => x.className.split(' ')[1]).join(''));
    await p.click('.mxm[data-tr="0"]'); const tally0 = await p.$eval('#mxtally', t => t.textContent);
    const noTrCounts = await p.$$eval('#mxbody .mx', xs => xs.map(x => x.className.split(' ')[1]).join(''));
    const sel = await p.$$eval('.mxm', xs => xs.map(x => x.dataset.tr + ':' + x.getAttribute('aria-selected')).join(' '));
    // keyboard: focus first coverage row, Enter closes it again
    await p.focus('#covbody tr.xrow'); await p.keyboard.press('Enter'); const covClosed = await p.$eval('#cd0', d => d.hidden);
    console.log(`== ${name}: page overflow ${await ov()} | leads tabs ${tabs.length}${bad.length ? ' EMPTY ' + bad : ''} | #attackers ${info.attackers}`);
    console.log(`   jump: ${info.jump}`);
    console.log(`   coverage rows ${info.covRows} (hidden details ${info.covDet}), inner scroll ${info.covScroll}; first: ${info.firstCov}`);
    console.log(`   cov row 0 opened: ${covOpen && covOpen.slice(0, 200)} | closes on Enter: ${covClosed}`);
    console.log(`   matchup rows ${info.mxRows}, cells ${info.mxCells}, inner scroll ${info.mxScroll}`);
    console.log(`   TR tally: ${info.tally}`); console.log(`   no-TR tally: ${tally0} | toggle ${sel} | grids differ: ${trCounts !== noTrCounts}`);
    console.log(`   opened: ${mxOpen.join(' || ')}`);
    await p.click('.mxm[data-tr="1"]');
    for (const id of ['coverage', 'matchups']) { const el = await p.$('#' + id); await el.screenshot({path: `${name}-${id}.png`}); }
    await p.close();
  }
  console.log('errors:', errs.length ? errs : 'none'); await b.close();
})();
