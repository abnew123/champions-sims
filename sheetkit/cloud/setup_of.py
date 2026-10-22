"""The sim setup a team's kit runs use, for the cloud scripts: SHEET_SETUP, else the sheet's pinned 'setup' (sheet.json), else sim.json's
'current' (the same order as picks.battle_run). Prints the binary, value file and engine data, then the files the setup's env names
(env_paths, e.g. CALC_DATA), space-separated.
  python3 sheetkit/cloud/setup_of.py [team]      (no team: SHEET_SETUP or current)
  python3 sheetkit/cloud/setup_of.py --all       every binary a box may need: current's and each sheet's pinned one, one per line"""
import json, os, sys, glob
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
S = json.load(open(os.path.join(ROOT, 'sheetkit', 'sim.json')))

def name(team=None):
    p = os.path.join(ROOT, 'sheets', team or '', 'sheet.json')
    pin = json.load(open(p)).get('setup') if team and os.path.exists(p) else None
    return os.environ.get('SHEET_SETUP') or pin or S['current']

def files(n):
    s = S['setups'][n]
    return [s['binary'], s['value'], s['engine_data']] + [s['env'][k] for k in s.get('env_paths', [])]

if __name__ == '__main__':
    if sys.argv[1:] == ['--all']:
        ns = {name()} | {json.load(open(p)).get('setup') for p in glob.glob(os.path.join(ROOT, 'sheets', '*', 'sheet.json'))} - {None}
        print('\n'.join(sorted({S['setups'][n]['binary'] for n in ns if n in S['setups']})))
    else:
        print(' '.join(files(name(sys.argv[1] if len(sys.argv) > 1 else None))))
