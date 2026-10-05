"""Sheet Version 14 (2026-10-04): picks re-checked against all 90 fours (bring matrix, real sets) and confirmed on fresh games
(bringmx_confirm.py decide -> bringcf_picks.json). Indeedee TR gets a new four (Farigiraf+Kingambit / Blastoise+Incineroar); every tab's
whole-game % is now the fresh-game number with the real sets. Turn-one lines from tr_final_v14plus.json (v11plus + the new Indeedee TR lead,
refined with the real sets). Only the page's `const L=[...]` data is spliced into the published v13 page.
usage (from the project root): python3 pssim/build_sheet_v14.py <scratch dir>"""
import json, re, os, sys, subprocess, shutil
S = sys.argv[1]
ORDER = ['Incineroar', 'Indeedee-F', 'Hatterene', 'Farigiraf', 'Torkoal', 'Kingambit', 'Blastoise']      # tr_final lead naming order
F = json.load(open('pssim/bringcf_picks.json'))
O = {a: {'lead': '+'.join(sorted(p['lead'], key=ORDER.index)), 'back': p['back'], 'fbw': round(100 * p['v'])} for a, p in F.items()}
json.dump(O, open('pssim/lead_override_v14.json', 'w'), indent=1)
env = dict(os.environ, LEAD_OVERRIDE='pssim/lead_override_v14.json', SHOW_PLAN='0', TEAM_NOTE='', READER_W='0.75', BACK_FILE='pssim/eg_final_summary.json',
           TRMULT_FILE='pssim/trmult_final.json', TRUP_FILE='pssim/trup_v11.json')
shutil.copy('tr_leads_data.json', S + '/tr_leads_data_before.json')
subprocess.run(['python3', 'tr_leads.py', 'pssim/tr_final_v14plus.json', 'trsheet/tr-sheet.html', S + '/v14.html'], env=env, check=True, stdout=open(S + '/v14.log', 'w'))
shutil.copy('tr_leads_data.json', 'pssim/tr_leads_data_v14.json'); shutil.copy(S + '/tr_leads_data_before.json', 'tr_leads_data.json')
pub = open('trsheet/tr-sheet.html').read(); new = open(S + '/v14.html').read()
L = re.search(r'const L=\[.*?\n\];', new, re.S).group(0)
out, n = re.subn(r'const L=\[.*?\n\];', lambda m: L, pub, count=1, flags=re.S); assert n == 1
shutil.copy('trsheet/tr-sheet.html', 'trsheet/tr-sheet.v13.html')
open('trsheet/tr-sheet.html', 'w').write(out)
print('written; picks:'); [print(' ', a, O[a]) for a in O]
