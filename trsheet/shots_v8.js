const {chromium} = require('playwright'); const fs = require('fs');
(async () => {
  const body = fs.readFileSync(process.argv[2], 'utf8');
  fs.writeFileSync('verify_s.html', '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>[hidden]{display:none!important}</style></head><body>' + body + '</body></html>');
  const b = await chromium.launch();
  for (const [w, scheme, tag] of [[390, 'dark', 'phone'], [1200, 'light', 'desk']]) {
    const p = await b.newPage({viewport: {width: w, height: 900}, colorScheme: scheme});
    await p.goto('file://' + process.cwd() + '/verify_s.html'); await p.waitForTimeout(300);
    for (const k of ['tw', 'indeedee']) { await p.click(`.lseg[data-k="${k}"]`); const el = await p.$('#leads'); await el.screenshot({path: `v8-${tag}-leads-${k}.png`}); }
    const cards = await p.$$('#teamgrid .mon'); await cards[cards.length - 1].screenshot({path: `v8-${tag}-inccard.png`});
    const sp = await p.$('#speed'); await sp.screenshot({path: `v8-${tag}-speed.png`});
    await p.close();
  }
  await b.close(); console.log('shots done');
})();
