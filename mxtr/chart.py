T=["Normal","Fire","Water","Electric","Grass","Ice","Fighting","Poison","Ground","Flying","Psychic","Bug","Rock","Ghost","Dragon","Dark","Steel","Fairy"]
E={
"Normal":{"Rock":.5,"Ghost":0,"Steel":.5},
"Fire":{"Fire":.5,"Water":.5,"Grass":2,"Ice":2,"Bug":2,"Rock":.5,"Dragon":.5,"Steel":2},
"Water":{"Fire":2,"Water":.5,"Grass":.5,"Ground":2,"Rock":2,"Dragon":.5},
"Electric":{"Water":2,"Electric":.5,"Grass":.5,"Ground":0,"Flying":2,"Dragon":.5},
"Grass":{"Fire":.5,"Water":2,"Grass":.5,"Poison":.5,"Ground":2,"Flying":.5,"Bug":.5,"Rock":2,"Dragon":.5,"Steel":.5},
"Ice":{"Fire":.5,"Water":.5,"Grass":2,"Ice":.5,"Ground":2,"Flying":2,"Dragon":2,"Steel":.5},
"Fighting":{"Normal":2,"Ice":2,"Poison":.5,"Flying":.5,"Psychic":.5,"Bug":.5,"Rock":2,"Ghost":0,"Dark":2,"Steel":2,"Fairy":.5},
"Poison":{"Grass":2,"Poison":.5,"Ground":.5,"Rock":.5,"Ghost":.5,"Steel":0,"Fairy":2},
"Ground":{"Fire":2,"Electric":2,"Grass":.5,"Poison":2,"Flying":0,"Bug":.5,"Rock":2,"Steel":2},
"Flying":{"Electric":.5,"Grass":2,"Fighting":2,"Bug":2,"Rock":.5,"Steel":.5},
"Psychic":{"Fighting":2,"Poison":2,"Psychic":.5,"Dark":0,"Steel":.5},
"Bug":{"Fire":.5,"Grass":2,"Fighting":.5,"Poison":.5,"Flying":.5,"Psychic":2,"Ghost":.5,"Dark":2,"Steel":.5,"Fairy":.5},
"Rock":{"Fire":2,"Ice":2,"Fighting":.5,"Ground":.5,"Flying":2,"Bug":2,"Steel":.5},
"Ghost":{"Normal":0,"Psychic":2,"Ghost":2,"Dark":.5},
"Dragon":{"Dragon":2,"Steel":.5,"Fairy":0},
"Dark":{"Fighting":.5,"Psychic":2,"Ghost":2,"Dark":.5,"Fairy":.5},
"Steel":{"Fire":.5,"Water":.5,"Electric":.5,"Ice":2,"Rock":2,"Steel":.5,"Fairy":2},
"Fairy":{"Fire":.5,"Fighting":2,"Poison":.5,"Dragon":2,"Dark":2,"Steel":.5},
}
def eff(a,d):
    m=1.0
    for x in d: m*= E[a].get(x,1)
    return m

TEAM=[("Rillaboom",["Grass"]),("Incineroar",["Fire","Dark"]),("Sneasler",["Fighting","Poison"]),
      ("Gholdengo",["Steel","Ghost"]),("Mega Raichu Y",["Electric"]),("Mega Salamence",["Dragon","Flying"])]
print("=== GROUND into the team ===")
w=0
for n,t in TEAM:
    m=eff("Ground",t)
    if m>1: w+=1
    print(f"  {n:16s} {'/'.join(t):14s} {m}x")
print(f"  -> {w}/6 weak to Ground\n")

print("=== Every attacking type vs the team (count of members hit 2x+) ===")
rows=[]
for a in T:
    hits=[n for n,t in TEAM if eff(a,t)>1]
    rows.append((len(hits),a,hits))
for c,a,h in sorted(rows,reverse=True):
    if c: print(f"  {a:9s} {c}/6  {', '.join(h)}")
