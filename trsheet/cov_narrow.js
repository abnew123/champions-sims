const {chromium} = require('playwright'); const fs = require('fs');
(async () => {
  const body = fs.readFileSync(process.argv[2], 'utf8');
  fs.writeFileSync('verify_n.html', '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>[hidden]{display:none!important}</style></head><body>' + body + '</body></html>');
  const b = await chromium.launch(); const p = await b.newPage({viewport: {width: 340, height: 740}});
  await p.goto('file://' + process.cwd() + '/verify_n.html'); await p.waitForTimeout(300);
  const r = await p.evaluate(() => { const rows = [...document.querySelectorAll('#covbody tr.xrow')];
    return rows.map(tr => [tr.scrollWidth, tr.querySelector('td.hit').textContent, tr.querySelector('td.hit').scrollWidth]).sort((a, b) => b[2] - a[2]).slice(0, 5); });
  console.log(JSON.stringify(r)); await b.close(); })();
