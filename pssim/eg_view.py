"""Render eg_examples.json as a readable HTML page (one card per archetype)."""
import json, sys, html
d = json.load(open(sys.argv[1])); out = sys.argv[2]; title = sys.argv[3] if len(sys.argv) > 3 else '2v2 endgame examples'
def mix(L): return ''.join(f'<li><span class="p">{round(100*p)}%</span> {html.escape(a)}</li>' for a, p in L)
cards = []
for g in d:
    turns = []
    for i, ev in enumerate(g['events']):
        t = g['turns'][i - 1] if 0 < i <= len(g['turns']) else None
        head = (f'<div class="th"><b>Turn {t["turn"]}</b><span class="v">model&rsquo;s win estimate {round(100*t["value"])}%</span></div>'
                f'<div class="mix"><div><div class="lab">Your mix</div><ul>{mix(t["my"])}</ul></div><div><div class="lab">Their mix</div><ul>{mix(t["th"])}</ul></div></div>') if t else '<div class="th"><b>Start</b></div>'
        turns.append(f'<div class="turn">{head}<div class="ev">{"<br>".join(ev)}</div></div>')
    res = 'You win' if g['v'] >= 0.99 else 'They win' if g['v'] <= 0.01 else f'Unfinished (value {round(100*g["v"])}%)'
    cards.append(f'''<details class="card"><summary><span class="tab">{g["tab"]}</span> your <b>{" + ".join(g["mine"])}</b> vs their <b>{" + ".join(g["theirs"])}</b>
      <span class="meta">{"Trick Room up, 3 turns" if g["K"] else "no Trick Room"} &middot; <span class="{"win" if g["v"] >= .99 else "loss" if g["v"] <= .01 else ""}">{res}</span></span></summary>
      <p class="note">Main lead {g["lead"]} (sets Trick Room {g["tr"]}% on turn one); this is its back pair. Their pair is the most common pair on the field at turn 3 for {g["tab"]} in the replays ({round(100*g["w"])}% of that archetype&rsquo;s teams).</p>
      <details class="sets"><summary>Sets</summary><div>{"<br>".join(html.escape(s) for s in g["sets"])}</div></details>
      {"".join(turns)}</details>''')
page = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>2v2 Examples</title>
<style>:root{{--bg:#f6f5f9;--panel:#fff;--ink:#16141b;--ink2:#55525f;--rule:#dfdce6;--acc:#6a43c7;--ok:#00734f;--off:#b8431c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141318;--panel:#1c1b21;--ink:#f2f1f6;--ink2:#aca9b7;--rule:#2e2c36;--acc:#a68cf3;--ok:#4cc79a;--off:#f08055}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,system-ui,sans-serif}}.wrap{{max-width:900px;margin:0 auto;padding:24px 16px 60px}}
h1{{font-size:26px;margin:0 0 6px}}.sub{{color:var(--ink2);margin:0 0 18px}}.card{{background:var(--panel);border:1px solid var(--rule);border-radius:6px;margin:0 0 10px;padding:0 14px}}
.card>summary{{cursor:pointer;padding:12px 0;list-style-position:outside}}.tab{{display:inline-block;min-width:92px;font-weight:700;color:var(--acc)}}.meta{{color:var(--ink2);font-size:13px;margin-left:6px}}
.win{{color:var(--ok);font-weight:600}}.loss{{color:var(--off);font-weight:600}}.note{{color:var(--ink2);font-size:13px;margin:0 0 8px}}.sets{{font-size:12.5px;color:var(--ink2);margin-bottom:8px}}
.turn{{border-top:1px solid var(--rule);padding:10px 0}}.th{{display:flex;justify-content:space-between;gap:8px}}.v{{color:var(--ink2);font-size:12.5px}}
.mix{{display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;margin:6px 0;font-size:12.5px;color:var(--ink2)}}@media(max-width:600px){{.mix{{grid-template-columns:1fr}}}}
.mix ul{{margin:2px 0;padding-left:0;list-style:none}}.lab{{font-weight:600;color:var(--ink)}}.p{{display:inline-block;width:36px;font-variant-numeric:tabular-nums;color:var(--acc);font-weight:600}}
.ev{{font-size:13.5px}}</style></head><body><div class="wrap"><h1>{html.escape(title)}</h1>
<p class="sub">One game per archetype: the sheet&rsquo;s main lead&rsquo;s back pair against the archetype&rsquo;s likeliest back pair, both fresh. Each turn both sides play the equilibrium mix of a one-turn game (shown: each side&rsquo;s top options and how often it picks them); the move actually played is drawn from that mix. &ldquo;Win estimate&rdquo; is the fitted model&rsquo;s chance you win from the position before the turn (fit on 7,347 positions from 2v2 games: HP, Pok&eacute;mon left, boosts, Trick Room turns, typing, one-on-one matchups, status, locks; Perish races added by hand).</p>
{"".join(cards)}</div></body></html>'''
open(out, 'w').write(page); print('ok', out)
