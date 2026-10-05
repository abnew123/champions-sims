const {chromium} = require('playwright'); const fs = require('fs');
(async () => {
  const body = fs.readFileSync('tr-sheet.html', 'utf8');
  fs.writeFileSync('preview.html', '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>' + body + '</body></html>');
  const b = await chromium.launch(); const errs = [];
  for (const [w, h, scheme, name] of [[1200, 900, 'light', 'desk-light'], [390, 844, 'dark', 'phone-dark']]) {
    const p = await b.newPage({viewport: {width: w, height: h}, colorScheme: scheme}); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); }); p.on('pageerror', e => errs.push(String(e)));
    await p.goto('file://' + process.cwd() + '/preview.html'); await p.waitForTimeout(800);
    const ov = await p.evaluate(() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, h: document.documentElement.scrollHeight}));
    console.log(name, JSON.stringify(ov));
    await p.screenshot({path: `${name}.png`, fullPage: true}); await p.close();
  }
  console.log('errors', errs.length ? errs : 'none'); await b.close();
})();
