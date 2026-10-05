"""Sheet Version 16 (2026-10-04): the Matchups grid's Torkoal column re-run for 12 HP / 32 SpA / 22 SpD (mxtr: TK_ST=157,105,160,150,112,36
GRID_MONS=Torkoal GRID_TAG=_tork22 tr_grid.py, TR=1 and 0). Replaces only Torkoal's cells in the page's `const X=[...]` and writes the merged
grid files mxtr/gx_cells_{tr,notr}_inc_t22.json for later add_charts.py builds (the battle sim's gx_cells_*_inc.json are left as they were).
usage (from trsheet/): python3 patch_v16_tork.py"""
import json, re, shutil
SIX = ["Blastoise", "Torkoal", "Farigiraf", "Kingambit", "Incineroar"]; COL = SIX.index("Torkoal")
NAME = {"Indeedee-F": "Indeedee F", "Indeedee": "Indeedee M"}
def disp(n): base, _, rest = n.partition(" ("); return NAME.get(base, base) + ((" (" + rest) if rest else "")
def cell(c):                                   # as in add_charts.py
    o = {"v": c["v"], "t": c["det"]}
    if c.get("pct") is not None: o["p"] = c["pct"]
    if c.get("dep"): o["d"] = c["dep"]
    if c.get("note"): o["n"] = c["note"]
    return o
G = {}
for t in ("tr", "notr"):
    base = json.load(open(f"../mxtr/gx_cells_{t}_inc.json")); new = json.load(open(f"../mxtr/gx_cells_{t}_tork22.json"))
    assert set(new) == {k for k in base if k.endswith("|Torkoal")}
    merged = {k: new.get(k, v) for k, v in base.items()}; json.dump(merged, open(f"../mxtr/gx_cells_{t}_inc_t22.json", "w"), ensure_ascii=True)
    G[t] = merged
foes = []
for k in json.load(open("../mxtr/gx_cells_tr_inc.json")):
    f = k.split("|")[0]
    if f not in foes: foes.append(f)
s = open("tr-sheet.html", encoding="utf-8").read()
m = re.search(r"const X=(\[.*?\]);\n", s, re.S); X = json.loads(m.group(1)); assert len(X) == len(foes)
n = 0
for row, f in zip(X, foes):
    assert row[0] == disp(f), (row[0], f)
    for i, t in ((2, "tr"), (3, "notr")):
        c = cell(G[t][f + "|Torkoal"]); n += row[i][COL] != c; row[i][COL] = c
js = json.dumps(X, ensure_ascii=False, separators=(",", ":"))
assert s.count(m.group(1)) == 1
shutil.copy("tr-sheet.html", "tr-sheet.v15.html")
open("tr-sheet.html", "w", encoding="utf-8").write(s.replace(m.group(1), js))
print(f"{n} Torkoal cells changed (text or verdict)")
