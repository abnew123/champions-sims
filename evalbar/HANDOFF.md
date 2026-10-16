# Eval bar thread: handoff (2026-10-05)

The user wants an evaluation bar for Pokémon Champions doubles games, like the engine bar on a live chess broadcast: for every turn of a
game, the current win chance and the best options for each Pokémon on the field, so a game can be commentated. This thread builds it.
Read the root `HANDOFF.md` first bullets (threads, git rules, the current battle-sim setup) after this file.

| Thread (session name) | Owns |
|---|---|
| **Eval bar** (you) | `evalbar/`: replay-to-position code, the evaluation pipeline, the page |
| **Battle sim** | `native/champ/` (the engine and planner, `champ` binaries), the position value (`pssim/egvalue*.json`), replay analysis in `pssim/` |
| **TR sheet** | the team sheets and the sheet kit (`sheetkit/`, `sheets/`, `trsheet/`) |
| **Team search** | `teamsearch/` |

Talk to the other threads directly with SendMessage; do not relay through the user. You use the engine as a tool. Do not edit
`native/champ/src`, `pssim/egvalue*.json` or the other threads' folders: ask **Battle sim** for engine or value changes (list below).

## State (2026-10-05, end of the first session)

Built, all in `evalbar/` (run the Python from the repo root; `common.py` finds the main folder's git-ignored data when run in a worktree):

- `replay.py`: log -> per-turn position (for the page and for the engine rebuild), what happened each turn as text, and what each slot
  chose. No usernames or nicknames leave it; checked on all 4,530 cached Bo3 logs (no errors).
- `build.py <replay id> [accuracy json]`: writes the page for one game to `evalbar/out/` (git-ignored) from `page.html`; `build.py pick`
  lists good demo games. The published page (private artifact, version 0, bar only): https://claude.ai/artifact/TuFFPZuzKoeo8w4Cx9NiRQ
  (republish `evalbar/out/eval-bar.html`, a copy of the built page, to keep that URL). The page already has a per-Pokémon options panel
  that shows when a step carries `opt` (`{p1: [{mon, played, options: [{l, w, v, played}]}], p2: [...]}`); nothing fills it yet.
- `accuracy.py`: out-of-sample scores (five folds by game). **Version 0 baseline: log loss 0.549, favourite won 70.3%, calibrated**
  (`results/accuracy_v0.json`); with engine result files as arguments it scores the engine value, static value, refitted features and
  version 0 plus engine on the same positions.
- `spots.py` + `positions.js`: every turn of a game rebuilt as an engine state, from each player's side, with the choices actually made.
  Coverage: 4,254 of 4,530 games (30,598 positions): 2,684 games clean, 1,140 with a stand-in for a brought Pokémon that never appeared,
  430 with moves or items the engine data lacks dropped from the sets; 210 games need a species or ability the engine lacks, 32 use
  Illusion or Transform, 34 have no turn; about 900 positions come after a Perish Song (flagged). Today's `champ spot` runs on
  these states (smoke test: turn 2 of the demo game, symmetric within seed jitter) but playouts cost about 1.5 s per game on one thread.

- `engine.py`: `positions` builds engine positions for chosen games or a fixed shuffled sample; `run` calls Battle sim's
  `champ-battle-v13 evalpos` with the bar's settings (`egvalue9_sym.json`, `RACE=1 RACE_TIES=avg TRSYM=1`, empty `GRID_DIR`, `EVAL_SEEDS`).
  One line per position: the one-turn equilibrium value, the static value and feature vector, and for both sides every option per slot
  with its weight and value. About 5 s per position at 8 seeds on one thread (turn 1 is the slowest), 21 s at 32 seeds.
- `status.py`: this thread's cards on the shared progress page (http://localhost:8766, root `status_server.py`, which looks for
  `evalbar/status.py` in the main checkout and else in the newest worktree). `engine.py run` writes the stamp a card is drawn from
  (`out/<output>.run.json`; `EVAL_TITLE` names the card).
- `build.py <id> acc=... engine=<evalpos output> pos=<positions>` fills the page's options panel. The published page (version 2) shows the
  demo game with the version 0 bar and the engine's options at 32 seeds.

**Result (2026-10-05, 560 held-out games, 3,968 positions, staged 32 samples, `results/accuracy_engine.json`):** the engine's one-turn
value, rescaled to real outcomes (log-odds times 0.744), has log loss 0.525 against version 0's 0.568 on the same positions (difference
-0.043 ± 0.009 by game resampling), favourite won 72.3% against 69.0%, calibrated in every 10% bucket, and is better at every turn
number. Adding version 0 to it adds nothing; the static value (-0.010) and the 20 features refitted on real games (-0.009) gain little.
Caveat: the engine knows each side's whole brought four and their sets from hindsight; version 0 only knows how many are left. The
published page (version 3) takes its bar from the rescaled engine value: `build.py <id> acc=evalbar/results/accuracy_engine.json
engine=... pos=... cal=0.7438`. The rescale weight depends on the sampling (flat 8 samples gave 0.56), so refit it if the mode changes.

**Recorded games (2026-10-05, the user asked):** `games/*.json` are the user's five recorded ladder games (recordings/batch1, batch2,
read-only; TR sheet owns that pipeline) transcribed turn by turn by hand from the OCR timelines and frames (`games/README.md` has the
format). `recorded.py positions out/rec_pos.jsonl`, `engine.py run out/rec_pos.jsonl out/rec_eval.jsonl`, `recorded.py page
out/rec_eval.jsonl out/rec_pos.jsonl` -> `out/recorded.html`, published as https://claude.ai/artifact/L5i4RRKHCc4Bf2MXDqiAde (republish a
copy named `out/ladder-games.html`). Your side is p1 ("You"), sets from `pssim/myteam_c_incin.json` with Brave Kingambit (the recordings
show Torkoal at 177 HP, i.e. 32 HP points); the opponent's from Smogon M-C sets plus what each game revealed; an unseen fourth is averaged
over its team-preview candidates. Caveat: `egvalue9_sym.json` weights Trick Room turns at 0.07 against egvalue9's 0.26, so the one-turn
bar may undervalue setting Trick Room (asked Battle sim).

**Two views of the recorded games (the user asked, 2026-10-05):** "as you saw it" (default) knows only the team preview, the Pokémon
that had come in (as they looked: Illusion fools it until it breaks) and what they had shown by the start of the turn; every set of
preview Pokémon they could still have brought is evaluated and averaged, weighted by bring rates (`hypotheses()` in `recorded.py`).
"With hindsight" knows their four and every reveal from turn 1. The opponent's unrevealed sets are the most common Reg M-C set per species
from the Bo3 team sheets (`recorded.py commonsets` -> `results/common_sets.json`: item, ability, nature, top four moves, bring rate;
stat points from the Smogon M-C set of the form played). Positions: `recorded.py positions` writes both views (names `<game> t<n>
seen<k>` / `hind<k>`). The as-seen view uses the same rescale as the hindsight bar and is not separately calibrated; it could be,
on the replay cache (open sheets, only the brought four hidden). Kept for review of finished games, not for use during a game.

**Live spectator mode (the user asked, 2026-10-05):** `live.py list [bo1|bo3]` lists ongoing Reg M-C battles (rating and link; Bo3
rooms carry no rating, so newest first); `live.py watch <room or URL> [threads=2] [port=8768]` joins the room as a guest through
`live_feed.js` (Node with `--experimental-websocket`; no account), evaluates each turn as it starts, and serves the page at
http://localhost:8768 (it polls `data.json` and follows the latest turn). It knows what a spectator knows: team previews, Bo3 open team
sheets (Bo1: the common set per species plus reveals: moves used, items that activated, Mega stones, abilities the species can have),
the Pokémon that came in and their state. For each player the three most likely unseen combinations (`recorded.py back_weight`, given
the leads) are paired, so up to 9 positions a turn (turn 1: about 9 s on one thread). Each turn is built from the log as it was when the
turn started (`Live.upto`), so nothing later leaks back; the choices made fill in the "played" tags once the turn is over. Files stay in
`out/live/` (the log has usernames). For watching other people's games only: never on a game the user is playing, and nothing passed
to a player during their game (the page says so).

**Value file (2026-10-05):** the bar now uses `pssim/egvalue9_sym2.json` (Battle sim: the symmetric value with Trick Room turns tied to
the HP weight at the real-game ratio), rescale weight 0.7538. On the 560-game set it is no worse overall (log loss 0.5240 against sym's
0.5245) and better with Trick Room up (0.5141 against 0.5199, within noise): `results/compare_sym_sym2.json`; `results/accuracy_engine.json`
now holds sym2's numbers. The recorded-games page (version 3) and the replay demo page (version 4) use it.

**Champions broadcasts (the user asked, 2026-10-05; for watching on their own computer, no restreaming):** `broadcast.py` reads an
official broadcast's video into the same battle log the live mode follows: the open team sheets the broadcast shows before the match
(matched to the left / right player by the scoreboard names, kept in memory only), the four HP boxes (percentages), the battle text
(Player 1 = left; "the opposing ..." = right) and the decision screen ("Trainers are choosing actions") as the turn boundary; one log per
game of the set ("The Trainer lost!" ends a game; the winner is the side with Pokémon left). `watch <YouTube URL> [start]` follows a stream
(or a recording from a time) in real time through yt-dlp, ffmpeg (2 frames a second) and Apple Vision (`recordings/ocr`), and serves the
page with a game picker; `frames`, `ocr`, `read`, `replay` are the offline steps. Tested on the Frankfurt Regional VOD, match 1 (1:44:09):
game 1 read in full (10 turns, Player 1 won; bar 37 61 67 30 52 72 73 65 92 95), game 2's first 5 turns; about 2-7 s a turn on 2 threads
with the full engine data (`champ-battle-v17`, `engine_data_full.json`). It needs both team sheets: started after they were shown, it
waits for the next game. Files stay in `out/` (frames and logs show the players' names).

Possible next steps (not asked for yet): more demo games, flagging Perish Song positions on the page, Battle sim extending the engine data
(210 games need a missing species or ability), step 2 (the user's recorded games, a belief over the opponent's hidden sets).

## Scope the user approved: step 1 only

A prototype on **Showdown replays** (exact logs, so no video parsing): a page that steps through one game turn by turn and shows
1. a win-chance bar (player 1 vs player 2),
2. for each Pokémon on the field, its best options with how often the planner would click each and what each is worth,
3. what happened that turn,
and a measured accuracy number for the bar on the cached replays. Not in scope yet: the user's own recorded ladder games (step 2: needs
the recording pipeline to rebuild every turn, and a belief about the opponent's hidden sets) and live use (step 3).

Fair play: this is for commentary on finished games and replays. Never frame it as help during a game the user is playing.

## What already exists

1. **Replays.** `pssim/replays_protect/*.log`: about 5,300 public Showdown logs (git-ignored: they contain usernames), with
   `index.json` (`fmt`, `rating`). 4,496 are Reg M-C best-of-three games, which have open team sheets (`|showteam|` lines: species, item,
   ability, moves, nature; stat points are not shown). Fetch more with `python3 pssim/protect_replays.py fetch <pages> bo3` or
   `rated <pages>` (highest-rated first; about 0.3 s between requests).
2. **Log parsing.** `pssim/replay_feats.py`: `game(log)` replays a log event by event and returns, for the start of every turn, eleven
   position features from player 1's side (HP share, Pokémon left, boosts, Trick Room turns x speed edge, Protected last turn, type edge,
   asleep, paralysed, burned/poisoned, Tailwind turns, screen turns), the winner and the players' mean rating; `parse_team` reads a team
   sheet. `pssim/protect_replays.py`: `acts(log)` gives each turn's action per slot (move or switch, Protect success).
3. **A calibrated win chance with no engine.** `pssim/results/fit_real_value.json` (git-ignored, present locally; rebuild with
   `fit_real_value.py`): a logistic model on those eleven features fitted on the 4,496 games; `real` = [intercept, 11 weights]. On real
   games it sits on the diagonal (positions rated 3.5% / 28% / 72% were won 2.6% / 29% / 71%; `pssim/protect_decided.py real`). This alone
   draws a reasonable bar: use it as version 0 and as the baseline every later version must beat.
4. **Engine evaluation of a position.** `native/spot_starts.js` rebuilds a mid-game position in Showdown (teams in brought order, HP,
   boosts, Mega Evolution, fainted, status, volatiles, items used, Trick Room / weather / terrain with turns left) and exports it;
   `champ spot <engine_data.json> <spots.jsonl> <out.json> [threads] [playouts]` then solves the turn: every joint action of side 0 against
   side 1's likely replies, each cell played out to the end by the planner, and reports per option its value against the opponent's
   equilibrium mix (`v`), its one-turn value, its weight in side 0's own mix (`eq_weight`), plus side 1's reply mix and the position's
   value. Example input and output: `recordings/spots.json`, `recordings/review_v2.json`. It was written for "the user's team vs an
   opponent" (my sets from `MYTEAM`, theirs from `regionals/smogon_mc_sets.json` with revealed details laid on top) and reports options for
   side 0 only; for replays you need both sides explicit and options for both. `native/battle_starts.js` shows explicit sets for both sides
   (`{mine: [4 sets], theirs: [4 sets]}`) at turn 0. Write your own builder in `evalbar/` (it may `require` `pssim/t1sim.js` for `toSet`
   and `native/export_state.js` for `exportState`; run node scripts from `pssim/`, where `node_modules` lives).
5. **The planner setup** (root `HANDOFF.md`, "Current battle-sim setup"): `native/champ/bin/champ-battle-v12` is the whole `champ`
   program (`battle`, `spot`, `plan` subcommands), value file `pssim/egvalue9.json`, `RACE=1 CALC_DATA=../native/champions_data.json`.
   One planner turn costs about 0.6 s on one thread.
6. **Stat points for sets.** Team sheets do not show them. `regionals/smogon_mc_sets.json` (259 species, most common spread) and
   `regionals/opp_sets_blend.json` give defaults per species.

## Things that will bite

- **The sim's value is written from side 0's point of view.** `egvalue9.json` has a non-zero intercept (a strong team bringing its best
  four) and two matchup-grid features that only exist for a side-0 team with a prepared grid. For a replay, players 1 and 2 are
  arbitrary, so the bar must be symmetric: intercept 0, grid features off (point `GRID_DIR` at an empty folder: the features then read 0),
  and `TRSYM=1` so either side may reverse Trick Room. Check symmetry directly: swapping the two sides of a position must give
  1 minus the value. Ask Battle sim for a symmetric value file fitted for this purpose rather than editing weights yourself.
- **Hidden information.** Which four each player brought is only revealed as Pokémon appear, and stat points never are. For step 1 use
  hindsight (everything revealed anywhere in the log) and default spreads, and say so on the page. A proper belief over sets is step 2.
- **Engine coverage.** The engine data covers the top 99% of Reg M-C usage; a few alternate forms and mechanics are missing (each game
  result lists `unsupported`). Count and skip positions you cannot build, and report the coverage.
- **Luck.** The planner scores each option on two random seeds, so values jitter. A bar should average over more seeds, or over the
  chance events themselves; ask Battle sim.
- **Perish Song** games: the planner cannot play the trap; flag them rather than trust the bar there.

## What to ask Battle sim for (it has offered)

- A features dump for arbitrary positions (`champ feats`-style: the planner's full feature vector, damage race included, for each state
  in a file), so a value can be fitted on real replay positions and outcomes.
- Options and values for both sides from one call, and a root evaluation averaged over luck.
- A symmetric value file for the bar, and later one fitted on real games with the full feature set.

## Suggested order

1. Version 0: log -> per-turn features (`replay_feats.game`) -> the real-game model -> a page with the bar and each turn's events.
2. Engine version: log -> full position per turn -> `champ spot`-style evaluation -> the bar plus per-Pokémon options.
3. Accuracy: on held-out cached games, calibration by bucket and log loss per turn for version 0 and the engine version; the engine
   version should beat version 0 before it replaces it. Then show the user one game end to end.

The page: a self-contained HTML page published as a private artifact (load the artifact design skill first). Players are "Player 1"
and "Player 2": no usernames on the page, in tracked files or in commit messages.

## How closely top players follow the engine (study.py)

`study.py <ocr .jsonl>` evaluates every turn of every broadcast game as the players knew it and compares each Pokemon's choice with the
planner, by action (the move, compared with its best target, or the switch). Day 1 of the regional VOD (reader with targets and popup slots,
2026-10-06): 469 decisions; players took the planner's top pick 45% (17% by chance), the planner put 39% on what they played (57% if they had
followed its mix), median regret 0.3 points. `study.py publish <ocr .jsonl>` writes `results/broadcast_study_day1.json` (measures, per game,
the costly plays: planner under 5%, over 5 points against its top action, with VOD times).
Players Protect more than the planner (13% vs 8.5%). Battle sim's two-turn horizon (EVAL_HORIZON=2, champ-battle-v18) raises planned Protect
to 11% on these games and on a Showdown subset, so about half the gap is depth; top-pick agreement does not improve, and the log-score gain
seen with 2 samples was mostly sampling noise (Battle sim's 4-sample check). Battle sim's reading of the rest: the planner knows exact sets
and spreads that players do not (testable here by evaluating with a few spread/item variants per Pokemon).

## Does spread uncertainty explain the gap? (uncertain.py)

Battle sim's idea: players do not know the opponent's stat points (the sheet shows item, ability, nature, moves), the planner is handed one
spread. `uncertain.py build / run / report` re-solves every day-1 turn with each player's mix taken from the payoff matrix averaged over 4
draws of the opponent's spreads (Smogon spreads with the sheet's nature, plus an offensive and a bulky one; same 32 samples per cell as the
known version; the solve reproduces evalpos's exactly). Result (444 decisions, `results/spread_uncertainty_day1.json`): no change toward
players. Planned Protect 8.7% -> 8.8% (players 13.3%), top pick 45.3% -> 43.7%, log score -2.091 -> -2.053 (+0.04, SE 0.07), mixes no
flatter. So what remains after the two-turn horizon is not spread knowledge. Of the 39 costly plays, 13 are switches, 10 Protects and 5
setup moves: the user's reading (2026-10-06) is that many are the engine undervaluing setup and switches, some real mistakes.

## Does the engine undervalue setup and switches? (aftermath.py)

Battle sim asked for a real-outcome test (2026-10-06): in the cached Showdown Bo3 games, positions right after a setup move, a chosen
switch, or with boosts held, the side's actual win rate against the engine's rescaled rating (`aftermath.py`; per-position rows with
markers in out/aftermath_rows.jsonl for Battle sim to fit). 3,408 positions: after setup -3.2 points (SE 2.7, n 397), holding boosts about
0, after a switch +0.7 (SE 0.9) with the lookahead and +1.9 (SE 0.9) for the static value. So the resulting positions are rated right:
the engine's reluctance to set up is not a misrating of the boosted position, and switches are underrated by at most ~2 points by the
value function alone. Summary in `results/aftermath_setup_switch.json`.
Players set up about twice as often as the planner (regional day 1: 4.7% of decisions vs 2.7% planned; Showdown Bo3: 3.3% vs 1.4%), and
their setup moves carry about twice the regret of their other plays (3.6 and 4.3 points vs 1.8 and 2.1). With the boosted positions rated
right, that reads as players overvaluing setup (the user's guess: habits from single-player games, where setup sweeps).

## What is a read worth? (influence.py)

The user's question (2026-10-06): if a player could make the opponent put an extra 20% on one option, how much does playing to exploit it
gain over equilibrium play? On the day-1 turns' full matrices (`influence.py`, exact equilibria by linear programming): about 4 points of
win chance per turn at 20% (2 at 10%, 6 at 30%, 11 at 50%), about 31 points summed over a game (an upper estimate: gains saturate). Equilibrium
play gains almost nothing from the lean (0.1 points), and the exploiting move costs almost nothing if the read is wrong (0.1 points): in 93%
of turns it is one of the reader's equally good options (4 per turn, median), so a read mostly decides between options the equilibrium is
indifferent between. Timing (the user's follow-up): a 10% lean every turn (15.3 points a game) and a 20% lean on the best third of turns (16.0)
are about even, because gains are close to linear in the lean and the best third holds 53% of a game's read value; a 20% lean on a random
third gives 10.2. Turn 1 reads are worth the most (5.1 points at 20%), later turns 3.5 to 4.6. Summary in `results/read_value_day1.json`.

## Were the costly plays reads? (reads.py)

`reads.py run` evaluates the costly plays' turns with the full payoff matrix (champ-battle-v18, EVAL_MATRIX=full); `reads.py report` scores
each play against what the opponent actually did (exact where the reader found targets) and lists the opponent lines that would have made it
better than the planner's pick, with how far the opponent's mix would have to lean to break even. Day 1: 11 of the 39 did at least as well
as the pick against the actual play (6 of those needed a lean under 20%: plausible reads of a habit); the rest did not, most clearly the
Protects the one-turn engine undervalues. Summary in `results/broadcast_reads_day1.json`.

## Positions for the Showdown bot (botpos.py, 2026-10-10)

Battle sim's ladder bot (bot/, the planner on its own account) asked for its decision positions. `botpos.bot_position(log, request, side,
topk=1, team=None)` builds the turn's specs with the bot as side 0: the opponent as a spectator knows it (live.py's sets, reveals and back-row
hypotheses, topk of them), the bot's own side from its |request| (the four it brought, exact HP, status, fainting, held item) over what the
log tracks (boosts, volatiles, the lock), exact spreads from a Showdown export if given. `live.positions(specs, outf)` then writes them (line
'<name> p1' is the bot's view). Team preview and replacements after a faint are not turn starts: it returns no specs and says why. PP is not
modelled. Checked on three cached Bo3 games from both sides (the two views mirror each other) and with an exact-HP request.
`bot_replacement(log, request, side, replacements)` answers a forceSwitch: the next turn's start with the chosen replacements in, the
switch-in abilities from rules.derive, and the opponent's own simultaneous replacement branched by back-row odds. `decisions(log, side)`
fakes every decision of a saved game (preview, turns, replacements, with what the player chose) for end-to-end tests; `python3
evalbar/botpos.py 400` built all 5,492 turns and 1,577 replacements of 400 saved games. replay.py now revives a Pokemon that Revival
Blessing heals in the back.

## The bot's games on the eval bar (live.py bot, 2026-10-11)

`live.py bot <room> [threads] [port=8769]` follows a game of the Showdown bot from its own log (bot/out/<room>.log in the main checkout):
the bot's side as its |request| shows it (the four brought, exact HP and items; logged just after each |turn| line) with its spreads from
bot/teams.json, the opponent as a spectator sees it, and the page names the bot's real back row. No rules checks (the log is Showdown's
own). On the first ladder game it cut the positions from 9 a turn to 1-3. The bot wrote its room log only when a game ended; Battle sim
now writes it on every |request| and |turn| (bot/client.js), so a game in progress can be followed. `live.py bot [threads] [port=8769]` (no
room) runs BotRunner: the bot's newest game when it starts, then each new battle log that appears in bot/out, all on one page (the page
moves to a new game when it is showing the latest one). A turn waits up to 15 s for its request before it is evaluated without it. Port
8768 stays the stream watcher's (auto.py). BotRunner starts with the last 12 hours' ladder games (room numbers of six digits or more; bot/out also
holds Battle sim's local test games). The bot is always Player 1 on these pages (the user asked, 2026-10-11): live.bot_first swaps every side
reference in the bot's log (p1/p2, p1a, "id":"p2" in its requests) when its requests say it is p2, before anything reads it.

## Luck (2026-10-11)

The user's idea: how much of the win-chance movement came from randomness. For each turn, luck = the value of the position the turn left
(the next turn's start, or the result after a last turn won outright) minus what the choices both sides actually made were expected to
give: the payoff table's cell for the actual joint actions (evalpos EVAL_MATRIX=1, at full seeds), a slot whose choice the log does not
show weighted by that side's mix (build.expected). Both sides of the difference use the value function before any lookahead ('static'
at the next turn), since the solved value of a position can differ a lot from it (0.26 vs 0.72 on one turn 1). Values rescaled with CAL;
weighted over the hypotheses. A reveal of an unseen Pokemon counts in. The page shows each turn's luck under its events and the game total
as a chip. It runs after a game, for reviews, not during it (the user, 2026-10-11: live evaluation must not slow down): when a bot game
is over, Live.luck_pass evaluates its turns again with EVAL_MATRIX=1 into <tag>_luck.jsonl, one engine thread at nice 19, one game at a
time (LUCK lock), apart from the live evaluation's WORK lock; the game's total shows once every turn is done. EVAL_MATRIX makes the engine
about 3x slower (22 s -> 61 s for a 6-turn game). The first check, a crit Wave Crash KO on a Mega Charizard Y, was +34 for the bot; over
62 turns of the first bot games luck averaged +0.5 points (sd 9). A move stopped by Armor Tail is now the user's choice (replay.py), or
its unknown choice made one turn look like +48.

## Opponents' spreads (spreads.py, 2026-10-11)

Checking the three unluckiest bot games (the user asked whether it was luck or play) found their big swings were spread errors. The bot's
own spreads had been guessed for teams outside bot/teams.json (botpos.spread now solves them from the stats in its requests), and the
opponent's Gholdengo was guessed with no Speed: spots.evs_for used the Smogon top set only when its nature matched the sheet and fell back
to a plain HP / attack spread. With Tailwind or against a 108-Speed Archaludon that flips the turn order, so certain KOs read as -45 to -57
luck. Now (the user's design): the species' Smogon spreads in order of use with the sheet's nature (spreads.ranked, from the moveset file:
the top six or so, "Other" is about half), the most used one the game has not ruled out (spreads.pick). What rules a spread out: the order
two Pokemon did things in, when the other one's Speed is exact (a bot's own): who moved first at the same priority, whose switch-in
ability went first as the battle began, who switched out or Mega Evolved first at the start of a turn, and who took or regained HP first
from the same end-of-turn effect (sand, poison, burn, Leftovers, Black Sludge, Grassy Terrain, Leech Seed, Salt Cure) or counted down
Perish Song first (the user's point: speed shows in more than move order). Counted: Tailwind, Trick Room (reverses all of these),
paralysis, stages, Choice Scarf, weather abilities (by replay.py's weather names), a Mega's own ability (Mega Swampert's Swift Swim) and
Speed. Skipped: Grassy Glide pairs, turns where Speed or the field changed between the two, Quick Claw, After You and the like,
Unburden, Quick Feet, Speed Boost (spreads.observations). Over the bot's 117 games: 732 observations (447 moves, 185 end of turn, 37
battle-start abilities, 37 switches, 26 Megas); of 272 opponent Pokemon with any, 250 kept Smogon's most used spread, 12 the 2nd or 3rd,
6 the plain guess, 4 needed their Speed points moved, none contradicted every spread (the weather-name and Mega-ability bugs had made 15). Every listed spread ruled out: the top one with its Speed points moved as little as fits.
Spectator pages get the nature-matched ranking (evs_for); bot pages and the bot itself (botpos.refine_opponent) also the turn order.
Damage is not used yet. After it: luck on the three games -91 -> -32, -89 -> -6, -79 -> -13. Older studies used the old spreads.

## Damage checks on spreads, and three Mega abilities (2026-10-11)

The user asked for damage to rule spreads out too. spreads.damage_observations: hits between a bot's Pokemon and an opponent's where
nothing changed either one's stats, item or form, or the weather, terrain or screens, earlier in the turn or earlier in the same move
(Electro Shot's charge); the bot's HP is exact (damage d), the opponent's in percent (an interval through the possible HP values); a KO,
Focus Sash or Sturdy says the hit did at least that. damage.js asks Showdown (positions.rebuild, getDamage at the lowest and highest
roll, the move's type changes applied first) for each candidate spread's range; cached per hit and spread. Not used: multi-hit moves,
fixed damage, damage that depends on the turn order (Payback, Analytic, ...), Substitute, Disguise. spreads.pick takes the most used
spread that fits the turn order and the hits; when the hits rule every one out, the one missing the fewest. Over the bot's 117 games:
795 hits; of 383 opponent Pokemon with any observation, 315 kept Smogon's most used spread, 35 the 2nd to 6th, 10 the plain guess, 23
missed some hit with every listed spread (about half of each species' use is outside the listed spreads). Bugs found on the way: HP
tracking re-read switch lines, lines inside a move's block did not count as mid-turn changes (a Light Screen), and three Megas: this
Showdown package (pssim, 0.11.11) gives Mega Golisopod Emergency Exit, Mega Garchomp Z Sand Force and Mega Absol Z Magic Bounce, where
the engine data (and the damage seen in real games) has Tough Claws, Levitate and Sharpness. positions.js now sets a Mega's ability from
engine_data_full.json, which every engine position goes through (the bar, the studies, the bot).

## Mega Evolution on the live pages (2026-10-11)

The user saw a Froslass shown as "Protect (and Mega Evolve)" on the turn before it actually Mega Evolved. champ-battle-v23 offered a Mega
Stone holder's moves only with the Mega, and build.same() ignored the Mega flag, so a plain Protect matched "Protect (Mega)". live.py now
runs champ-battle-v25 (the bot's build: moves with and without the Mega, EG_MEGA_TIE tie-break toward the Mega), and same() matches the
Mega flag whenever both versions are offered. Older results (studies, Louisville) were made with v23.

## Trapping, sleep and Yawn in positions; the Yawn study (2026-10-12)

- Trapping: positions.js runs Showdown's TrapPokemon / MaybeTrapPokemon events on the rebuilt position (as Showdown does at the end of a
  turn). The engine takes the root's `trapped` flag as given, so before this a side facing Mega Gengar's Shadow Tag (or Arena Trap, Magnet
  Pull) was offered switches it did not have. 18 bot games were redone. The bot builds through positions.js too, so it got this at once.
- Sleep: Champions sleep counters are 2 (1/3) or 3 (2/3) (the champions mod's slp onStart; the engine's conditions.rs), counted down at each
  attempt to move, so a Pokemon sleeps one turn or two; switching out pauses it. live.sleep_cases splits each sleeping Pokemon on the field
  by its counter (names get s2/s3), less the turns slept (Early Bird counts double); positions.js reads `sleepStart`, default 3. The pages
  use it; the bot does not (Battle sim's call).
- Yawn: a Yawn on the field at a turn start lands at the end of that turn. Specs with `yawnDue` (live.specs_for, and botpos.bot_position
  since the user OK'd it for the bot) get duration 1 instead of a fresh 2. Taunt, Throat Chop and Heal Block still get fresh durations.
- A Pokemon asleep all turn (every move worth the same) shows one row, "Stay in (asleep)", played when the log shows it could not move.
- The bot's Bo1 games (from 2026-10-12) have no team sheets: the page guesses sets as a spectator page does (live.botfmt).
- The bot is frozen (the user, 2026-10-12): positions.js, live.py's spec helpers, botpos.py and spreads.py reach the live bot without a
  restart, so message Battle sim before changing what they build.
- yawn_study.py: after a Yawn, did the player take the drowsy Pokemon out on the next turn? Humans (18.8k Bo3 replays): 228 of 487 Yawns
  where they could (47%). yawn_engine.py runs the engine in those same positions (the player's own four exact, the opponent's back row
  guessed, champions_data_full.json for the calc): its mix leaves 53%; it agrees with the human's choice 64% of the time; humans stay in
  too often with non-Megas (42% vs 54%) and leave Megas more than it does (62% vs 51%); the human choice gives up 1.3 points of win chance
  per Yawn on average (1.8 when staying, 0.6 when leaving). Half the decisions are within 2 points either way. yawn_engine.json has every row.

## Was the bot's bad luck luck? (2026-10-12)

The four unluckiest bot games (−87, −70, −68, −62), checked turn by turn (the user asked). Two were real dice: Game 208's turn 9 (Close
Combat's roll left Farigiraf 1 HP above its Sitrus Berry, then Sludge Bomb rolled high, about 1 in 10) and Game 204 (two 30% Rock Slide
flinches in a row). Two were mostly the model:
- Unburden: Showdown keeps its doubled Speed as a volatile the log never shows; positions.js wiped it, so a Sneasler whose Psychic Seed
  was used up had its normal Speed (Game 108, turn 4: the engine had the Scarf Basculegion first). replay.py now tracks 'unb' and Perish
  Song's count ('perish'); positions.js applies both for specs with `fieldDue` (live.specs_for; not the bot's yet).
- Perish Song's count was never in the positions (Game 24, turns 5 to 7).
- Hidden spreads: Game 24's Charizard survived a Sucker Punch on 1% that the guessed spread (Smogon's most used) could not; one or two
  points of HP more fit. Luck now uses hindsight (Live.at(..., hindsight=True), names with ' L'): each player's Pokemon and the opponent's
  spreads as the whole game showed them, so luck counts the dice. Neither listed Charizard spread fits that hit exactly, so the pick
  falls back to the closest (still the frail one): a search of nearby spreads (points moved into HP or defences) would settle it.
- Damage checks are exact now (`strict`, the user asked why there was 1 HP of slack: there was no reason). spreads.refine(strict=True)
  keeps hits after a mid-turn weather change (a weather setter switching in, a Mega Charizard Y) in the weather they landed in, and
  damage.js with `strict`: a shown percent stands for every HP it could be (Water Spout's power), Psychic Fangs / Brick Break / Raging
  Bull break screens first, the move counts as in use (Aqua Jet, Flip Turn, Wave Crash errored). damage_fits(slack=0). Checked on 40
  random battles between the bot's teams with known spreads (scratch sim.js + check.py): all 806 hits inside the range, none off by 1.
  Live.at passes strict=True; the bot's refine_opponent call does not yet (frozen).

## More unlucky turns, more bugs (2026-10-12, the user asked)

The worst single-turn luck from the luck values made before the day's fixes, leaving out turns whose position or the next turn's had
one of the bugs already fixed (Unburden, Perish, the strict spread changes; luck compares with the next turn's start). Real dice: Games
197, 92, 96, 166, 110 (crits), 129 (the lowest roll, then a crit), 75 (a miss, a paralysed Pokemon moving). Model problems found:
- Two-turn moves: the turn after a charge, positions rebuilt the charger as free, so the engine had Electro Shot charging again in the
  sun (Game 201, −64). positions.js now rebuilds twoturnmove + the move's volatile (targetLoc from where the log shows it fired), duration
  1, trapped as Showdown's request has it (fieldDue). The engine still offers a locked charge both targets (Battle sim is fixing it).
- Luck with a choice the log shows only in part (fainted first, could not move, no target): the expected value took in cells where it
  Mega Evolved, which the log rules out; and Expanding Force spreading in Psychic Terrain lost its target (replay.py `spreadTarget`).
  Game 237's turn 3: 76% expected, 41% with the exact choice.
- Hidden bulk (Games 24, 220, 113, 195): spreads.nearby (strict), see above. Bo1 sets also guess items, which no spread fixes.
- Hidden Speed with the bot's choice unseen (Game 165: its Farigiraf chose Psychic and fainted first, so the opponent's Kingambit was
  faster than guessed). The bot's client now logs `|bot-choice|<rqid>|<choice>` after each request; Live.choice reads it and fills the
  bot's acts where the log shows them only in part (its own games from 2026-10-12 on). Not yet used as a Speed reading.

## The luckiest turns, and replacements in luck (2026-10-12)

The user asked to keep to Bo3 and check the luckiest turns too. Of the 9 luckiest clean Bo3 turns, five were dice (misses, a full
paralysis, ~50% knockouts). The rest:
- Game 36's turn 3 was the charged-move bug; the stale-cache scan had missed it because the page had already rebuilt those positions
  with the fix (approx no longer said 'charging') while the cached results were the old ones. Charged turns are now found from the logs.
- Game 164: hits the spread checks threw away. Strict level 2 (the eval bar's; the bot is at 1): a hit after the turn changed a stat
  stage (Intimidate, Defiant) is kept with the change applied, and a multi-hit move's first hit counts (crits read per hit).
- Game 120: a replacement choice counted as luck. Within the luck's payoff cell, evalpos settles faint replacements and pivots by its
  own equilibrium, so a player sending in something else showed as luck (+30). Battle sim added actual_replace to evalpos
  (champ-dev-2026-10-12b): live.replacements reads them from the log (switches after the turn's first move, and after faints), the
  luck pass runs that engine (LUCK_BIN, link evalbar-champ-alt), and build uses its actual_cell where every choice is known. Still to
  come: actual_cell for partly known choices (asked Battle sim).

## Bug hunt beyond luck: hook audit and reachability check (2026-10-12)

The user asked for ways to find bugs without luck swings. Three parts; Battle sim's differential testing (engine against Showdown, now
from mid-battle positions of real sheets) is theirs and found several engine bugs the same evening.
- hook_audit.py: Showdown's hooks for every effect on real sheets against the engine's handlers (cval constants and named-list loops
  counted), ranked by use, in hook_audit.json. Battle sim ports from it (batches 4 to 7).
- reach.py / reach.js: each turn rebuilt in hindsight and played in Showdown with the log's choices and replacements, over seeds plus
  extremes (every chance, none, the typical turn, every added effect, each at both rolls); every next-turn feature checked against what
  the runs reached. Bot games (`reach.py`) and the cached replays (`reach.py replays k/n`, resumable, a progress card per share; each
  worker is about 2 cores with its node child), `reach.py recheck <file>` for a share's unreached turns, reach_mechanics.py ranks the
  mechanics in unreached turns. 117,104 replay turns, no errors; of the 71,663 with every choice known, 2.9% leave a feature unreached,
  mostly knockouts that turn on hidden spreads.
- Found and fixed: percent-to-HP rounding (pctDue), the bot's fainted slot a (own_side slots=True), abilities gained in battle
  (abilDue), exact Speed and no tie slack (strict 3), Baton Pass handing on stages and effects (replay.BATON_PASS: 85% of Baton Pass
  turns unreachable before, 10% after). Harness-only fixes: a locked charge takes no target, a self-target (Curse) is no target, Revival
  Blessing picks a fainted Pokemon, a move the log shows without a target is a guess (partial), certain events stay certain in the
  extremes. Still above the base rate: Imposter, Moody (random), Baneful Bunker 32/342, Aura Sphere 60/703, Draining Kiss 33/409.
- mega_check.py (`run k/n`, `report` -> mega_check.json): every clean hit a Mega gave or took in the Bo3 replays (53,074 hits over 18,782
  games) against damage.js, by class (own-type / other moves given, contact / other hits taken), each against the same class among non-Megas.
  It found Mega Lucario Z's Aura Guard (Battle sim, cb9cf51) and three rebuild gaps, fixed behind flags the bot does not set yet:
  replay.MEGA_ABIL (a traced ability kept after Mega Evolving: Trace Mega Gardevoir lost Pixilate), fallenDue (Supreme Overlord's count),
  typeDue (Soak, Protean / Libero, Double Shock, Burn Up, Forest's Curse; damage.js applies Protean as it hits). The rest of the table moves
  with spreads (bulkier than Smogon's: Mega Floette, Gardevoir, Froslass; more offence: Mega Staraptor, whose Smogon spread has 2-4 Atk), which
  popfit.py fits (`collect k/n`, `fit` -> default_spreads.json, for review; nothing reads it yet). Mega Delphox gives and takes about 5% more
  than predicted with Smogon's spread already all Sp. Atk and no bulk: unexplained.
- setguess.py: Bo1 set guesses from the rest of the team. Every Bo3 six with the species counts, weighted 20^(shared teammates - 5)
  (teams are built around cores, the user's point), with naive Bayes on single teammates as the fallback, then filtered to what has been
  revealed. Held out by team, the whole set right 24.6% (the species' most common set) -> 40.2%. live.sets_for's Bo1 branch and the bot's
  bo1.guess (Battle sim's flag) use it; `build` retunes it and writes out/setguess.json (git-ignored; built in a second if missing).
- Fitted default spreads (spreads.FITTED, set by live.py and reach.py): popfit.py's whole spread per species and nature from the replays'
  hits and turn order (default_spreads.json) is the default and the first candidate the in-game reading tries. Held out: 87.9% of each
  Pokemon's evidence fitted against 85.1% for Smogon's (the 1630 and 1760 cutoffs fit worse); damage with both sides fitted, observed /
  predicted median 0.964 -> 0.999, within 10% 60% -> 67%. Its attack stats run low (judged against targets at Smogon's frailer spreads):
  right as a whole, not stat by stat; a joint refit (each side against the other's fitted spread) would fix that. Team cores add +0.6
  points for spreads (popfit.py ctx), not used.
- Two reads on the bot page (the user, 2026-10-13): live turns are read quickly (LIVE_SEEDS 8), and BotRunner.refine reads every saved game
  again (REFINE_SEEDS 128, newest first, one engine thread at the lowest priority, sharing the luck pass's lock) into <tag>_refined.jsonl,
  rebuilds its page and saves it with refined set; build prefers refined values and marks each turn's tier; the page shows "quick read" on
  the rest. Saved pages (bot_<n>_page.json, PAGE_V) make a restart take seconds. Battle sim's budgeted engine (planner_issues 18: EVAL_BUDGET,
  value_se) will replace the seed counts; each budget needs its own CAL, and a 1/5/15/60 s accuracy check on the bot games is promised.
- live.evalbar_mode() switches on the eval bar's own reading: Baton Pass, a Mega ending a traced ability, fitted spreads, and the damage
  check's positions with battlestate.FLAGS (spreads.DMG_FLAGS). live.py, broadcast.py (the streams, which had none of these before
  2026-10-14) and reach.py call it; the bot never does. The calibration set (out/acc_p1.jsonl, CAL 0.676) predated battlestate; the refit on the
  rebuilt positions is under Engine version and the rescale (the Stream watcher found 299 of 403 sampled states differ).
- The -start lines in the replays against what positions.js carries: still left out (approx) are Charge (38 games), Stockpile (28), Focus
  Energy / Dragon Cheer (26), Salt Cure (7), Curse (9), Octolock (6), Smack Down (4), Future Sight (4), No Retreat (3).

## One builder for every reader (battlestate.py, 2026-10-14)
- An outside review (the user had it done; the Stream watcher checked it and passed each thread its part) found the position builders had
  drifted apart. `spots.specs` (the replays' positions: the accuracy set, and Battle sim's value data through `pssim/value_data.py`) lacked
  what `live.spec_mon` passed (Unburden, gained abilities, changed types, Perish and Toxic counts, binding moves, volatile countdowns,
  Protean, Syrup) and every positions.js flag; `live.spec_mon` took the item from the set, so an item received by Trick was lost.
- `battlestate.py` now builds every spec (`mon`, `fresh`, `order`, `acts`, `side`, `spec`): live.specs_for, spots.specs, botpos (the bot's
  positions) and spreads.py's damage check all go through it. `battlestate.FLAGS` is the eval bar's list of positions.js fixes (live and
  replay positions alike); the bot's is `botpos.BOT_FLAGS`, which Battle sim switches on fix by fix. A new fix's flag goes into FLAGS, not
  into one builder.
- `itemDue` (FLAGS; not the bot's yet): replay.py marks a Pokemon whose item an `-item` line showed (`iset`), and `mon` takes the log's item
  over the set's. A replay where a Dragapult received a Choice Scarf by Trick: Focus Sash before, Choice Scarf now. It is read in `mon`,
  not positions.js, which sets items twice (the second time after the field is laid).
- `chargeDue` (FLAGS, 2026-10-16; not the bot's yet): a charged move stopped before it fires (flinch, full paralysis, sleep, Disable, a
  confusion self-hit) loses its charge, as Showdown's twoturnmove does on MoveAborted. replay.py marks it (`cabort`) and `mon` drops
  'charging'. Before, the Pokemon stayed locked into the charge: a bot game's turn 7 (an Archaludon flinched mid Electro Shot) gave evalpos
  "no choices to make", and build.options' KeyError killed that game's page thread, so it never showed. In the bot's logs and the cached
  replays: 22 lost charges, none fired the old charge next turn (13 other moves, 9 charged again); 32 turn starts in 25 games change, none in
  the calibration hold set. build.options / merge now take a "no choices" line as no options.
- Checked against main on 300 held-out replays (2,080 positions), 40 of them through live.specs_for, and the 4 botcmp games: the bot's
  specs and states identical; live's identical apart from the new flag; the replay positions gained the fields and flags (779 Pokemon
  with an item gone since they came in, 107 Perish counts, 72 volatile countdowns, 67 gained abilities, 17 changed types; 299 of 403
  rebuilt states differ). Their actions now go by engine slot as live's do (none of the 2,080 changed).
- Files built from the old replay positions are stale until rebuilt: Battle sim's `pssim/results/value/real_*` (positions, searches,
  features) and the accuracy set the rescale (CAL) was fitted on.

## Louisville day 1 (2026-10-10)

The same study on the Louisville day 1 stream (12 games from 1:15 pm, read live; `study.py out/champions/louisville1.ocr.jsonl 3 14340`,
`reads.py run 3 name=louisville1`): 282 decisions, players took the planner's top pick 50% (19% by chance; Frankfurt 45%), the planner put
44% on what they played (61% if they had followed its mix), mean regret 2.3 points, median 0.1. Protect 14.9% played vs 11.7% planned; Follow
Me 3.5% vs 1.3%. 31 costly plays (`results/broadcast_study_louisville1.json`); 4 did at least as well as the pick against the actual play
(Frankfurt 11 of 39). Each costly turn was also evaluated at horizon 2 (EVAL_HORIZON=2, champ-battle-v23; `h2_cost` in
`results/broadcast_reads_louisville1.json`): 16 of the 26 it could evaluate fall under 5 points there, 8 of them Protects, among them the top
two (a lone Mega Garchomp's Draco Meteor instead of Protect: at horizon 2 the game was already lost whatever it did); 10 stay over 5. Horizon 2
cannot evaluate a position with Decorate (it panics in dex.rs), and some of its values for unplayed options look wrong (Basculegion's Aqua
Jet 48 points under Last Respects in a position Player 1 wins 99%), so it is a cross-check, not the score. Match 3 had no team sheets on
stream: its sets are the common ones.

## The costly plays page (costly.py)

`costly.py <out.html>` builds the page published as the "Day 1 Costly Plays" artifact (template `costly.tpl`: index of plays; per play the
board as known at the turn's start, field, sets, every active's options, what happened, win chance by turn, the read panel). Publish the
same scratchpad file to keep the artifact's URL. The template is .tpl so writing it does not open it in the user's browser pane.

## Louisville (2026-10-10): what changed for a second event

The Louisville Regional stream uses the same overlay as Frankfurt (HP boxes, popups, battle text, decision screen all read), but its team
sheets print "INDEEDEE (FEMALE)" and "HISUIAN ARCANINE": `sheet_species` maps gender and regional names to the species (Indeedee-F,
Arcanine-Hisui, Meowstic-F, Ninetales-Alola), and natures are matched by prefix ("JollyAspeed" when the text runs together). A live watch
keeps every frame's text and catches up from it when restarted. `follow` reads a live stream through its numbered 5-second DASH fragments
(the format yt-dlp lists with --live-from-start): from the live edge or from any point so far (`at=h:mm:ss` into the stream), catching up at
about 3x real time. After many requests YouTube's bot check refused yt-dlp ("Sign in to confirm you're not a bot"); the fragment URL fetched
earlier kept working (it lasts about 6 hours), so `follow` takes a saved one (`src=<json with url and headers>`). Do not pass the user's
browser cookies to yt-dlp without asking them.

## The broadcast reader: state it works out itself (2026-10-10)

Text is not enough on its own, so the reader also keeps track of state:
- Messages are read once, when they leave the screen, in their most common reading (a misread first frame used to lose the message);
  "won't go any higher / lower" sets the stat to +6 / -6; the full-stop messages that matter are read (weather and terrain ending, forfeits).
- Weather and terrain end on their own after 5 turns, 8 with the setter's Damp Rock / Heat Rock / Smooth Rock / Icy Rock / Terrain
  Extender (from its team sheet); the setter (the move just used, else the Pokemon on the field with the ability, latest sent out first) is
  named in the log line so the parser agrees.
- What happens as the leads come in (Intimidate, weather, terrain) is held and applied before turn 1, also for the second and third games
  of a set, when the reader is still between games.
A further step would be to replay each turn with the engine (its turntest loads the state before a turn and plays both sides' choices)
and keep the outcome that matches the HP boxes: abilities like Stamina, item use and durations would then come from the simulation.

## Watching a game again (2026-10-10)

With the video embedded, the page has "Watch this game" (the video goes 20 s before its first turn), "Watch from turn N" and "Stop
following the video": while following, the page shows only what the video has reached (upToPlayer), as with a recording, so a finished
game plays out live again; this works on the live stream (its DVR) and on the recording once it ends. The step times (vt) are the stream
time: `follow` keeps the stream time of its first frame in out/live/live_<id>_t0.txt so a restart, which catches up on the kept frames,
gives them the same times.

## The eval number (2026-10-10)

The user asked for a chess-style number beside the win chance. It is the win chance's log-odds divided by what one Pokemon of advantage is
worth: in the 2,789 cached Showdown games, the side one Pokemon up (of the four brought) won 75%, two up 92% (`unit.py`, a symmetric
logistic fit, 1.115 log-odds per Pokemon; `results/eval_unit.json`). So +1.0 is as far ahead as being a Pokemon up, and equal steps are
equal changes in the odds (40% to 20% is -0.9, 40% to 60% is +0.7). The page shows it centred between the two win chances, above the turn counter, from Player 1's
side (+ ahead, - behind, colored for the leader), and the graph switches between win chance and eval (-4 to +4).

## How often the rules and the battle text are right (2026-10-10)

The 18 Louisville flags (games with sheets), checked against the stream re-read at 6 frames a second and the field label at the top of
the screen ("Psychic Terrain", "Sandstorm"): the rules were right 15 times, the text 3 (`results/louisville_flag_check.json`). The reader's
misses: a lead's ability message still on screen at the first decision screen was dropped when the reader switched games (the message
buffer is now kept across games), "rose sharply" / "harshly fell" were read as one stage (the pattern now tries the longer wording first),
and three messages fell between the 2-a-second frames. The rules' misses: Psychic Terrain blocking a Prankster Parting Shot (the reader logs
"is protected by the Psychic Terrain" as -activate) and terrain seeds (Psychic Seed +1 Sp. Def), both now rules. After the fixes: 3 flags
left on Louisville (all frame misses), 20 on Frankfurt (was 45). The last 9 of those went with a fix to the decision screen: its HP bar
slides in, so the first frame can show a name over the next slot (a Basculegion read into Charizard's slot with Charizard's 35%, which
benched Charizard on the board). Its boxes now count once two frames in a row agree (or after four frames); that also drops the empty
turns a one-frame flicker of "Trainers are choosing actions" used to add. The study (study.py), the costly plays page (costly.py) and the read
analysis (reads.py) take the event's name now (name=louisville1; study.py <ocr> [threads] [t0] with the stream time of the first frame).

## Sheet names in brackets; a sheet entry the reader missed (2026-10-10)

Sheets print forms in brackets: "FLOETTE (ETERNAL FLOWER)" (the first word gives Floette-Eternal), "ROTOM (HEAT)", besides "(FEMALE)" /
"(MALE)". A Pokemon on the field that the sheet as read lacks (a misread panel) is added to the sheet with its most common set, and the
"footage from elsewhere" rule (Pokemon on neither sheet) never counts a Pokemon on the field: a missed Floette used to close each game of
a match after its first turn. The page's header is compact: games are labelled M<match> G<game> with the players on hover, a finished
game says "N turns" (not "so far"), the sheets chip says whether the sheets were on stream, and the reader's status shows only for a game
still being played.

## A match the broadcast shows no team sheets for (2026-10-10)

The Louisville stream skipped the sheets for one feature match, and the reader used to wait for them ("waiting for both team sheets").
Now such a game starts anyway (meta 'closed'): its preview is the Pokemon this match has shown so far plus the leads, a Pokemon nobody has
seen yet is added when it comes in, and the live mode treats it like a Bo1 closed-sheet game (each species' most common set, what the game
shows laid on top; items hidden). The battle-text vs rules checks are off for it: the rules need the sheets' abilities and items. A form
the text does not name (Basculegion-F) falls back to the base species.

## Missed faints and who won (2026-10-10)

A faint whose message was not read left a fainted Pokemon "in the back" (Louisville: Player 2's Sneasler, 21%, knocked out by Muddy Water,
replaced at the end of the turn by Rotom). The reader now infers it: a Pokemon sent in after the turn's moves, into a slot whose Pokemon
did not go back, replaces a fainted one, unless it is the replacement of a switching move (Baton Pass, U-turn, Volt Switch, ... in PIVOT)
that has not had one yet. The game's result comes from "<name> lost!" / "<name> won!": the name Player 2's own messages use ("The Trainer"
on the Louisville stream, the player's name at Frankfurt) means Player 2, any other name Player 1. "The battle has ended due to a forfeit."
waits for that message (a game that closes without it goes to the side with more Pokemon left). A game also ends when one side's
fourth Pokemon faints. After a game the broadcast replays highlights (earlier faints and moves again); the reader ignores them because the
game has ended, and a faint for a Pokemon already down is ignored.

## Options across hypotheses; names on the live page (2026-10-10)

Options are merged over the hypotheses about unseen back Pokemon (build.py merge). An option's win chance is now the side's overall win
chance plus what the option gains or loses against the best play within each hypothesis where it exists; before, a switch to a Pokemon
that exists only in some hypotheses averaged only over those, so it carried how good those hypotheses were (the user saw "Switch to
Pelipper" at 80% next to the best move at 67%, really equal). Such options carry cond (the share of hypotheses where they exist), shown as
"if X was brought · 48%". Small mismatches between picks and wins remain where the planner's design shows: each side's mix is solved
against the other side staying in, while wins are scored against the other side's whole mix.
The user asked (2026-10-10) for the players' real names on the live broadcast page: the reader takes them from the scoreboard
(scoreboard_names, without country and record), keeps them in memory per game (meta['who']) and serves them in data.json only; logs,
results and everything tracked still say Player 1 and Player 2.

## Battle text vs rules: the reconciler (rules.py, 2026-10-10)

The user asked for two versions of the state with a flag where they disagree. `rules.py` keeps the log's facts (switches, moves and
targets, Protect, misses, immunities, super-effective and critical hits, hit counts, faints, HP; the reader now logs -supereffective,
-crit, -miss, -immune, -hitcount and -fail) and replaces its stat and field messages with what the rules say: entry abilities (Intimidate
and the abilities that block or answer it, weather and terrain setters, Mega abilities, which stay after switching out), on-hit abilities
(Stamina, Weakness Policy, Justified, ...), each move's stat changes from the engine data (plus Parting Shot and Electro Shot's charge),
White Herb, Speed Boost, and weather / terrain / Trick Room / Tailwind / screens with their durations. `compare(log)` lists, per turn,
the stat stages of the Pokemon on the field and the field conditions where the two differ, each shown where its gap first appears.
On Frankfurt day 1: 45 flags in 19 games, most of them real misses by the reader (lead Intimidates, Snarl drops on a second target, Nasty
Plot read as +1); Louisville: 5 in two games. The live page lists the turns with open checks and shows each with Text is right / Rules are
right; a verdict is saved beside the game's log (out/live/<tag>_g<n>_fixes.json), a "rules" verdict is put into the log as a -fix line
(replay.py sets the stat or field as given) and that turn and the later ones are evaluated again; pressing a chosen button again takes the
verdict back. `?novideo` on the page leaves out the YouTube player.

## Hands-free: auto.py (the user asked, 2026-10-10)

The Play Pokémon channel names its streams consistently ("VGC Day 2 | 2027 Pokémon Louisville Regional Championships"; side streams are
"VGC Feature Station ..."). `auto.py` reads the channel's streams page every 5 minutes (the public feed was returning errors) and runs one
program: `broadcast.py follow` while a main VGC stream is live (from the stream's start when there is no record of it yet, again after 5
minutes without a new fragment since the fragment URL lasts about 6 hours, the Mac kept awake on mains power), else `broadcast.py serve`
for the newest VGC stream (a record shown without fetching; `scan` of the recording first when it was never read). It pauses its program's
process group while other programs keep 8 or more cores busy and carries on below 6 (the user chose start-on-its-own, 2 workers).
The user's LaunchAgent (`auto.py install`, label local.evalbar.auto) runs it from the main checkout, so the records it keeps are in the main
checkout's evalbar/out/live; it owns port 8768. One game's evaluation at a time now (`live.WORK`): a page rebuilt from a record used to
start an engine for every game at once. yt-dlp answered again on 2026-10-10 (no bot check); the watch page alone no longer has the
stream's manifest.

## The public page on the user's site (2026-10-10)

The user chose live via Netlify (estimate: about 6 credits per streamed weekend plus about 2 per viewer-weekend; a spike of 1,000
viewers for an hour is about 90, and running out on Netlify's Free plan pauses the whole site). The site side (a Netlify function with
Blobs at the site's /api/evalbar, the /evalbar/ page, the account) belongs to the personal-website thread. This side has:
`publish.py`, which uploads head.json plus one file per game (the reconciler's checks left out) every 10 seconds from auto.py, once
~/.config/evalbar/site.json exists; and page.html's public mode (`publish.py page <out.html>`), which polls head.json every 10 seconds
while the tab is visible, fetches a game's file when its version changes, starts the video paused, says it is unofficial, and stops after
30 minutes without activity. Scoreboard names stay on the public bar and game list (the user's choice); analysis pages stay anonymous.
`publish.py sample <dir>` writes the files with Player 1 / Player 2 for the site's tests.

## The broadcast reader: targets

Mid-turn the broadcast pops up the HP box of the Pokemon being hit, alone, in that Pokemon's slot. The reader (broadcast.py `aim`/`hit`/
`watch_hp`) takes a single-target move's target from the box that drops after "X used Y!", or from text naming it (protected itself,
avoided, It doesn't affect, a faint, and for a status move the first thing said about another Pokemon), or the only possible target.
Day 1: 232 of 262 single-target moves (89%), 163 of them from the popup box. The popups also place send-outs whose slot the text did not
give; "<trainer> withdrew X!" frees X's slot; a game closes when Pokemon on neither sheet start acting (the broadcast cut to other footage).
Each target's evidence and VOD time is kept in meta['aims'] for spot checks. The popup-to-slot mapping was checked against the video by the user
(M4 G1 turn 1: Night Slash on the right-side Tyranitar, Wood Hammer on the left-side Milotic, both as read).

## Engine version and the rescale (CAL)

- The bar (live.py, broadcast.py) reads with `live.ENGINE` = v34 (2026-10-16; Battle sim: v31 plus the immune-target filter judging a
  move by its type as used and a Mega copy by the Mega's ability, 1.25x faster) and the acc value net, set by `live.EVAL_ENV`. Reads go to
  files named for the engine (`<tag>_eval_v34.jsonl`, `_refined_v34`, `_luck_v34`). `live.EARLIER` lists earlier engines' files (v25's
  unsuffixed, v31's): they stay on the pages, each rescaled with its own `CALS` weight, and a turn or luck pass one of them read is not read
  again, so a switch costs no engine time on saved games. `PAGE_V` 2 rebuilt every saved bot page once with the new weights.
- `CALS` (accuracy.py compare, 32 seeds staged, folds by match): v25 0.754 (Oct 5 calibration build); v31 0.782 and v34 0.785 on Battle
  sim's rebuild of the 891 hold games through today's spots.specs (pssim/results/value2/real_hold.pos.jsonl, 6,381 positions: the 560
  calibration games plus the other games of their matches). Runs: out/acc_hold_v31.jsonl, out/acc_hold_v34.jsonl.
  - The rebuilt positions predict real results better: on the 3,968 calibration positions v31 scores 0.5003 against 0.5172 on the Oct 5
    build (-0.0169 +- 0.0049). The engine change adds little: v34 minus v31 -0.0004 +- 0.0003 on all 6,381.
  - At 0.785 the calibration bands match: rated 96.6% -> won 96.6% at 90%+, 85.0 -> 86.4 at 80-90, 75.0 -> 72.4 at 70-80.
- `live.CAL` (0.676) is the bot's, not the bar's: bot/brain.py, position.py, contempt.py and contempt_bot.py read it, so changing it
  changes the live bot's play. The bar uses `BAR_CAL` = CALS[ENGINE]. Moving the bot to the new weight is Battle sim's call, behind its flag.
- If the bot moves to depth search (planner_issues 18, a 12-hour confirmation from 2026-10-16), score real_hold.pos.jsonl with that search
  too and give its weight to Battle sim.
- Depth at 4x (the Bo1 bot's search from 2026-10-16: EVAL_BUDGET 80000, EVAL_DEPTH 2, EVAL_DEEP_K0 2, 32 seeds, not staged) on the same
  6,381 positions (out/acc_hold_d4.jsonl): log loss 0.4787 against the one-turn v34's 0.4889 (-0.0101 +- 0.0016; on the 3,968 calibration
  positions -0.0113 +- 0.0021), weight 0.765 (0.744 on the 560 games). Its output has the same sides / slots / options as evalpos, no
  payoff matrix (the luck pass keeps the one-turn EVAL_MATRIX). One core: 5.4 s a position, against 1.7 s for one turn at 32 rolls staged
  and 4.5 s at 128 (the streams' background read). Not used by the bar yet.
- reads.py and uncertain.py stay on v18 so their committed results reproduce.

## Process names (the user asked, 2026-10-06)

Every process this thread starts must show as `evalbar-<program>` in `top` and in Stats (which the user watches; it lists `ps -Aceo comm`), so
they know whom to ask to stop it. `procs.py` makes the links in `out/bin` (`exe('ffmpeg')` etc.: the engine is `evalbar-champ`, node
`evalbar-node`, OCR `evalbar-ocr`), and every subprocess call goes through them. Each script's main starts with `P.own()`, which re-starts it
under `evalbar-py` (plain `python3` would show as "Python"), carrying a venv's packages along, so `python3 evalbar/<script>.py` is enough,
for the user's own runs too. The other threads use battlesim-, trsheet- and teamsearch- (shared memory process-names.md).

## Rules that apply (also in memory)

- No names in the repo: write "the user" or "the player"; never a real name, the Mac username, absolute `/Users/` paths, an email, or
  other people's names (replay usernames, opponents, tournament players). Replay logs and anything derived from them that keeps usernames
  stay git-ignored. Commit only your own area with explicit paths.
- Push continuously without asking (the user, 2026-10-07, confirmed in this thread): after each commit, rebase this worktree's branch onto
  `main` (only `evalbar/` changes here, so it is clean), fast-forward `main` in the main checkout (`git -C <main checkout> merge --ff-only
  <branch>`, which touches only `evalbar/`), and `git push origin main`. Never bypass the privacy hooks.
- CPU: never more than 10 busy cores on the Mac across all threads; at most 3 workers while the user may be playing (ask first);
  coordinate core splits with the other threads by message before any multi-core run.
- Times in 12-hour am/pm. Keep what you build lean; add features when asked.
