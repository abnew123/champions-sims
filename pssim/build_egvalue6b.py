"""egvalue6b (2026-10-04): egvalue5 with only the weights self-play cannot learn (its TR-six games have almost no sleep, paralysis, burn or
opposing Tailwind) taken from real Bo3 games (results/fit_real_value.json), converted with egvalue5's HP weight (real weight / real HP
weight x egvalue5 HP weight). Everything else stays egvalue5: self-play weights are on-policy, e.g. the Protected-last-turn penalty
corrects this one-turn planner's own over-Protecting (egvalue6, with the real -0.07 there, Protected far more).
usage: python3 build_egvalue6b.py"""
import json
R = json.load(open('results/fit_real_value.json')); e5 = json.load(open('egvalue5.json'))
real = dict(zip(R['names'], R['real'][1:])); hp5 = e5['w'][0]
TAKE = {'slp': 11, 'par': 12, 'brn': 13, 'tw': 14}
W = list(e5['w'])
for k, i in TAKE.items(): W[i] = real[k] / real['hp'] * hp5
hand = dict(e5['hand_set']); hand.pop('Tailwind turns (no TR)', None)
json.dump({'b0': e5['b0'], 'w': W, 'names': e5['names'], 'hand_set': hand,
           'note': f"egvalue5 with asleep/frozen, paralysed, burned/poisoned and Tailwind from {R['n_real_games']} real Bo3 games, scaled by egvalue5's HP weight."},
          open('egvalue6b.json', 'w'), indent=1)
for nm, a, b in zip(e5['names'], e5['w'], W):
    if a != b: print(f"   {nm:30s} {a:+.3f} -> {b:+.3f}")
