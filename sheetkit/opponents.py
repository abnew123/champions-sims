"""Opponents from real teams, grouped by core rules (the classification the sheets use since 2026-10-06).

Battle sim's pool (pssim/opp_pool.py: every side of the cached Showdown Reg M-C Bo3 games with an open team sheet) is split by its
ordered core rules (pssim/results/core_rules_both_100.json; a team takes the first rule its six matches). Each rule is one card on the
sheet, shown under the tab of its nearest archetype; teams that match no rule get one "other" card per archetype. Each card gets an
opponent model in the shape t1sim.js reads (its six most common lead pairs with their turn-one clicks and back rows, and each species'
most common set), so every kit step runs on cards exactly as it ran on archetypes.

  python3 sheetkit/opponents.py        -> sheetkit/opponents/cards.json (the cards, their shares, tabs and guide) and
                                          sheetkit/opponents/opp_model.json (the models, keyed by card name)
A sheet uses them with "opponents": "cards" in its sheet.json."""
import json, os, re, subprocess, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import KIT, ROOT, PSSIM, VENV_PY, rj, wj

OUT = os.path.join(KIT, 'opponents')
RULES = os.path.join(PSSIM, 'results', 'core_rules_both_100.json')
MIN_PAIR = 5                                 # a lead pair seen fewer times than this is too thin to model
MIN_OTHER = 0.01                             # an "other" card needs at least 1% of all teams
TAB = {'Tailwind': 'tw', 'Sun': 'sun', 'Indeedee TR': 'indeedee', 'Rain': 'rain', 'Balance': 'balance', 'Sand': 'sand', 'Snow': 'snow',
       'Trick Room': 'tr', 'Rain + Sun': 'rainsun', 'Perish': 'perish'}
TAB_NAME = {'tw': 'Tailwind', 'sun': 'Sun', 'indeedee': 'Indeedee TR', 'rain': 'Rain', 'balance': 'Balance', 'sand': 'Sand', 'snow': 'Snow',
            'tr': 'Trick Room', 'rainsun': 'Rain + Sun', 'perish': 'Perish'}
TAB_ORDER = ['tw', 'indeedee', 'sun', 'rain', 'balance', 'sand', 'snow', 'tr', 'rainsun', 'perish']
FALLBACK_GUIDE = [['Gengar', 'perish'], ['Charizard + Pelipper or Politoed', 'rainsun'], ['Charizard or Torkoal', 'sun'], ['Pelipper or Politoed', 'rain'],
                  ['Tyranitar', 'sand'], ['Froslass, Alolan Ninetales or Vanilluxe', 'snow'], ['Indeedee', 'indeedee'], ['Farigiraf or Sinistcha', 'tr'],
                  ['Salamence, Whimsicott, Talonflame or Staraptor', 'tw'], ['none of these', 'balance']]

def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def pool_model(group, out):
    py = VENV_PY if os.path.exists(VENV_PY) else sys.executable
    subprocess.run([py, 'opp_pool.py', 'model', group, out, '12'], cwd=PSSIM, check=True, stdout=subprocess.DEVNULL)
    m = rj(out)
    m['pairs'] = [p for p in m['pairs'] if p['n'] >= MIN_PAIR][:6]          # (12 asked, so the floor still leaves up to six)
    return m

def guide_rules(rules, cards):
    """every core rule in order (first match wins), each pointing at its card; a rule too thin for a card of its own points at its tab's
    "other" card (else the tab's most common card), so a team that matches it still lands somewhere sensible"""
    have = {c['model'] for c in cards}; out = []
    for r in rules:
        arch, _, label = r['name'].partition(': '); tab = TAB[arch]
        if r['name'] in have: card = r['name']
        else:
            other = f'Other {arch}'
            card = other if other in have else max((c for c in cards if c['tab'] == tab), key=lambda c: c['share'])['model']
        out.append({'label': label, 'tab': tab, 'card': card, 'all': r['all'], 'none': r['none']})
    return out

def build():
    py = VENV_PY if os.path.exists(VENV_PY) else sys.executable
    if not os.path.exists(os.path.join(PSSIM, 'opp_pool.json')): subprocess.run([py, 'opp_pool.py', 'build'], cwd=PSSIM, check=True, stdout=subprocess.DEVNULL)
    pool = rj(os.path.join(PSSIM, 'opp_pool.json'))['entries']; N = len(pool)
    count = collections.Counter(e['group'] for e in pool); other = collections.Counter(e['arch'] for e in pool if e['group'] == 'other')
    rules = rj(RULES); os.makedirs(OUT, exist_ok=True); tmp = os.path.join(OUT, 'tmp_model.json')
    cards, models, guide = [], {}, []
    def add(name, group, tab, label, rule):
        m = pool_model(group, tmp)
        if not m['pairs']: print(f"  skipped {name}: no lead pair seen {MIN_PAIR}+ times"); return
        share = (count[group] if not group.startswith('other:') else other[group[6:]]) / N
        models[name] = {'n': m['n'], 'sets': m['sets'], 'pairs': m['pairs']}
        cards.append({'model': name, 'key': slug(name), 'tab': tab, 'label': label, 'rule': rule, 'share': round(100 * share, 2), 'sides': m['n'],
                      'pairs_cover': round(sum(p['n'] for p in m['pairs']) / max(1, m['n']), 3)})
        print(f"  {name}: {m['n']} teams ({100*share:.1f}%), {len(m['pairs'])} lead pairs covering {100*cards[-1]['pairs_cover']:.0f}%")
    for r in rules:
        arch, _, label = r['name'].partition(': ')
        add(r['name'], r['name'], TAB[arch], label, {'all': r['all'], 'none': r['none']})
    for arch in TAB:
        if other[arch] / N >= MIN_OTHER: add(f'Other {arch}', f'other:{arch}', TAB[arch], 'anything else', None)
    os.remove(tmp)
    tabs = [{'key': k, 'tab': TAB_NAME[k], 'cards': [c['model'] for c in sorted((c for c in cards if c['tab'] == k), key=lambda c: (c['rule'] is None, -c['share']))]}
            for k in TAB_ORDER]
    wj({'source': 'pssim/opp_pool.json (Showdown Reg M-C Bo3 sides with open team sheets) grouped by pssim/results/core_rules_both_100.json',
        'teams': N, 'in_a_core_group': round(1 - count['other'] / N, 3), 'cards': cards, 'tabs': [t for t in tabs if t['cards']],
        'guide_rules': guide_rules(rules, cards), 'guide_fallback': FALLBACK_GUIDE}, os.path.join(OUT, 'cards.json'), indent=1)
    wj(models, os.path.join(OUT, 'opp_model.json'))
    print(f"{len(cards)} cards ({sum(c['share'] for c in cards):.0f}% of {N} teams) -> sheetkit/opponents/")

if __name__ == '__main__': build()
