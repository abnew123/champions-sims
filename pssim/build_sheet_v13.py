"""Sheet Version 13 (2026-10-04): every tab shows the strongest four by full battles (battle_picks_final.json): one card per archetype with its
whole-game win %, the turn-one lines for that lead, and mechanics notes. Builds the lead data with tr_leads.py (LEAD_OVERRIDE for all ten
archetypes) and splices it into the published page (trsheet/tr-sheet.html, Version 12 layout), with the card label and leads note updated.
usage (from the project root): python3 pssim/build_sheet_v13.py <scratch dir>"""
import json, re, os, sys, subprocess, shutil
S = sys.argv[1]
ORDER = ['Incineroar', 'Indeedee-F', 'Hatterene', 'Farigiraf', 'Torkoal', 'Kingambit', 'Blastoise']      # tr_final lead naming order
F = json.load(open('pssim/battle_picks_final.json'))
O = {a: {'lead': '+'.join(sorted(p['lead'], key=ORDER.index)), 'back': p['back'], 'fbw': round(100 * p['v'])} for a, p in F.items()}
json.dump(O, open('pssim/lead_override_v13.json', 'w'), indent=1)
env = dict(os.environ, LEAD_OVERRIDE='pssim/lead_override_v13.json', SHOW_PLAN='0', TEAM_NOTE='', READER_W='0.75', BACK_FILE='pssim/eg_final_summary.json',
           TRMULT_FILE='pssim/trmult_final.json', TRUP_FILE='pssim/trup_v11.json')
shutil.copy('tr_leads_data.json', S + '/tr_leads_data_before.json')
subprocess.run(['python3', 'tr_leads.py', 'pssim/tr_final_v11plus.json', 'trsheet/tr-sheet.html', S + '/v13.html'], env=env, check=True, stdout=open(S + '/v13.log', 'w'))
shutil.copy('tr_leads_data.json', 'pssim/tr_leads_data_v13.json'); shutil.copy(S + '/tr_leads_data_before.json', 'tr_leads_data.json')
pub = open('trsheet/tr-sheet.html').read(); new = open(S + '/v13.html').read()
L = re.search(r'const L=\[.*?\n\];', new, re.S).group(0)
out, n = re.subn(r'const L=\[.*?\n\];', lambda m: L, pub, count=1, flags=re.S); assert n == 1
old = '(p.fb?"Full-battle pick":(p.x2!=null?"Top lead with Trick Room doubled":"Top lead"))'
assert out.count(old) == 1; out = out.replace(old, '(p.fbw!=null?`Wins ${p.fbw}% of whole-game sims`:(p.fb?"Full-battle pick":(p.x2!=null?"Top lead with Trick Room doubled":"Top lead")))')
old = re.search(r'The first card is the main lead\. In Sun, Rain, Sand, Trick Room and Perish.*?marked &ldquo;Top lead&rdquo;\.', out, re.S).group(0)
out = out.replace(old, 'Each tab shows the four to bring: the lead and back row that won the most whole-game sims against that archetype (both sides '
                       'switching, every turn played out, Trick Room and endgames included). Its lines are the turn-one plan for that lead.')
m = re.search(r'Leads are ranked on a score[^<]*?like yours\. ', out); assert m; out = out.replace(m.group(0), '')
m = re.search(r'The back row shown is the pair that did best in a 2v2 endgame sim.*?Trick Room credit\. ', out, re.S); assert m
out = out.replace(m.group(0), 'The lead and back row shown won the most whole-game sims: full 4v4 battles in a native port of Showdown&rsquo;s engine, '
                  'both sides playing each turn&rsquo;s best mix (switches included) to the end, against the archetype&rsquo;s six most common leads '
                  'with the back rows they bring in replays; close calls were settled head to head on the same seeds. The turn-one numbers were simulated '
                  'with a default back row, which only affects turn-one switches and the Trick Room credit. ')
open('trsheet/tr-sheet.html', 'w').write(out)
print('written; picks:'); [print(' ', a, O[a]) for a in O]
