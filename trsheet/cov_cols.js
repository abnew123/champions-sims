const {chromium} = require('playwright'); const fs = require('fs');
(async () => {
  const b = await chromium.launch();
  for (const f of process.argv.slice(2)) {
    const body = fs.readFileSync(f, 'utf8');
    fs.writeFileSync('verify_n.html', '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>[hidden]{display:none!important}</style></head><body>' + body + '</body></html>');
    const p = await b.newPage({viewport: {width: 340, height: 740}});
    await p.goto('file://' + process.cwd() + '/verify_n.html'); await p.waitForTimeout(300);
    const r = await p.evaluate(() => { const t = document.querySelector('table.cov'), box = t.closest('.tscroll');
      const ths = [...t.querySelectorAll('thead th')].map(th => Math.round(th.getBoundingClientRect().width));
      let widest = null; for (const tr of t.querySelectorAll('#covbody tr.xrow')) { for (const [i, td] of [...tr.children].entries()) { if (td.scrollWidth > td.clientWidth + 1) widest = [i, td.textContent, td.scrollWidth, td.clientWidth]; } }
      return {box: [box.scrollWidth, box.clientWidth], ths, over: widest}; });
    console.log(f, JSON.stringify(r)); await p.close();
  }
  await b.close(); })();
