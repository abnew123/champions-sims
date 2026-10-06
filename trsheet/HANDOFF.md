# TR sheet thread: handoff (2026-10-05)

On 2026-10-05 the user split the work in this repo into three Claude threads. This file is the starting point for the **TR sheet** thread.
The main `HANDOFF.md` at the repo root has the full history and every recipe; read its sections "Sheet Version 12" onward after this file.

| Thread (session name) | Owns | Does not touch |
|---|---|---|
| **TR sheet** (you) | The published sheet and everything that decides what is on it: `trsheet/`, `tr_leads.py`, `tr_rules.py`, the turn-one lead pipeline in `pssim/` (`t1sim.js`, `tr_final.py`, `run_jobs.sh`), the sheet's bring picks (`bringmx_*`, `bringcf_*`, `build_sheet_v*.py`), spreads, `recordings/` and game reviews, the 1v1 grid for the sheet (`mxtr/`) | `native/champ/src`, `egvalue*.json`, `teamsearch/` |
| **Battle sim** | The full-battle simulator and planner: `native/champ/` (Rust engine, `champ-battle-vN` binaries), the position value (`pssim/egvalue*.json`, `build_egvalue*.py`), replay analysis (`pssim/replays_protect/`, `protect_*.py`, `replay_feats.py`, `fit_real_value.py`, `elo_check.py`), planner tests (`dp_test*`, `ev*_test*`, `dplog*`, `dpfeats*`) | The sheet page |
| **Team search** | `teamsearch/` (hill climb for the strongest six; a thought exercise, exempt from the no-miss rule) | Everything else |

Talk to the other threads directly with SendMessage (names above); do not relay through the user. You use the battle sim as a tool: ask
**Battle sim** which binary, value file and flags are current before any large run, and tell it if results look wrong.

## The sheet now

- Published: https://claude.ai/artifact/Qufendyuq8b42JmB56XSc6, **Version 21** (2026-10-05): each lead card has a short game plan and the Leads section an "Adjust the four at team preview" list (the user asked for a strategy guide: overall game plans, not just turn one, and "if you see X, bring Y"). Built by the kit's new `guide` step (`sheetkit/guide.py`: `guide run`, 64 games per opposing lead from index 7000 with per-turn logs on the final simulator, run on the shared box; `guide report` -> `guide.json`; the tells come from the bring matrix). Version 20 collapsed each section's notes and Version 19 moved them below the working content (the user found the page hard to scroll). Data otherwise Version 18's (the picks rerun; open item 2).
  `sheets/trick-room-six/sheet.html` (`python3 sheetkit/kit.py trick-room-six page`); `trsheet/tr-sheet.html` is a copy of it. Older
  pages: `trsheet/tr-sheet.v11.html` ... `tr-sheet.v15.html`, Version 16 in `sheetkit/fixtures/tr-v16/published.html`, and git from here on.
- Version 17 against Version 16: Torkoal back to 32 HP / 2 SpD (card and Matchups column); Incineroar's Matchups column with White Herb
  modelled (ten cells: Mega Salamence TR-up lost -> roll 55, Corviknight TR-up roll 65 -> check, Mega Gardevoir no-TR roll 15 -> check,
  Kingambit no-TR roll 40 -> 35, six detail-text changes); the whole-game % of the six tabs that bring Torkoal (Rain 58 -> 54, Snow
  85 -> 88, Rain + Sun 48 -> 50, Perish 95 -> 91, Tailwind and Trick Room unchanged after rounding); the Rain tab's turn-one lines against
  four of its six opposing leads (the 36 jobs of all six Torkoal tabs were re-run; the other five tabs' lines came out the same); the
  order of equal-share opposing leads on three tabs.
- To publish from a new conversation: Artifact `action: "read"` on that URL first, then publish `sheets/trick-room-six/sheet.html` with `url` set to it, copy it over `trsheet/tr-sheet.html`, set `published` in the folder's `sheet.json`, commit. Never touch the older sheet "Low-Variance Six" (https://claude.ai/artifact/DEF8ycjXrKGXokgH26he9A).
- The team (real sets: `sheets/trick-room-six/team.json`, same as `pssim/myteam_real.json`; SP order HP/Atk/Def/SpA/SpD/Spe):

| Pokémon | Item | Ability | Nature, SP | Moves |
|---|---|---|---|---|
| Mega Blastoise | Blastoisinite | Torrent → Mega Launcher | Quiet 32/0/0/32/2/0 | Fake Out, Water Spout, Aura Sphere, Dark Pulse |
| Torkoal | Charcoal | Drought | Quiet 32/0/0/32/2/0 (back from 12/0/0/32/22/0 on 2026-10-05, the user's decision) | Eruption, Weather Ball, Earth Power, Protect |
| Indeedee-F | Psychic Seed | Psychic Surge | Relaxed 32/0/32/0/2/0 | Follow Me, Helping Hand, Trick Room, Healing Wish |
| Farigiraf | Sitrus Berry | Armor Tail | Relaxed 30/0/21/0/15/0 | Trick Room, Protect, Psychic, Thunderbolt |
| Kingambit | Chople Berry | Defiant | Brave 32/32/0/0/2/0 | Iron Head, Kowtow Cleave, Low Kick, Sucker Punch |
| Incineroar | White Herb | Intimidate | Brave 32/32/0/0/2/0 | Fake Out, Flare Blitz, Throat Chop, Close Combat |

- Each Leads tab shows one card: the four to bring (lead + back row) that won the most whole-game sims, with its turn-one lines. Picks
  (`sheets/trick-room-six/picks.json`; old planner: champ-battle-v4 + egvalue5. The fours are from the bring matrix and confirmation,
  which ran with the 12 HP / 22 SpD Torkoal and were not re-chosen. Wins: the four tabs without Torkoal are the confirmation's 288 fresh
  games; the six with it are the 32 HP arm of the spread A/B, 384 games each. Version 16 showed the confirmation numbers for all ten):

| Tab (ladder share) | Lead / back | Wins |
|---|---|---|
| Tailwind (26.2) | Incineroar + Farigiraf / Torkoal, Kingambit | 92% |
| Sun (12.0) | Kingambit + Blastoise / Farigiraf, Incineroar | 52% |
| Indeedee TR (11.9) | Farigiraf + Kingambit / Blastoise, Incineroar | 68% |
| Rain (10.5) | Incineroar + Torkoal / Blastoise, Farigiraf | 54% |
| Balance (9.3) | Farigiraf + Blastoise / Kingambit, Incineroar | 80% |
| Sand (9.0) | Incineroar + Farigiraf / Blastoise, Kingambit | 83% |
| Snow (7.8) | Farigiraf + Blastoise / Torkoal, Incineroar | 88% |
| Trick Room (6.7) | Incineroar + Farigiraf / Blastoise, Torkoal | 73% |
| Rain + Sun (3.3) | Incineroar + Blastoise / Torkoal, Farigiraf | 50% |
| Perish (3.3) | Kingambit + Blastoise / Torkoal, Farigiraf | 91% |

  Ladder-weighted 75.5% (Version 16: 75.6%).

## Sheet kit (2026-10-05): how a sheet is built from now on

The user asked for sheet threads to be generic: one thread per team on a shared kit. The kit is `sheetkit/` (read `sheetkit/README.md`
first: steps, rules for every sheet thread, a new team's checklist, what the simulators leave out); each team has `sheets/<team>/`. This
thread maintains the kit and owns `sheets/trick-room-six/`.

- One command per step: `python3 sheetkit/kit.py <team> init | status | grid | smoke | matrix jobs|run|report | confirm jobs|run|decide |
  t1 jobs|run|solve | page`. Sim setups are named in `sheetkit/sim.json`; `current` is `v4-eg5` (what Version 16 used) until Battle sim
  says the new planner setup is final.
- `python3 sheetkit/selftest_tr.py` rebuilds the Version 16 sheet (inputs frozen in `sheetkit/fixtures/tr-v16/`) from the raw results in `pssim/results/` and checks every step
  against the old pipeline's files (matrix jobs, confirmation jobs, picks, turn-one jobs, Speeds, all 60 solved plans, the page). All
  pass. The one intended difference: opposing leads with exactly equal share are listed in the opponent model's order, which swaps two
  rows on three tabs (Balance, Snow, Trick Room). Run it after every kit change.
- `sheets/trick-room-six/`: `team.json` (= `pssim/myteam_real.json`), `sheet.json`, `text.json`, `cards.json`, `notes.json`, `charts.json`
  and `speed.json` (imported from the Version 16 page), `picks.json` (= `bringcf_picks.json`), `t1.json` (the 60 plans of the picks),
  `sheet.html` (the kit's build). `work/` links to the old result folders (`selftest_tr.py --link`).
- Every version from 17 on is built with `kit.py trick-room-six page`. The section below ("How the current page was built") describes
  the old hand-run route that built Versions 12-16, kept for history; the scripts it names still work.
- The kit's `grid` step (Team search's generic one-on-one code, read-only) matches the hand-built `mxtr_t22/` grid in 456 of 460
  cells; the four that differ are Incineroar cells where the generic code models White Herb, and it adds cells for Indeedee-F. The
  Trick Room Six still points at `mxtr_t22/` (`grid_dir` in its `sheet.json`). Agreed with Battle sim (2026-10-05): the rerun on the
  new planner (open item 2) uses the generic grid, already built at `sheets/trick-room-six/work/grid/` with the current sets (Torkoal
  12 HP / 22 SpD); Battle sim fits the final value file on self-play games that read it. To switch: delete `grid_dir` from `sheet.json`.
  If the Torkoal spread changes (open item 1): edit `team.json`, rerun `grid`, and tell Battle sim at once, since its refit must use
  the same sets. Version 16's own numbers were run with `GRID_DIR=../mxtr` (old Torkoal cells; `mxtr_t22` did not exist yet).
- A second team was dry-run in a scratch folder (the user's Rillaboom / Incineroar / Sneasler / Gholdengo / Kingambit / Mega Salamence
  six, sets from `teamsearch/teams/low_variance_six.json`): `init`, `grid`, `smoke` and a page all work with nothing Trick Room-specific.
  No folder was created under `sheets/` for it: that team's thread does `init` itself.
- Coverage, Matchups and Speed are generated (`charts`, `speed`). This sheet's `charts.json` comes from `charts` since Version 17 (the
  user chose to have White Herb modelled): Coverage is identical to the hand-built table and Matchups differ only in Incineroar's ten
  cells. `speed.json` is still hand-written (`"hand": true`).
- Not in the kit yet: effective-Speed rows (Tailwind, Scarf, Unburden, weather), cloud runs through the kit
  (same commands on the box, untested), species tells on the page.
- One progress page for all threads since 2026-10-05 (the user asked): `status_server.py`, `sim-progress` in `.claude/launch.json`,
  port 8766, with sections Sheets (kit runs, also ones pulled from a cloud box), Battle sim and Team search (that thread's own cards).
  The same server shows built sheets at `/sheets/<team>/work/preview.html`; the separate `sheets-preview` entry is gone.

## How the current page was built

1. Picks: bring matrix (all 90 fours x 6 opposing leads x 16 games per archetype, `pssim/bringmx_report.py`) and a fresh-game
   confirmation (`pssim/bringmx_confirm.py jobs|decide` -> `bringcf_picks.json`; a pick changes only if the fresh leader beats it by >= 1.5
   paired standard errors).
2. Turn-one lines: `pssim/v15_run.sh` (every tab's lead with the real sets and its planned back row; `run_jobs.sh` with 12 samples, then
   Indeedee-F item variants, `v15_merge.py`, `tr_final.py` -> `pssim/tr_final_v15plus.json`).
3. Page: `python3 pssim/build_sheet_v15.py <scratch dir>` from the repo root (runs `tr_leads.py` with `LEAD_OVERRIDE=pssim/lead_override_v14.json`
   and splices only the page's `const L=[...]`; also the Torkoal card), then `cd trsheet && python3 patch_v16_tork.py` (Matchups grid, Torkoal
   column, from `mxtr/gx_cells_{tr,notr}_inc_t22.json`).
   `tr_leads.py` still carries unpublished "Other" tab code from a v12 draft, so never write its output straight onto the page: splice `L`.
4. Check the page in the browser (Leads tabs, team card, Matchups rows) before publishing. Every turn-one switch must go to a Pokémon in
   that card's back row (v14 had switches to Pokémon outside the four; v15 fixed it by simulating with the real back rows).

## Open items (the user decides)

1. **Torkoal spread: decided 2026-10-05, back to 32 HP / 2 SpD.** The full-battle A/B (`pssim/tork_ab_run.sh`, `tork_ab_report.py`,
   `results/tork_ab_report.txt`) had the 12 HP / 22 SpD spread about 1 point worse on the tabs that bring Torkoal (Snow -5.4 +- 2.2,
   Trick Room -5.9 +- 2.5, from physical leads). Done: `team.json`, `pssim/myteam_real.json`, the card, the Matchups column (the
   Version 15 page's), the six tabs' whole-game % and turn-one lines (36 jobs re-run through the kit), the generic grid's Torkoal cells;
   Battle sim and Team search use the same sets. Published in Version 17.
2. **Picks rerun on the final simulator: DONE 2026-10-05 (8:12 pm); published as Version 18 the same evening.**
   Setup v13-v16 (all the same games: champ-battle with `DP2=1 RACE=1 RACE_TIES=avg`, `egvalue9.json`, the team's generic grid,
   32 HP Torkoal). Bring matrix 86,400 games (index 600-615) on a shared cloud box, confirmation 312 jobs x 48 fresh games (index
   1000-1047). Report `sheets/trick-room-six/work/matrix/report.txt` and `work/confirm/report.txt` (ignored by git; rerun `matrix
   report` / `confirm decide` to see them). Three picks change: Rain Blastoise + Farigiraf / Torkoal, Incineroar (61.7 vs the old pick's
   50.6, +11.0 +- 5.1; this was item 3's near miss), Balance Farigiraf + Incineroar / Blastoise, Torkoal (86.1 vs 72.9), Sand
   Blastoise + Farigiraf / Kingambit, Incineroar (73.6 vs 66.1). Ladder-weighted 75.9% (the old picks on the same fresh games 72.8%;
   not comparable with Version 17's 75.5%, another simulator). Turn-one lines re-run only for those three tabs (18 jobs); notes for
   the three new leads rewritten; two stale sentences dropped from the method note (Adamant Kingambit, default back row). Version 18
   is `sheets/trick-room-six/sheet.html`; publish it as described under "The sheet now". The sim's matchup error against real
   regional results is about 6 win-rate points per archetype, so whole-game % ranks fours within a tab better than it predicts real
   win rates. **Perish:** the tab shows the sim's 92% although the sim cannot play Perish trap properly (Team search uses a real-data
   rate, 45-53% by archetype); the user chose on 2026-10-05 to keep the sim's number on the sheet. Shared-box lessons are in `sheetkit/README.md`.
3. **Rain near miss:** resolved by the rerun (see item 2).
4. **Species tells and per-archetype strategy guides:** on the sheet since Version 21 (game plan per lead card; "Adjust the four at team preview"). The tells are small (about 4-9 points); the user's own reads (e.g. double switches against rain) are not what the planner does, so the plans describe the sim's usual game.
5. **Recordings.** The user sends ladder recordings; `recordings/process.sh <mov> <batch>` compresses, extracts frames, OCRs and parses a
   timeline; decision points go through `native/spot_starts.js` + `champ spot` (HANDOFF.md "Spread study, game reviews"). Two batches
   reviewed so far (`recordings/batch1`, `batch2`, `spots.json`).
   Never write an opponent's ladder name into `recordings/spots.json`, a review file or anything else tracked (Battle sim removed
   three on 2026-10-05); say "the opponent". The OCR timelines under `recordings/batch*/` stay git-ignored. A fourth
   thread, "Eval bar" (`evalbar/`, see `evalbar/HANDOFF.md`), will later build on this pipeline for the user's recorded games and
   will coordinate first; it may also want a card on the shared progress page (`status_server.py`).

## Running full battles (the sheet thread's main tool)

From `pssim/`:
```bash
MYTEAM=myteam_real.json node ../native/battle_starts.js <jobs.json> <starts.jsonl> <games> [first game index]
BATTLE_ANTICIPATE=1 EG_VALUE=<value.json> GRID_DIR=<grid dir> ../native/champ/bin/champ-battle-vN battle ../native/engine_data_spot.json <starts.jsonl> <outdir> <threads>
```
Jobs are `{arch, k, lead: [a, b], back: [c, d]}` (k = the archetype's opposing lead 0-5). Seeds depend on the opponent and the game index
only, so two runs with the same game indices are paired game by game: always compare on the same games and report paired differences with
standard errors. Use fresh game indices for confirmation (used so far: 0-23, 200-263, 400-431, 600-615, 1000-1047, 2000-2063, 3000-3003,
4000-4015, 5000-5003, 6000-6002). Ask **Battle sim** for the current binary, value file and flags.

Progress page: `status_server.py` on port 8766 (`sim-progress` in `.claude/launch.json`). A run shows up only if its log in `pssim/` starts
with `HH:MM:SS <jobs.json> -> <outdir>, <games> games, <threads> threads (...)`.

## Rules that apply (also in memory)

- No miss-able moves on the team (95% counts as miss-able). Keep it a distinct Trick Room team; do not drift toward the user's other team.
- Sims assume competent opponents; do not tune around ladder misplays.
- Keep the sheet lean; add sections only when asked. Times in 12-hour am/pm.
- CPU: never more than 10 busy cores on the Mac across all threads; at most 3 workers while the user may be playing (ask first); when
  several threads need cores, split evenly and coordinate by message. Never delete the user's files unless asked.
