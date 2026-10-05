# Readable dump of the leads data, for writing the rule under each lead.
import json, re
D = json.load(open('tr_leads_data.json'))
strip = lambda x: re.sub(r'<[^>]+>', '', x).replace('&rarr;', '->')
for t in D:
    print(f"\n######## {t['tab']} ({t['k']})")
    for p in t['picks']:
        print(f"== {p.get('when', '')} {' + '.join(p['lead'])} | back {p['back']} | v {p['v']} | top {p['top']} | TR {p['tr']}%")
        for n, sh, v, ls in p['vs']:
            print(f"   vs {n:30s} {sh:5.1f}%  {v[0]}/{v[1]}  " + ' ;; '.join(f"{l[0]}% {strip(l[1])} | {strip(l[2])}" for l in ls))
