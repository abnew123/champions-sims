// Render the sheet at phone and desktop widths, click through every Leads tab, report overflow, empty panels and script errors.
const {chromium} = require('playwright'); const fs = require('fs');
(async () => {
  const src = process.argv[2] || 'tr-sheet.html'; const body = fs.readFileSync(src, 'utf8');
  fs.writeFileSync('verify.html', '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>' + body + '</body></html>');
  const b = await chromium.launch(); const errs = [];
  for (const [w, h, scheme, name] of [[1200, 900, 'light', 'v-desk-light'], [390, 844, 'dark', 'v-phone-dark']]) {
    const p = await b.newPage({viewport: {width: w, height: h}, colorScheme: scheme});
    p.on('pageerror', e => errs.push(name + ': ' + e)); p.on('console', m => { if (m.type() === 'error' && !/fonts|ERR_TUNNEL/.test(m.text())) errs.push(name + ': ' + m.text()); });
    await p.goto('file://' + process.cwd() + '/verify.html'); await p.waitForTimeout(500);
    const tabs = await p.$$eval('.lseg', xs => xs.map(x => x.dataset.k));
    const res = [];
    for (const k of tabs) { await p.click(`.lseg[data-k="${k}"]`); const n = await p.$$eval('#lpanel .lpick', xs => xs.length); const lines = await p.$$eval('#lpanel .lline', xs => xs.length);
      const ov = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth); res.push(`${k}:${n}p/${lines}l${ov > 0 ? ' OVERFLOW ' + ov : ''}`); }
    console.log(name, tabs.length, 'tabs', res.join(' '));
    await p.click('.lseg[data-k="tw"]').catch(() => {}); await p.screenshot({path: name + '.png', fullPage: false}); await p.close();
  }
  console.log('errors:', errs.length ? errs : 'none'); await b.close();
})();
