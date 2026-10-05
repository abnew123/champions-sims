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
- `build.py <id> acc=... engine=<evalpos output> pos=<positions>` fills the page's options panel. The published page (version 2) shows the
  demo game with the version 0 bar and the engine's options at 32 seeds.

Running / next: the accuracy sample (`out/acc_p1.jsonl`, 3,968 positions from 560 of the first 600 sample games, 8 seeds, output
`out/acc_eval.jsonl`, resumable with `engine.py run`). Then `accuracy.py out/acc_eval.jsonl` compares the engine value, static value,
refitted features and version 0 plus engine against version 0 on the same positions; the bar switches to the engine only if it wins, with
its values rescaled to real outcomes. Cores: TR sheet and Battle sim agreed to 3 threads for this run; ask the user before going above one.

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

## Rules that apply (also in memory)

- No names in the repo: write "the user" or "the player"; never a real name, the Mac username, absolute `/Users/` paths, an email, or
  other people's names (replay usernames, opponents, tournament players). Replay logs and anything derived from them that keeps usernames
  stay git-ignored. Commit only your own area with explicit paths; push only when the user asks.
- CPU: never more than 10 busy cores on the Mac across all threads; at most 3 workers while the user may be playing (ask first);
  coordinate core splits with the other threads by message before any multi-core run.
- Times in 12-hour am/pm. Keep what you build lean; add features when asked.
