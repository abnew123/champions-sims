"""Trick Room Six, v8: Incineroar replaces Hatterene. Team card, subtitle, speed table and sources. Run after tr_leads.py and
add_charts.py have rebuilt the leads, coverage and matchups for the new six. Safe to re-run."""
import re, sys
SRC = sys.argv[1] if len(sys.argv) > 1 else "tr-sheet.html"
h = open(SRC, encoding="utf-8").read()

def sub1(old, new):
    global h
    if new in h: return                      # already applied
    assert h.count(old) == 1, old[:70]
    h = h.replace(old, new)

# subtitle
sub1("Mega Blastoise, Torkoal, Indeedee, Farigiraf, Kingambit and Hatterene:", "Mega Blastoise, Torkoal, Indeedee, Farigiraf, Kingambit and Incineroar:")

# team card
INC = ('{n:"Incineroar",t:"Fire / Dark",role:"Support",item:"White Herb",ab:"Intimidate",nat:"Brave",sp:[32,32,0,0,2,0],st:[202,183,110,100,112,72],\n'
       '  mv:["Fake Out","Flare Blitz","Throat Chop","Close Combat"],\n'
       '  note:"Fake Out and Intimidate on the lead, and again each time it switches back in. Throat Chop is its hit on Indeedee, whose terrain blocks Fake Out; '
       'Close Combat is for Kingambit, Incineroar and Tyranitar. White Herb undoes one drop: Attack after their Intimidate, or both Defenses after Close Combat.",\n'
       '  src:"The most common Incineroar set on Indeedee Trick Room teams in the replays (157 of 532 there). Brave with no Speed points gives 72 Speed, '
       'the same as your Farigiraf; HP and Attack are maxed like your other slow attackers."}')
h, n = re.subn(r'\{n:"Hatterene",t:"Psychic / Fairy".*?src:"[^"]*"\}', lambda m: INC, h, count=1, flags=re.S)
assert n == 1 or '{n:"Incineroar"' in h

# speed table: Hatterene is no longer yours; Incineroar sits with Farigiraf at 72
sub1('[44,"Hatterene","Hatterene","Tie"]', '[44,"","Hatterene",""]')
sub1('[72,"Farigiraf","Farigiraf (Relaxed, Quiet)', '[72,"Farigiraf, Incineroar","Farigiraf (Relaxed, Quiet)')

# sources
sub1('<a href="https://metavgc.com/pokemon/hatterene">Hatterene</a>, ', '')
sub1("The two spare stat points go wherever the top spread put them; they change nothing that matters.</p>",
     "Incineroar&rsquo;s set is the most common one on Indeedee Trick Room teams in the 5,000 M-C Bo3 replays the leads were simulated from. "
     "The two spare stat points go wherever the top spread put them; they change nothing that matters.</p>")

# team section notes: two setters now
sub1("Each set uses the most common spread for that Pok\u00e9mon running these moves. Stat points",
     "Each set uses the most common spread for that Pok\u00e9mon running these moves; Incineroar&rsquo;s card says where its set comes from. Stat points")
sub1("<b>Bringing four:</b> two setters and two attackers works for most games, and each lead in the Leads section names a back row. Keep the second setter in the back: it replaces a setter that falls and resets Trick Room when it ends.",
     "<b>Bringing four:</b> both setters, Indeedee and Farigiraf, and two of the others works for most games, and each lead in the Leads section names a back row. Keep the setter you don&rsquo;t lead with in the back: it replaces a setter that falls and resets Trick Room when it ends.")

open(SRC, "w", encoding="utf-8").write(h)
left = [m.group(0) for m in re.finditer(r'.{60}Hatterene.{60}', h)]
print("ok", len(h), "| Hatterene mentions left:", len(left))
