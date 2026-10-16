"""One builder for the engine's position specs, for every program that reads a battle: the live page and the broadcasts (live.specs_for),
the bot (botpos.py), the replays' positions behind the eval bar's accuracy set and Battle sim's value data (spots.specs), the damage fits
(spreads.py). An outside review (2026-10-14; the user: "go ahead with the shared builder") found that each had its own and fixes reached one
and missed the others: the replays' positions lacked Unburden, gained abilities, changed types, Perish and Toxic counts, binding moves,
volatile countdowns, Protean, Syrup and every positions.js flag, and gave each action to the log's slot, not the engine's.
replay.parse gives each turn's state; positions.js turns a spec into an engine state.
  mon(m, st, flags)    a Pokemon as the turn's state has it (m), played with the set st (spots.fit_set's form)
  fresh(st)            one that has not come in: a stand-in for an unseen back row (stand_in=True), the bot's bench from its request
  order(side)          a side's Pokemon in the engine's order: slot a, slot b, the bench, the fainted
  acts(step, orders)   the turn's actions by engine slot, their targets in the engine's slot letters
  side(S, mons), spec(name, step, sides, acts, stand_ins, flags, dropped)
FLAGS are the positions.js fixes the eval bar's positions ask for: without its flag positions.js rebuilds the old way. The bot passes its
own list (botpos.BOT_FLAGS): Battle sim switches each fix on for it."""
import replay as R, spots as S
toid = R.toid
FLAGS = {'yawnDue': True,       # a Yawn at the turn start puts its target to sleep at this turn's end
         'volDue': True,        # each volatile's countdown from the turn it started
         'fieldDue': True,      # Unburden's Speed after its item went, Perish Song's count
         'pctDue': True,        # a shown percent rebuilt as an HP that shows as it
         'abilDue': True,       # an ability gained in battle (Trace, Skill Swap)
         'chipDue': True,       # Toxic's count and a binding move go on
         'fallenDue': True,     # Supreme Overlord's count of fallen allies
         'typeDue': True,       # types changed in battle (Soak, Protean, Double Shock) (also damage.js)
         'syrupDue': True,      # a Supersweet Syrup that has activated stays spent (the v29 engine reads it)
         'srcDue': True,        # a volatile's source as Showdown has it: the holder for Imprison and the like, the seeder's slot for Leech Seed
         'rechargeDue': True,   # a Pokemon that must recharge (Hyper Beam) has only that
         'itemDue': True,       # the item a log line showed (Trick, Switcheroo, Thief), not the set's (the review; mon() reads it, not positions.js)
         'chargeDue': True}     # a charged move stopped before it fired (flinch, full paralysis, confusion) is no longer charging (mon() reads it)
def mon(m, st, flags=FLAGS):
    item = m['item'] if flags.get('itemDue') and m.get('iset') else st['item']
    return {**st, 'forme': m['forme'], 'mega': m['mega'], 'hpPct': m['hp'], 'fainted': m['f'], 'status': m['st'], 'slept': m['slept'], 'boosts': m['b'],
            'itemNow': '' if m['gone'] or toid(item) not in S.E['items'] else item, 'moved': m['moved'], 'stall': m['stall'], 'lock': m['lock'],
            'vol': [v for v in m['vol'] if v != 'charging'] if flags.get('chargeDue') and m.get('cabort') else m['vol'], 'onField': bool(m['pos']), 'last': m['last'], 'volarg': m['volarg'], 'volturn': m.get('volturn') or {},
            'unburden': m.get('unb', False), 'perish': m.get('perish', 0), 'abilityNow': m.get('abil', ''), 'toxn': m.get('toxn', 0), 'ptrap': m.get('ptrap'),
            'typesNow': m.get('types'), 'typeAdd': m.get('tadd', ''), 'proteanUsed': m.get('protean', False), 'syrupDone': m.get('syrup', False)}
def fresh(st, stand_in=False):
    d = {**st, 'mega': False, 'hpPct': 100, 'fainted': False, 'status': '', 'slept': 0, 'boosts': {}, 'itemNow': st['item'], 'moved': False,
         'stall': False, 'lock': '', 'vol': [], 'onField': False, 'last': '', 'volarg': {}}
    if stand_in: d['standIn'] = True
    return d
def order(side):
    return sorted(side['mons'], key=lambda m: (0 if m['pos'] == 'a' else 1 if m['pos'] == 'b' else 2 if not m['f'] else 3))
def acts(step, orders):
    """positions.js puts each side's first two of `orders` in its slots a and b: each action goes with its Pokemon's engine slot, and a
    target's slot letter is mapped the same way (a Pokemon alone in the log's slot b plays from the engine's slot a)"""
    eng = {sd: {m['pos']: 'ab'[i] for i, m in enumerate(orders[sd][:2]) if m['pos']} for sd in ('p1', 'p2')}
    def act(sd, i):
        m = orders[sd][i] if i < len(orders[sd]) else None
        a = step['acts'].get(sd + m['pos']) if m and m['pos'] else None
        if a and a.get('target'): a = {**a, 'target': a['target'][:2] + eng[a['target'][:2]].get(a['target'][2], a['target'][2])}
        return a
    return [[act(sd, i) for i in (0, 1)] for sd in ('p1', 'p2')]
def side(S_, mons):
    return {'mons': mons, 'tailwind': S_['tailwind'], 'screens': S_['screens'], 'hazards': S_['hazards']}
def spec(name, step, sides, acts_, stand_ins, flags=FLAGS, dropped=()):
    st = step['state']; f = st['field']
    return {'name': name, 'turn': step['turn'], 'sides': sides, 'acts': acts_, 'perish': st['perish'], 'standIns': stand_ins, **flags,
            'dropped': list(dropped), 'field': {'weather': [f['weather'], f['wturns']] if f['weather'] else None,
                                               'terrain': [f['terrain'], f['tturns']] if f['terrain'] else None, 'trickroom': f['tr']}}
