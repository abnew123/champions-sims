"""Trick Room Six, v4: drop the Blastoise-or-Torkoal section; add the Coverage gaps table and the Matchups grid
(Trick Room up / no Trick Room) from ../mxtr. Runs on the v3 file and is safe to re-run on its own output."""
import json, re, sys, os
sys.path.insert(0, "../mxtr"); os.chdir("../mxtr"); os.environ["TR"] = "0"
import matchup as M
os.chdir("../trsheet")
SRC = sys.argv[1] if len(sys.argv) > 1 else "tr-sheet.html"
h = open(SRC, encoding="utf-8").read()

SIX = os.environ.get("SIX", "Blastoise,Torkoal,Farigiraf,Kingambit,Hatterene").split(",")
SHORT = {"Blastoise": "Blast", "Torkoal": "Tork", "Farigiraf": "Fari", "Kingambit": "Gambit", "Hatterene": "Hatt", "Incineroar": "Incin"}
NAME = {"Indeedee-F": "Indeedee F", "Indeedee": "Indeedee M"}
def disp(n):
    base, _, rest = n.partition(" (")
    return NAME.get(base, base) + ((" (" + rest) if rest else "")
def usage(u): return u if isinstance(u, str) else (round(u, 1) if u else 0)

# ---------- data: coverage ----------
cov = json.load(open(os.environ.get("COV", "../mxtr/tr_cov.json"), encoding="utf-8"))
def move_type(mon, mv):
    return next(m["t"] for m in M.MINE[mon]["moves"] if m["n"] == mv)
C = []
for r in cov:
    foe = r[0].split(" (")[0]
    types = M.F[foe][0]
    rank = [[m, mv, M.eff(move_type(m, mv), types), pct, ko] for m, mv, pct, ko in r[9]]
    C.append([disp(r[0]), usage(r[1]), 1 if r[8] == "sash" else 0, rank])

# ---------- data: matchups ----------
gt = json.load(open(os.environ.get("GX_TR", "../mxtr/gx_cells_tr.json"), encoding="utf-8"))
gn = json.load(open(os.environ.get("GX_NOTR", "../mxtr/gx_cells_notr.json"), encoding="utf-8"))
old = json.load(open("../team-sheet.html.usage.json", encoding="utf-8"))
foes = []
for k in gt:
    f = k.split("|")[0]
    if f not in foes: foes.append(f)
def cell(c):
    o = {"v": c["v"], "t": c["det"]}
    if c.get("pct") is not None: o["p"] = c["pct"]
    if c.get("dep"): o["d"] = c["dep"]
    if c.get("note"): o["n"] = c["note"]
    return o
X = [[disp(f), usage(old.get(f, 0)), [cell(gt[f + "|" + m]) for m in SIX], [cell(gn[f + "|" + m]) for m in SIX]] for f in foes]
js = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))

# ---------- CSS ----------
CSS = r"""/* coverage + matchups */
.badge{display:inline-flex;align-items:center;gap:5px;font-family:var(--disp);font-size:10.5px;font-weight:600;letter-spacing:.05em;
  text-transform:uppercase;line-height:1.3;padding:3px 8px;border-radius:3px}
.badge::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor;flex:none}
.b-ok{background:var(--ok-bg);color:var(--ok)}
.b-warn{background:var(--warn-bg);color:var(--warn)}
.b-off{background:var(--off-bg);color:var(--off)}
.u{display:block;font-family:var(--mono);font-size:10px;font-weight:400;color:var(--ink3);letter-spacing:0}
.xrow{cursor:pointer}
.xrow:hover td{background:var(--panel-2)}
.xrow.open td{background:var(--accent-soft)}
.xrow:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.xdet td{text-align:left;font-size:12.5px;line-height:1.55;color:var(--ink2);background:var(--panel-2);padding:10px 12px}
.xdet div{margin:3px 0}
table.cov td{vertical-align:middle}
table.cov td.thr{font-family:var(--disp);font-weight:600;color:var(--ink)}
table.cov td.hit b{font-family:var(--disp);font-weight:600}
.eff{font-family:var(--mono);font-size:11.5px;color:var(--ink3);white-space:nowrap}
table.cov td.max{font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap;color:var(--ink)}
table.cov td.max.short{color:var(--off)}
.kok{color:var(--ok);font-weight:600}.kpart{color:var(--warn);font-weight:600}.kno{color:var(--ink3)}
#coverage .sm{display:none}
@media(max-width:600px){#coverage .lg{display:none}#coverage .sm{display:inline}
  table.cov th,table.cov td{padding:8px 6px}table.cov th:first-child,table.cov td:first-child{padding-left:10px}table.cov thead th{white-space:normal}
  table.cov td.thr{font-size:12.5px}table.cov td.hit{font-size:12.5px}table.cov .badge{font-size:9.5px;letter-spacing:.03em;padding:3px 6px}}

.mxmode{display:inline-grid;grid-template-columns:repeat(2,auto);gap:1px;margin:0 0 12px;border:1px solid var(--rule);border-radius:4px;overflow:hidden;background:var(--rule-2)}
.mxm{font-family:var(--disp);font-size:11.5px;font-weight:600;letter-spacing:.02em;padding:8px 14px;border:0;background:var(--panel);color:var(--ink3);cursor:pointer}
.mxm:hover{background:var(--panel-2);color:var(--ink2)}
.mxm.on{background:var(--accent);color:var(--panel)}
.mxm:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.mxt{table-layout:fixed}
.mxt th{text-align:center;padding:9px 3px}
.mxt th:first-child{text-align:left;width:132px;padding-left:12px}
.mxt td{padding:5px 3px;text-align:center;vertical-align:middle}
.mxt td.thr{text-align:left;font-family:var(--mono);font-size:12px;color:var(--ink);font-weight:500;padding-left:12px}
.mx{display:block;font-family:var(--disp);font-size:10px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;padding:5px 2px;border-radius:3px;white-space:nowrap}
.mx i{font-style:normal;margin-left:2px}
.mx.c{background:var(--ok);color:var(--panel)}
.mx.k{background:var(--ok-bg);color:var(--ok)}
.mx.w{background:var(--warn-bg);color:var(--warn)}
.mx.l{color:var(--ink3)}
.mx.g{color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}
.mx.r{color:var(--off);box-shadow:inset 0 0 0 1px var(--off)}
#matchups .sm{display:none}
.mxdg{display:block;margin-top:1px;padding-left:14px;text-indent:-14px;color:var(--ink);font-weight:500}
.mxdg::before{content:"\21B3  "}
.mxv{font-family:var(--disp);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}
.mxv.c,.mxv.k{color:var(--ok)}.mxv.w{color:var(--warn)}.mxv.l{color:var(--ink3)}.mxv.g{color:var(--accent)}.mxv.r{color:var(--off)}
.mxleg{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;font-size:12px;color:var(--ink2);margin:0 0 12px}
.mxleg .mx{display:inline-block;padding:3px 7px;margin-right:4px}
@media(max-width:600px){#matchups .lg{display:none}#matchups .sm{display:inline}.mxt th{letter-spacing:.02em;font-size:9px;padding:8px 1px}.mxt td{padding:5px 1px}
  .mx{font-size:9px;letter-spacing:.02em}.mxt th:first-child{width:94px;padding-left:8px}.mxt td.thr{font-size:10.5px;padding-left:8px}}
@media(max-width:350px){.mxt th{font-size:8px;letter-spacing:0}.mx{font-size:8px;letter-spacing:0}.mxt th:first-child{width:84px}.mxt td.thr{font-size:9.5px}}
"""

# ---------- HTML ----------
HEADS = "".join(f'<th scope="col"><span class="lg">{m}</span><span class="sm">{s}</span></th>'
                for m, s in ((m, SHORT[m]) for m in SIX))
SECTIONS = f"""<section id="coverage">
  <div class="shead">
    <h2>Coverage gaps</h2>
    <p class="snote">Your hardest hit on each threat, worst gaps first. <b>Pessimistic throughout:</b> each threat is at the bulkiest of its most common spreads for the side you hit, with the items that stop a knockout: Focus Sash (Arcanine-H, Pelipper, Whimsicott), Chople on Kingambit, Colbur on Indeedee F. Sitrus is never counted as extra HP, and Sneasler has already used its Grassy Seed (+1 Defense). Your Torkoal is in its own sun; otherwise the threat&rsquo;s own weather and terrain are up. Water Spout and Eruption are from full HP, spread moves take their 25% cut, and Fake Out is left out. Tap a row for all five attackers.</p>
    <p class="snote">Your Indeedee&rsquo;s Psychic Terrain is not assumed. """ + ("In it, Hatterene&rsquo;s Expanding Force hits both foes for about 1.5 times the damage shown, and Farigiraf&rsquo;s Psychic does 1.3 times." if "Hatterene" in SIX else "In it, Farigiraf&rsquo;s Psychic does about 1.3 times the damage shown.") + f""" One-hit KOs only, so &ldquo;none&rdquo; can still be a clean two-hit win; the Matchups grid counts those.</p>
  </div>
  <div class="tscroll">
    <table class="cov">
      <thead><tr><th scope="col">Threat</th><th scope="col">Best hit</th><th scope="col"><span class="lg">Max roll</span><span class="sm">Max</span></th><th scope="col">Guaranteed KO</th></tr></thead>
      <tbody id="covbody"></tbody>
    </table>
  </div>
</section>

<section id="matchups">
  <div class="shead">
    <h2>Matchups</h2>
    <p class="snote">Who wins the one-on-one with both sides picking their best move each turn: your minimum rolls against their maximum, across their most-used spreads, up to three. Switch between Trick Room up for the whole fight and no Trick Room. Tap a row for the numbers. Under each name: its op.gg doubles usage or ladder rank; the six Trick Room threats added for this team have none. Indeedee has no attacks, so it has no column.</p>
  </div>
  <div class="mxmode" role="tablist" aria-label="Trick Room" id="mxmode">
    <button type="button" class="mxm on" role="tab" aria-selected="true" data-tr="1">Trick Room up</button><button type="button" class="mxm" role="tab" aria-selected="false" data-tr="0">No Trick Room</button>
  </div>
  <div class="mxleg">
    <span><span class="mx c"><span class="lg">Counter</span><span class="sm">Ctr</span></span> switches in and wins</span>
    <span><span class="mx k"><span class="lg">Check</span><span class="sm">Chk</span></span> wins or trades if already out</span>
    <span><span class="mx g"><span class="lg">Guess 50%</span><span class="sm">?50%</span></span> a mind game: your odds with best play</span>
    <span><span class="mx w">Wall</span> survives if already out, can&rsquo;t win</span>
    <span><span class="mx r"><span class="lg">Roll 20%</span><span class="sm">~20%</span></span> loses on your worst rolls; wins or trades this often on real ones</span>
    <span><span class="mx l">&mdash;</span> lost on any rolls</span>
    <span><b>*</b> needs its item intact</span>
  </div>
  <p class="snote" id="mxtally" style="margin:0 0 10px"></p>
  <div class="tscroll"><table class="mxt">
    <thead><tr><th scope="col">Threat</th>{HEADS}</tr></thead>
    <tbody id="mxbody"></tbody>
  </table></div>
  <p class="snote" style="margin-top:11px">One-on-one only, Protect left out. Fake Out is in, on each side&rsquo;s first turn out; it can&rsquo;t touch Ghost types, and Armor Tail or their Psychic Terrain blocks it and every other priority move. &ldquo;Trick Room up&rdquo; keeps it up for the whole fight. Spread damage is in, partner chip is not; in doubles, chip is what breaks the <b>*</b> wins. Rolls count accuracy as 100%. Your Torkoal is always in its own sun, and their Pelipper, Charizard Y, Torkoal and Tyranitar bring their weather. Grassy Terrain is up against Rillaboom and a seeded Sneasler, and their Psychic Terrain against Indeedee; yours is not assumed. Mega Raichu Y&rsquo;s Zap Cannon always paralyses: your worst luck counts every turn as fully paralysed, and real rolls use Champions&rsquo; 1-in-8 chance. Blastoise takes its switch-in hit before it Mega Evolves.</p>
</section>

"""

# ---------- JS ----------
JS = """/* coverage: best hit on each threat; rows are [threat, usage, Focus Sash, [[attacker, move, effectiveness, max %, KO rolls of 16], ...]] */
(function(){
const C=""" + js(C) + """;
const tb=document.getElementById("covbody");
const us=u=>typeof u==="string"?u:(u?u.toFixed(1)+"%":"\\u2014");
const pc=x=>(x<100?Math.floor(x):Math.round(x))+"%";
const ef=e=>(e===0.5?"\\u00bd":e===0.25?"\\u00bc":e)+"\\u00d7";
function badge(r){const ks=r[3].filter(x=>x[4]===16);
  if(r[2]) return '<span class="badge b-warn"><span class="lg">Sash: two hits</span><span class="sm">Sash</span></span>';
  if(!ks.length) return '<span class="badge b-off">none</span>';
  if(ks.length===1) return `<span class="badge b-warn"><span class="lg">only ${ks[0][0]}</span><span class="sm">${ks[0][0]}</span></span>`;
  return `<span class="badge b-ok">${ks.length} of five</span>`;}
function ko(x,sash){ if(x[4]===16) return '<span class="kok">always one-shots</span>';
  if(x[4]>0) return `<span class="kpart">one-shots on ${x[4]} of 16 rolls</span>`;
  return sash&&x[3]>=100?'<span class="kpart">the Sash holds</span>':"";}
tb.innerHTML=C.map((r,i)=>{const b=r[3][0];
  return `<tr class="xrow" tabindex="0" aria-expanded="false" data-d="cd${i}"><td class="thr">${r[0]}<span class="u">${us(r[1])}</span></td>`+
   `<td class="hit"><b>${b[0]}</b> ${b[1]} <span class="eff">${ef(b[2])}</span></td><td class="max${b[3]<100?" short":""}">${pc(b[3])}${b[4]>0&&b[4]<16?`<span class="u"><span class="lg">${b[4]}/16 rolls</span><span class="sm">${b[4]}/16</span></span>`:""}</td><td>${badge(r)}</td></tr>`+
   `<tr class="xdet" id="cd${i}" hidden><td colspan="4">`+r[3].map(x=>{const k=ko(x,r[2]);
     return `<div><b>${x[0]}</b> ${x[1]} <span class="eff">${ef(x[2])}</span> &middot; max ${pc(x[3])}${k?" &middot; "+k:""}</div>`;}).join("")+`</td></tr>`;}).join("");
})();

/* matchups: [threat, usage, cells with Trick Room up, cells without], one cell per attacker in N's order */
(function(){
const N=""" + js(SIX) + """;
const X=""" + js(X) + """;
const L={counter:["Counter","Ctr","c"],check:["Check","Chk","k"],guess:["Guess","?","g"],wall:["Wall","Wall","w"],roll:["Roll","~","r"],lost:["\\u2014","\\u2014","l"]};
const D={counter:c=>"counter",check:c=>"check",guess:c=>`guess &middot; ${c.p}% with best play`,wall:c=>"wall",roll:c=>`roll &middot; wins or trades ${c.p}% on real rolls`,lost:c=>"lost"};
const tb=document.getElementById("mxbody"), tally=document.getElementById("mxtally"), bar=document.getElementById("mxmode");
const us=u=>typeof u==="string"?u:(u?u.toFixed(1)+"%":"\\u2014");
function draw(tr){
  const col=tr?2:3;
  tb.innerHTML=X.map((r,i)=>{const cs=r[col];
    return `<tr class="xrow" tabindex="0" aria-expanded="false" data-d="md${i}"><td class="thr">${r[0]}<span class="u">${us(r[1])}</span></td>`+
    cs.map(c=>{const l=L[c.v],pc=c.p!=null?c.p+"%":"",mk=c.d?"*":"";
      const lg=(c.v==="guess"||c.v==="roll")?`${l[0]} ${pc}`:l[0], sm=(c.v==="guess"||c.v==="roll")?`${l[1]}${pc}`:l[1];
      return `<td><span class="mx ${l[2]}"><span class="lg">${lg}</span><span class="sm">${sm}</span>${mk?`<i>${mk}</i>`:""}</span></td>`;}).join("")+
    `</tr><tr class="xdet" id="md${i}" hidden><td colspan="6">`+
    cs.map((c,j)=>`<div><b>${N[j]}</b> <span class="mxv ${L[c.v][2]}">${D[c.v](c)}${c.d?" &middot; needs "+c.d:""}</span> &mdash; ${c.t}${c.n?`<span class="mxdg">${c.n}</span>`:""}</div>`).join("")+
    `</td></tr>`;}).join("");
  const all=X.flatMap(r=>r[col]), n=v=>all.filter(c=>c.v===v).length, rest=all.length-n("counter")-n("check")-n("wall");
  tally.innerHTML=`${tr?"With Trick Room up":"Without Trick Room"}: <b>${n("counter")}</b> counters, <b>${n("check")}</b> checks and <b>${n("wall")}</b> ${n("wall")===1?"wall":"walls"} in ${all.length} squares. `+
    `Of the other ${rest}, <b>${n("lost")}</b> are lost on any rolls and <b>${n("roll")}</b> come down to rolls${n("guess")?`; <b>${n("guess")}</b> ${n("guess")===1?"is a guess":"are guesses"}`:""}.`;
  bar.querySelectorAll(".mxm").forEach(b=>{const on=(b.dataset.tr==="1")===tr; b.classList.toggle("on",on); b.setAttribute("aria-selected",on);});
}
bar.addEventListener("click",e=>{const b=e.target.closest(".mxm"); if(b) draw(b.dataset.tr==="1");});
draw(true);
})();

/* tap or Enter on a row opens its numbers (both tables) */
(function(){
function flip(r){const d=document.getElementById(r.dataset.d); if(!d) return; d.hidden=!d.hidden; r.classList.toggle("open",!d.hidden); r.setAttribute("aria-expanded",!d.hidden);}
["covbody","mxbody"].forEach(id=>{const tb=document.getElementById(id);
  tb.addEventListener("click",e=>{const r=e.target.closest(".xrow"); if(r) flip(r);});
  tb.addEventListener("keydown",e=>{const r=e.target.closest(".xrow"); if(r&&(e.key==="Enter"||e.key===" ")){e.preventDefault(); flip(r);}});});
})();

"""

# ---------- apply ----------
# 1. old section, CSS and JS out (no-ops on a re-run)
h = re.sub(r'<section id="attackers">.*?</section>\n+', "", h, flags=re.S)
h = re.sub(r'\.wx\{.*?table\.wxt td\.half\{[^}]*\}\n+', "", h, flags=re.S)
h = re.sub(r'/\* weather tables:.*?\}\)\(\);\n+', "", h, flags=re.S)
# 2. previous copies of the new blocks out, so a re-run replaces them
h = re.sub(r'/\* coverage \+ matchups \*/.*?\n\n(?=table\.spd td\.s\{)', "", h, flags=re.S)
h = re.sub(r'<section id="coverage">.*?</section>\n+<section id="matchups">.*?</section>\n+', "", h, flags=re.S)
h = re.sub(r'/\* coverage: best hit.*?/\* tap or Enter on a row.*?\}\)\(\);\n+', "", h, flags=re.S)
# 3. new blocks in
h = h.replace("\ntable.spd td.s{", "\n" + CSS.rstrip("\n") + "\n\ntable.spd td.s{", 1)
h = h.replace('<section id="speed">', SECTIONS + '<section id="speed">', 1)
h = h.replace("/* speed under Trick Room", JS + "/* speed under Trick Room", 1)
# 4. jump bar, subtitle, Blastoise note, footer
h = h.replace('<a href="#attackers">Blastoise or Torkoal</a>', '<a href="#coverage">Coverage</a><a href="#matchups">Matchups</a>')
h = h.replace("the sets to train, how to get Trick Room up, which attacker to bring, and what to lead.",
              "what to lead, the sets to train, how to get Trick Room up, and who beats what.")
h = h.replace("Dark Pulse one-shots Gholdengo and Mega Gengar.",
              "Dark Pulse one-shots the usual Gholdengo and Mega Gengar spreads, though not their bulky ones.")
h = re.sub(r'<p><b>Damage\.</b>.*?</p>',
           "<p><b>Damage.</b> Coverage and Matchups use an exact damage calculator that follows Showdown&rsquo;s formula, checked against the "
           "Smogon calculator, without crits. The leads were simulated in Showdown&rsquo;s own engine with Champions mechanics.</p>", h, flags=re.S)
open(SRC, "w", encoding="utf-8").write(h)
print("ok", len(h), "bytes;", len(C), "coverage rows;", len(X), "matchup rows")
