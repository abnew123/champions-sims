"""Trick Room Six, v6: drop the Trick Room setter, Psychic Terrain and Guides sections; rebuild the speed table from ladder
spreads (Smogon, Aug 2026 Reg M-B Bo3 1500, top six spreads per Pokemon) and our tournament sets. Safe to re-run."""
import re, sys
SRC = sys.argv[1] if len(sys.argv) > 1 else "tr-sheet.html"
h = open(SRC, encoding="utf-8").read()

# sections, jump links, their CSS and JS
for sid in ("room", "terrain", "guides"):
    h = re.sub(rf'<section id="{sid}">.*?</section>\n+', "", h, flags=re.S)
h = h.replace('<a href="#room">Trick Room</a>', "").replace('<a href="#terrain">Terrain</a>', "").replace('<a href="#guides">Guides</a>', "")
h = re.sub(r'\.v\{display:inline-block.*?table\.matrix td\{width:28%\}\n\n', "", h, flags=re.S)
h = re.sub(r'\.rules\{display:grid.*?\.rules li\{[^}]*\}\n\n', "", h, flags=re.S)
h = re.sub(r'\.notes\{display:grid[^}]*\}\n\.notes p\{[^}]*\}\n\n', "", h)
h = re.sub(r'\.guides\{display:grid.*?\.guide p\{[^}]*\}\n\n', "", h, flags=re.S)
h = re.sub(r'/\* guides \*/\n\(function\(\)\{.*?\}\)\(\);\n\n', "", h, flags=re.S)

# words that pointed at the removed sections
h = h.replace("what to lead, the sets to train, how to get Trick Room up, and who beats what.",
              "what to lead, the sets to train, who beats what, and who moves first under Trick Room.")
h = h.replace("Their other leads are not simulated, so use the Trick Room section for those.", "Their other leads are not simulated.")

# speed table: [speed, yours, theirs, tie note]
R = r'''const R=[[36,"Torkoal","Torkoal (Quiet), Mega Camerupt","Tie"],[40,"","Torkoal (Modest)",""],[44,"Hatterene","Hatterene","Tie"],[60,"","Mega Golisopod",""],
 [63,"Kingambit","Kingambit (Brave)","Tie"],[70,"","Kingambit (Adamant, the most common)",""],[71,"","Kingambit (1 Speed point)",""],
 [72,"Farigiraf","Farigiraf (Relaxed, Quiet), Grimmsnarl (Sassy), Incineroar (Brave, Sassy), Kingambit (2 Speed points)","Tie"],
 [80,"","Incineroar (Careful, Impish), Farigiraf (Bold, Calm), Grimmsnarl (Careful), Sylveon (no Speed points)",""],[83,"","Incineroar (3 Speed points)",""],
 [85,"","Armarouge (Quiet), Pelipper (Modest, no Speed points)",""],[87,"","Corviknight",""],
 [88,"Mega Blastoise","Mega Blastoise (Quiet), Sylveon (8 Speed points, its most common)","Tie"],[90,"","Sinistcha, Politoed",""],
 [91,"","Mega Tyranitar (no Speed points)",""],[93,"","Politoed (3 Speed points)",""],[94,"Indeedee","",""],[96,"","Pelipper (11 Speed points)",""],
 [102,"","Kingambit (max Speed)",""],[105,"","Indeedee (Bold), Archaludon",""],[107,"","Rillaboom",""],
 ["127+","","Everything else, including most Mega Blastoise (130: Modest, max Speed), Mega Tyranitar, Gholdengo, Mega Gardevoir, Sneasler, Mega Salamence and Mega Raichu Y",""]];'''
h = re.sub(r'const R=\[\[36,.*?\]\];', lambda m: R, h, count=1, flags=re.S)
h = re.sub(r'<p class="snote">Lowest moves first\..*?</p>',
           '<p class="snote">Lowest moves first. Your six are shaded; the others are the most common opposing spreads on the Showdown ladder '
           '(Smogon&rsquo;s August stats, the latest published) and in tournament sets, with the Speed points each spread uses. Equal numbers are a coin flip.</p>', h, count=1, flags=re.S)
NOTE = ('<p class="body spdnote"><b>Nothing common sits at 89, or between 64 and 69.</b> One Speed point on Blastoise (89) only changes the two 88s, '
        'Quiet Mega Blastoise and Sylveon&rsquo;s most common spread: you move before them without Trick Room and after them under it, instead of a coin flip; '
        'the usual Mega Blastoise is at 130 either way. Your Brave Kingambit (63) only changes the mirror: under Trick Room it moves before every Adamant Kingambit '
        'instead of tying the 70s, and without Trick Room it moves after the 70s instead of tying them. Sylveon&rsquo;s spreads are scattered from 80 to 103.</p>')
h = re.sub(r'\n  <p class="body spdnote">.*?</p>', "", h, flags=re.S)
h = h.replace('<div class="tscroll"><table class="spd" id="spdt"></table></div>',
              '<div class="tscroll"><table class="spd" id="spdt"></table></div>\n  ' + NOTE, 1)
if ".spdnote{" not in h:
    h = h.replace("table.spd td.tie{", ".spdnote{margin-top:14px}\ntable.spd td.tie{", 1)
if "table.spd th,table.spd td{padding:8px 7px}" not in h:
    h = h.replace(".spdnote{margin-top:14px}", ".spdnote{margin-top:14px}\n@media(max-width:600px){table.spd th,table.spd td{padding:8px 7px}table.spd td.s{width:40px}table.spd td.who{font-size:13px}}", 1)
open(SRC, "w", encoding="utf-8").write(h)
print("ok", len(h))
