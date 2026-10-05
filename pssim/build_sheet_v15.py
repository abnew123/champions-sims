"""Sheet Version 15 (2026-10-04): the same picks as v14 (bringcf_picks.json), with every tab's turn-one lines re-run with the real sets
(myteam_real.json: Brave Kingambit, Torkoal 12/0/0/32/22/0) and each tab's planned back row (tr_final_v15plus.json; v15_run.sh), and the team
card's Torkoal updated to 12 HP / 32 SpA / 22 SpD. Only the page's `const L=[...]` and the Torkoal card entry change.
usage (from the project root): python3 pssim/build_sheet_v15.py <scratch dir>"""
import json, re, os, sys, subprocess, shutil
S = sys.argv[1]
env = dict(os.environ, LEAD_OVERRIDE='pssim/lead_override_v14.json', SHOW_PLAN='0', TEAM_NOTE='', READER_W='0.75', BACK_FILE='pssim/eg_final_summary.json',
           TRMULT_FILE='pssim/trmult_final.json', TRUP_FILE='pssim/trup_v11.json')
shutil.copy('tr_leads_data.json', S + '/tr_leads_data_before.json')
subprocess.run(['python3', 'tr_leads.py', 'pssim/tr_final_v15plus.json', 'trsheet/tr-sheet.html', S + '/v15.html'], env=env, check=True, stdout=open(S + '/v15.log', 'w'))
shutil.copy('tr_leads_data.json', 'pssim/tr_leads_data_v15.json'); shutil.copy(S + '/tr_leads_data_before.json', 'tr_leads_data.json')
pub = open('trsheet/tr-sheet.html').read(); new = open(S + '/v15.html').read()
L = re.search(r'const L=\[.*?\n\];', new, re.S).group(0)
out, n = re.subn(r'const L=\[.*?\n\];', lambda m: L, pub, count=1, flags=re.S); assert n == 1
# team card: Torkoal's spread (stats from the engine: 157 HP / 112 SpD, was 177 / 92)
old = 'nat:"Quiet",sp:[32,0,0,32,2,0],st:[177,105,160,150,92,36]'
assert out.count(old) == 1; out = out.replace(old, 'nat:"Quiet",sp:[12,0,0,32,22,0],st:[157,105,160,150,112,36]')
old = 'src:"Most common spread, 48% on the Showdown ladder."'
assert out.count(old) == 1
out = out.replace(old, 'src:"Points moved from HP to Special Defense: its Defense is already high and its Special Defense low. Survives two Mega '
                       'Salamence Hyper Voices 83% of the time (was 14%) and Mega Garchomp&rsquo;s Draco Meteor 69% (was 25%), for a little less '
                       'against rare physical hitters."')
shutil.copy('trsheet/tr-sheet.html', 'trsheet/tr-sheet.v14.html')
open('trsheet/tr-sheet.html', 'w').write(out)
print('written')
