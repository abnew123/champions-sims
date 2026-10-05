# Recorded games

The user's recorded ladder games, transcribed turn by turn from the OCR timelines and frames in `recordings/batch1`, `batch2` (those
stay git-ignored: they show in-game names). No names here: "you" are p1, "the opponent" is p2. `recorded.py` turns these into engine
positions and the page.

One file per game. Fields:
- `mine`: your four in brought order (keys of `pssim/myteam_c_incin.json`); `my_overrides`: set changes for these games (Brave Kingambit).
- `theirs`: their four as far as the game showed them, in the order they appeared. Each starts from the Smogon M-C set of `from` (else of
  `species`), with what the game revealed laid on top (`moves` listed first, then the set's own moves fill up to four; `item`, `ability`; `guess`: the item is
  a guess, so the page does not show it).
- `candidates`: when one of their four never came in, the team-preview Pokémon it could have been, weighted by how often each is brought
  when on team preview (Reg M-C Bo3 replays). The bar averages over them.
- `turns`: the position at the start of each turn. Per side, only what changed since the previous turn: `slot` (a, b, or "" for the
  bench), `hp` (your HP points) or `pct` (their HP percentage), `b` (stat stages, replacing the old ones; cleared when a Pokémon leaves
  the field), `mega`, `gone` (item used up), `st` (status), `f` (fainted). `stall`: Pokémon that Protected successfully the turn
  before. `field` is given in full every turn (turns left). `acts`: what each slot chose, when the recording shows it. `events`: what
  happened in the turn, for the page.
