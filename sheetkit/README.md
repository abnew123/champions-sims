# Sheet kit

One ladder sheet per team, each built the same way: pick the four to bring against every archetype from whole-game sims, work out the
turn-one lines for those picks, and build the page. The kit is the shared code and page template; each team has its own folder and
its own Claude thread.

| Where | What | Who changes it |
|---|---|---|
| `sheetkit/` | The steps (`kit.py`), the page template, the archetype list, the sim setups, this file | The kit maintainer (the "TR sheet" thread) |
| `sheets/<team>/` | One team: its six, config, page text, picks, turn-one lines, built page, and `work/` (jobs, results, logs; not in git) | That team's thread |
| `pssim/`, `native/`, `mxtr/`, `teamsearch/mx/` | The simulators the steps call | Their owning threads (see the root `HANDOFF.md`) |

A team thread never edits `sheetkit/`. If a step does not fit your team, message the kit maintainer (SendMessage "TR sheet") with what
you need; a fix there reaches every sheet. Run `python3 sheetkit/selftest_tr.py` after any kit change: it rebuilds the published Trick
Room Six sheet from the raw results and fails if anything on it would change.

## The steps

Run from the repo root. `<team>` is the folder name under `sheets/`.

```bash
python3 sheetkit/kit.py <team> status
```

| Step | Command | What it does | Cost |
|---|---|---|---|
| 0 | `init` | Creates `sheets/<team>/` from `sheetkit/starter/` | none |
| 1 | `grid [--workers N]` | One-on-one cells for the six against 46 threats, Trick Room up and not: the planner's `GRID_DIR` | about 1 CPU-minute |
| 2 | `smoke` | Dry run of everything on one core: 2 whole games, 1 turn-one job, a draft page at `work/smoke/preview.html` | about 15 seconds |
| 3 | `matrix jobs`, `matrix run`, `matrix report` | All 90 fours (lead + back) against each archetype's 6 opposing leads, 16 games each, the same games for every four | 86,400 games, about 110-130 core-hours: a cloud box |
| 4 | `confirm jobs`, `confirm run`, `confirm decide --write` | Each archetype's top 5 fours plus the current pick on 48 fresh games per opposing lead; writes `picks.json` | about 17,000 games, 22-26 core-hours |
| 5 | `t1 jobs`, `t1 run`, `t1 solve` | Turn-one lines for each pick with its real back row (12 samples per cell, opposing Indeedee-F item variants); writes `t1.json` | about 25 minutes on 3 workers |
| 6 | `charts [--workers N]`, `speed` | Coverage and Matchups from the grid (`charts.json`); the Speed table from ladder spread stats (`speed.json`) | seconds |
| 7 | `guide run`, `guide report` | Game plans: each pick vs its six opposing leads, 64 games each with per-turn logs (3,840 games: a few minutes on a box, about half an hour on 3 Mac workers); plus team-preview tells from the matrix; writes `guide.json` | minutes |
| 8 | `page [--compare other.html]` | Builds `sheet.html` from the template, `picks.json`, `t1.json`, `guide.json`, the charts and the team's text | seconds |

Every run resumes where it stopped (finished jobs are skipped), writes its log to `pssim/kit_<team>_<step>.log`, and shows under
"Sheets" on the one progress page all threads share (`status_server.py`, `sim-progress` in `.claude/launch.json`, port 8766), also
when it runs on a cloud box and the results are only pulled back. Start long runs in the background (`nohup ... &`).

**How a pick is decided.** Seeds depend on the opponent and the game index only, so every four plays the same games and all comparisons
are paired. Picking the best of 90 on the same games flatters the winner, so the matrix only nominates; `confirm decide` keeps the
current pick unless the fresh-game leader beats it by at least 1.5 paired standard errors. With no current pick, the fresh-game leader
is taken. Use fresh game indices for every confirmation (the defaults are 600 for the matrix and 1000 for the confirmation; pass
`--g0` for a later round and note it in your handoff).

## The matrix and the confirmation on a cloud box

The box is set up once the way `teamsearch/cloud/README.md` describes (steps 0-3: the user launches it; the bundle gives it
`~/champions-sims` with Showdown's engine and the battle binary built for the current setup's source tarball). Then, from the Mac:

1. `python3 sheetkit/kit.py <team> grid` and `matrix jobs` here, so the grid and the job list exist.
2. `sheetkit/cloud/push.sh <host> <key file> <team>` copies the kit and the team folder (and any shared simulator file the box lacks).
3. On the box, in `~/champions-sims`: `python3 sheetkit/kit.py <team> smoke`, then start the run detached, for example
   `(setsid nohup python3 sheetkit/kit.py <team> matrix run --threads 180 > matrix.out 2>&1 < /dev/null &)` (the parentheses let the
   ssh command return at once). `--threads` is how many cores you
   take; on Linux the kit spreads them over battle processes of 3 threads each (one process with many threads runs about ten times
   slower there), dealing the jobs round-robin so the processes finish together. If the box is shared, agree the split first, and
   do not start your run inside a tmux server another thread uses: a tmux server's process title is the command line of the session
   that created it, so a `pkill -f` aimed at one run can match the server and kill every session in it (it happened both ways on
   2026-10-05). Use `setsid nohup` as above, or your own server (`tmux -L <name>`), and stop a run only with patterns that contain
   your own paths (`sheets/<team>`), fed to the box as a script (`ssh host 'bash -s' < stop.sh`), never typed inline.
4. `sheetkit/cloud/pull.sh <host> <key file> <team>` copies results back (repeat every ten minutes or so: a spot box can be taken
   away without notice, and only what was pulled survives); `status` and the progress page show how far it is. To resume on a new
   box, push again: results already on the Mac are sent along and skipped by the run.
5. `matrix report`, `confirm jobs`, push again, `confirm run` on the box, pull, `confirm decide --write`.

A result folder holds one run: the kit refuses to add games to a folder whose results came from other sets, another sim setup or
other game indices (`<folder>.run.json` records them). Move the old folder aside instead.

## Opponents: archetypes or cards

`sheet.json` "opponents" picks what a sheet is built against:

- `archetypes` (the default; the Trick Room Six through Version 21): ten archetype models mined from replays, one tab each.
- `cards` (since 2026-10-06): real teams from Battle sim's pool (`pssim/opp_pool.py`, Showdown Bo3 sides with open team sheets),
  grouped by its ordered core rules (`pssim/results/core_rules_both_100.json`). Each rule is a card under the tab of its nearest
  archetype, and teams that match no rule get an "other" card per archetype: 32 cards in all. `python3 sheetkit/opponents.py` builds
  `sheetkit/opponents/` (the cards, the guide, and one opponent model per card in the shape `pssim/t1sim.js` reads; every step passes it
  on as `OPP_MODEL`). The page's guide becomes the ordered rule list, each rule jumping to its card. The both-sides-pick step plays
  each card's most common real sixes, and `optimal adopt` makes its best candidate the card's pick, with the number "when they bring
  their best four" (the user's choice for the sheet's percentages). A four can only become the pick once its own strongest answers
  have been searched: the screen looks for answers to the current pick only, so a candidate that beats the pick there has only met
  answers found against another four. `optimal run --only more` (`sheetkit/cloud/more.sh` on a box, which also redoes adopt, turn one and
  game plans) screens, for each card whose best four so far has not been searched, that four, and plays every candidate against its
  answers; repeat until it says there is nothing to do. A result is only reused while its job still holds the same fours (a changed pick
  moves the old results to `<folder>.stale/`).

A result folder records which opponents it was played against, and the kit refuses to mix them.

On a fresh box of its own: `sheetkit/cloud/bundle.sh <team>` on the Mac, copy `sheetkit/cloud/bundle.tar.gz` there, unpack it into
`~/champions-sims` and run `sheetkit/cloud/setup_box.sh` (about 10 minutes). On a box another thread already set up: `sheetkit/cloud/push.sh <host> <key> <team>` (also the sheet thread's own simulator files and the current battle
source), then on the box `sheetkit/cloud/build.sh` (the binary, if missing) and
`(setsid nohup sheetkit/cloud/all.sh <team> <threads> > /dev/null 2>&1 < /dev/null &)`: matrix, confirmation, both-sides-pick, adopt,
turn-one lines and game plans in order (log `work/all.log`), then `more.sh` the same way for the second both-sides-pick round
(log `work/more.log`). Pull with `pull.sh`, then `page` on the Mac.

## Rules for every sheet thread

- **Cores.** Never more than 10 busy cores on the Mac across all threads, at most 3 workers while the user may be on it. Ask the user
  before any multi-core run and agree the split with the other threads by message. `kit.py` defaults to 3 workers on the Mac and
  refuses more than 10. The matrix and the confirmation belong on a cloud box (`teamsearch/cloud/README.md`; the user starts the box).
- **Sim setup.** `sheetkit/sim.json` names the full-battle setups (binary, value file, flags). Run `current` unless you are told
  otherwise, and never compare numbers across setups. Only the kit maintainer moves `current`, when the Battle sim thread says a setup
  is final. Tell Battle sim if results look wrong. A setup with the same `games` as another plays the same games and shares its result
  folders; `SHEET_SETUP=<name>` in front of any kit command or cloud script (`push.sh`, `build.sh`, `all.sh`, `more.sh`) runs that
  setup instead of `current`, and a sheet can pin one in its sheet.json (`"setup": "<name>"`), which the kit and the cloud scripts
  follow (`sheetkit/cloud/setup_of.py`; on a shared box `build.sh <team>`).
- **Flagged games.** A game that hits a mechanic the simulator has not ported is flagged `unsupported` in its result.
  `kit.py <team> flagged` counts the results with one per folder; `--write` moves them to `<folder>.flagged/`. Then run the steps again
  on a setup that ports them and shares the folders (for v20's results: `SHEET_SETUP=v23-dp2-race-eg9-full`, `all.sh` then `more.sh`
  until it has nothing to do; `sheetkit/cloud/replay.sh <team> <threads> [moves]` does all of that in one go). Only the moved jobs are
  played, and the picks follow. On a shared box only one thread runs `build.sh`.
- **Competent opponents.** The sims assume them; do not tune a sheet around ladder misplays.
- **Lean page.** Add a section or a paragraph only when the user asks for it.
- **No names.** Nothing in a tracked file names the user, an opponent or a player, and no absolute paths. Write "the user".
- **Git.** `work/` is ignored. Commit with explicit paths (`git add sheets/<team>`), one commit per published version; do not push
  unless the user asks.

## A new team

1. `python3 sheetkit/kit.py <team> init`, then write `sheets/<team>/team.json`: the six in the sims' MYTEAM format, keyed by species
   name, in the order you want the six listed.
   ```json
   {"Kingambit": {"species": "Kingambit", "item": "Chople Berry", "ability": "Defiant", "nature": "Brave",
                  "evs": [32, 32, 0, 0, 2, 0], "moves": ["Iron Head", "Kowtow Cleave", "Low Kick", "Sucker Punch"]}}
   ```
   `evs` are Champions stat points in the order HP, Atk, Def, SpA, SpD, Spe. A Mega is its base species holding the stone, with the
   base forme's ability. Two stones in one six are fine: a lead holding both offers one or the other Mega Evolving on turn one (the
   line says which), and the game plan says how often each one does.
2. Edit `sheet.json` (options below) and `text.json` (the page's prose; the starter has the parts that are true of every sheet).
3. `grid`, then `smoke`. If either fails, the set uses something a simulator does not know (see the two lists below): fix that before
   spending compute. Then ask Battle sim for a focused case batch with your six (`FOCUS_POOL=<its sets> FOCUS=<its species>` with
   `native/gen_turn_cases.js`, checked against Showdown): a mechanic nobody ported and no test set carries is otherwise invisible
   (Healing Wish did nothing until v22).
4. `charts` and `speed` (cheap, and they tell you early what the six cannot hit), then `matrix`, `confirm`, `t1`. Write `notes.json` (one short mechanics note per archetype card, keyed by the archetype's model
   name: why a line looks odd, what blocks what) and `cards.json` (per Pokémon: `role`, `note`, `src`).
5. `page`, look at `work/preview.html` in the browser at phone and desktop width, and publish `sheet.html` as an Artifact only when the user asks. Record the
   Artifact link and version in `sheet.json`.

### `sheet.json`

| Key | Meaning |
|---|---|
| `name`, `artifact`, `published` | The sheet's name, its Artifact link, and the last published version |
| `lead_order` | How a lead pair is written and simulated on turn one (first name first). Default: `team.json` order |
| `my_names`, `short_names` | Display names for your Pokémon (`{"Indeedee-F": "Indeedee"}`) and the narrow-screen column names of the Matchups grid |
| `grid_dir` | The planner's one-on-one grid, relative to the team folder. Default `work/grid` (what `grid` writes) |
| `t1.reader_w` | Weight on the "player who reads your mix" number when solving turn one. 0.75 |
| `t1.tr_credit` | `fitted`: Trick Room up after turn one counts for whoever set it (the replay fit). `slower-four`: it counts for whichever side brought the slower four, the right model for a team built around Trick Room |
| `t1.tw_under_tr` | `zero`: a Tailwind set in the same turn as Trick Room scores nothing (Trick Room teams) |
| `t1.trmult_file` | Per-archetype multipliers on the Trick Room credit (Trick Room Six only, from its 2v2 study) |
| `t1.stat_move` | A move whose turn-one click rate is shown on each card ("Sets Trick Room 100%"). Leave out for none |
| `t1.mega_choice` | `true`: a stone holder's turn-one options include each move without Mega Evolving (lines that Mega Evolve say so). Set it with the v24 setup, whose battles make the same choice |
| `t1.exclude_moves` | Turn-one actions never to click, as `": <text>"` fragments of the action label |
| `lines.short_moves`, `lines.rewrites` | How turn-one lines are written: shorter move names, and one move shown in place of another against one target |
| `threats` | The rows of Coverage and Matchups: names from the grid's 46 threats. Default: the 29 with usage numbers (`team-sheet.html.usage.json`) |
| `matchups_default` | `tr` or `notr`: which Matchups grid shows first |
| `speed.order`, `speed.top`, `speed.tiers`, `speed.range` | The Speed table: `fastest-first` or `slowest-first`; how many of the most-used Pokémon to list (30); how many Speeds per Pokémon (2); `[low, high]` outside which everything folds into one row |
| `theme` | The page's ten colour tokens, light and dark |
| `proc_prefix` | The name every process of this sheet's runs starts with in `top` (`trsheet` gives trsheet-py, trsheet-node, trsheet-champ-battle-v16); default the folder name. Each thread uses its own, so the user can see whose a process is |

### What the page is built from

`sheetkit/template.html` holds the markup, styles and scripts. `{{NAME}}` slots are filled from the team folder; lines between
`@@if <section>` and `@@end` are kept only when the team has that section's data.

| File | Fills |
|---|---|
| `picks.json` | Each tab's four and its whole-game win % |
| `t1.json` | Each card's turn-one lines and its two turn-one numbers |
| `notes.json` | The note under each card |
| `team.json` + `cards.json` | The team cards (formes, types and stats are computed) |
| `text.json` | `title`, `sub`, `leads_intro` (paragraphs), `leads_method`, `team_h2`, `team_intro`, `footer` (paragraphs); with the optional sections also `cov_intro`, `mx_intro`, `mx_foot`, `speed_h2`, `speed_intro`, `speed_foot` |
| `charts.json` | Optional: Coverage (`coverage`) and Matchups (`attackers`, `matchups`), written by `charts` |
| `speed.json` | Optional: the Speed table (`rows`: `[speed, yours, theirs, tie note]`), written by `speed`. Mark a hand-written one `"hand": true` and `speed` leaves it alone |

`charts` words each Matchups cell the way the first sheet's grid did: verdict, damage each way, who moves first, whether the win needs
the item intact, and the move line where best play is not the obvious one. A Pokémon with no attacking move gets no column. `speed`
labels each opposing Speed by nature and Speed points from Smogon's September 2026 Reg M-C spread stats; it is a starting point, so trim
it with the `speed` options until it shows what matters for your six. The starter `text.json` has prose for all three sections that is
true of any team; add what is specific to yours (your own weather or terrain, a spout move, an item).

`page` also writes `work/preview.html`, the same page with the charset and viewport lines a published Artifact gets. Open that one to
check phone width: the progress page's server also serves `sheets/`, so it is at
`http://localhost:8766/sheets/<team>/work/preview.html` (`sim-progress` in `.claude/launch.json`).

The "Which tab" guide and the tab list come from `sheetkit/archetypes.json` and are the same on every sheet. `page` reports (and exits
with an error for) a card whose turn-one line switches to a Pokémon outside its back row, or whose line weights do not sum to 100.

## What the simulators do not model

**Full battles** (`native/champ`): Revival Blessing, Healing Wish, Baton Pass, Ally Switch, Beat Up, Magician and Wandering Spirit are
not ported; a game that reaches one is flagged in its result row (`unsupported`) and still counted, so check the flag rate after a
run (none of the Trick Room Six's 15,552 confirmation games were flagged). Ask Battle sim about anything else unusual on your team.

**The one-on-one grid** (`teamsearch/mx`, used read-only; ask Team search before relying on a new mechanic):

- Damage only. Status moves are ignored except Fake Out; accuracy, crits and secondary effects under 100% are ignored. "Trick Room up"
  means up for the whole one-on-one.
- Weather and terrain come only from the Pokémon's own ability or the threat's; a partner's is never assumed. That affects Grassy and
  Psychic Seed holders, Chlorophyll / Swift Swim / Sand Rush users, and Weather Ball or Solar Beam on a Pokémon that does not set the weather.
- Abilities outside its list of about 30 (plus weather and terrain setters and the -ate abilities) are ignored, for example Sheer
  Force, Technician, Guts, Supreme Overlord and Sand Force.
- Items it knows: Choice Band / Specs / Scarf, Assault Vest, Life Orb, Expert Belt, Focus Sash, Rocky Helmet, White Herb, Sitrus Berry,
  Leftovers, Grassy and Psychic Seed, type-boosting items and resist berries. Others are ignored (Lum Berry, Mental Herb, Clear Amulet,
  Covert Cloak, Weakness Policy, Throat Spray, Booster Energy).
- Approximations: 2-5-hit moves count as 3 hits (5 with Skill Link), Population Bomb as 7, Triple Axel as 3 full hits, Last Respects as
  100 power; Solar Beam, Electro Shot and Meteor Beam charge outside their weather.
- "Roll" percentages are a 200-game estimate rounded to the nearest 5, so a cell near a boundary can read 5 points either way.
- A set whose species, item or a move is missing from `native/champions_data.json` cannot be built; `grid` stops and says which.
- The threats are a fixed list of 46. The planner treats a matchup with no cell as neutral.

## Not in the kit yet

- **Effective Speed.** The Speed table lists raw Speed only: no Tailwind, Choice Scarf, Unburden or weather-speed rows.
- **Species tells and per-archetype guides** exist as a report (`matrix report`), not as page content.

## The Trick Room Six folder

`sheets/trick-room-six/` was imported from the published Version 16 page and the results that built it; Version 17 was the first
page published from it. Its `work/` links to the old
result folders in `pssim/results/` (`python3 sheetkit/selftest_tr.py --link` recreates the links), and `grid_dir` points at the
hand-built grid the published picks were run with. The kit's own `grid` step reproduces that grid in 456 of its 460 cells; the four
that differ are Incineroar cells where the generic code models White Herb. Since Version 17 its `charts.json` comes from the `charts`
step; its `speed.json` is hand-written.

The self-test checks, against the files the old pipeline left behind: the 5,400 matrix jobs, the confirmation jobs, the ten picks
with their win shares, the 60 turn-one jobs, their Speeds, all 60 solved turn-one plans, the page (data by value; markup, styles
and scripts byte for byte), and Coverage and Matchups (Coverage identical; Matchups identical in 340 of 350 cells, the other ten being
Incineroar's White Herb cells). Its inputs are frozen in `sheetkit/fixtures/tr-v16/`. One difference is by design: two opposing leads with exactly the same share are now listed in the
opponent model's order, which swaps two rows on three tabs.
