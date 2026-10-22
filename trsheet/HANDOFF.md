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

- Published: https://claude.ai/artifact/Qufendyuq8b42JmB56XSc6, **Version 27** (2026-10-22, the user's go-ahead): the Perish fix the user chose (2026-10-17) over moving the sheet to the bot's net setup. The sheet now plays on `v23p2-dp2-race-eg9-full` (v23 + PERISH2=1, pinned in sheet.json 'setup'; Battle sim's check on 244 real Perish pairings: v23 overrates the side facing Perish by ~8 points, PERISH2 halves it and gets the singing rate right). The 3,696 results with Perish Song in a four (stale copies included) were replayed (`flagged --write --moves perishsong --moves-only --tag perish`, chain `work/perish_replay.sh`), then both-sides-pick rounds, the mix check (258 new cells), turn one and game plans. Also fixed on the way: picks.load read set-aside folders through 'res*' (an archived result won over the live one: 1,051 of 6,825 matrix results), which fed the tells and the both-sides-pick candidates. Result: 12 of 32 picks changed, ladder-weighted 44.7% single pick / 46.8% mixed (V26 45.3 / 47.8). The Perish cards barely moved (+4.5, +1.5, 0, within noise; real ladder record vs Gengar teams 52%); Indeedee TR Metagross + Milotic + Sneasler 13% -> 58% with Farigiraf + Kingambit / Blastoise + Torkoal, a four the old candidate list never tried (56-94% against all 12 answer fours at 32 games). V26 outputs are in `work/v26_snapshot/`. Version 26 (2026-10-11): the Mac's pssim/node_modules had lost the Champions data patch (pssim/engine_patch; a `node build` at 11:24 pm on Oct 10 recompiled dist/), re-applied; the 59 turn-one results made on the Mac that day were rerun (4 plans moved by about a point). Full battles were unaffected (starts take only stats, ids and PP from Showdown). If node_modules is ever rebuilt, re-run setup.sh's copy step. Version 25 (2026-10-11): Version 24 with the turn-one lines facing Mega Garchomp Z / Mega Golisopod redone after the Mega-ability fix in t1sim.js (pssim's Showdown had outdated abilities for three Megas; `t1 redo`); 6 of 23 plans changed. Version 24 (2026-10-11, the user's go-ahead): after the mix check found stronger opposing answers (the top-2-of-a-4-game-screen answer search misses some), two more both-sides-pick rounds and adoption: 7 fours changed since Version 23, ladder-weighted 45.3% single pick / 47.8% mixed (Version 23 read 48.1%); the Archaludon + Pelipper Rain card fell from 46% to 14%. Version 23 (v23 replay) and Version 22 (cards) before it; Version 21 (archetype tabs) is in `archive_v21/`.
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

## Cards: opponents by core group (started 2026-10-06; the user's choice)

The user asked to move the sheet onto Battle sim's real-team classification and chose the layout: the ten archetype tabs stay, each
holding one card per core group (in order of how common) plus an "other" card, and the "Which tab" guide becomes the ordered rule list,
each rule jumping to its card. 32 cards (25 rules, two too thin for a card of their own; 8 "other" cards), built by
`sheetkit/opponents.py`. `sheets/trick-room-six/sheet.json` has `"opponents": "cards"`; the archetype-era results are in
`work/archetypes/` and `archive_v21/` (picks, turn-one plans, guide, notes of Versions 18-21; Version 21 was still
archetype-based). The new matrix jobs (15,750) and each card's real sixes are written. The whole rerun is about 550,000 battles
(`sheetkit/cloud/all.sh`), so it waited for a cloud box. None could be had on 2026-10-06, so the run was trimmed to about 167,000
battles (sheet.json `matrix_fours`, `games`, `optimal`; see `trim_note`). Team search freed its Spain box (c7a.24xlarge, 96 threads)
that evening, so the Mac run at 3:30 am was cancelled and `all.sh` ran there from 9:40 to 11:39 pm (log `work/all.log`). The first
both-sides-pick round changed 27 of 32 picks, but each opposing six's strongest answers had only been searched against the old pick, so
the new picks' numbers were flattering (Sand read 72%). Two more rounds (`optimal run --only more`, `sheetkit/cloud/more.sh`; logs
`work/more_r1.log`, `more_r2.log`, `more.log`) searched the answers to each card's best four; only a searched four can be the pick now.
Round two kept 22 of the 27 changes and sent 5 back; round three (7 cards) changed 3 more. One card's untested best four is still 0.7
points ahead of its pick, which is noise, so the rounds stopped there (box done 12:54 am on 2026-10-07). Ladder-weighted: 49% when both
sides pick their four, 71% against the usual fours (real ladder Trick Room teams win about 54%). Round two also found that a re-run
reused results by job number even when the job had changed (the game plans of the 5 changed cards were for their old fours);
`battle_run` now moves such results to `<folder>.stale/`, and `pull.sh` no longer copies the box's text.json and notes.json over the
Mac's. Notes per card come from `card_notes.py` (Armor Tail and Psychic Terrain against Fake Out and Sucker Punch); `text.json` now
describes the cards. Published as Version 22 on 2026-10-07 after the user saw the draft.

## Both sides pick their four (started 2026-10-06)

The user asked that the sheet's whole-game percentages assume both players pick their four optimally (the sim's opponents always bring
the replay-average four, which is a large part of why Snow and Tailwind read 93-96%). A first test (`work/oppbr*.py`, Snow and Tailwind):
with the opponent bringing its best four against our pick, Snow drops to 75% +- 6 and Tailwind to 77% +- 6 (their best answers lead
Kingambit + Raichu or Froslass + Sneasler vs Snow, Salamence first vs Tailwind). The kit's `optimal` step does it for every tab
(`sheetkit/optimal.py`, sixes from `sheetkit/opp_sixes.js`): screen the pick against every four each opposing six allows, then our
candidate fours against each six's three strongest answers. First full run scheduled by `work/optimal_at_3am.sh` (10 Mac threads from
3 am, the user's request; log `work/optimal_at_3am.log`, result `optimal.json`). Not on the sheet yet: go through the result with the
user first (picks may change, which means new turn-one lines and game plans for those tabs). Battle sim is reworking the opponent model
into a pool of real Bo3 sides grouped by core rules; if that lands, real sixes would replace the reconstructed ones and the tabs may be
re-keyed (Battle sim will say first).
**Standing instruction from the user (2026-10-06, about 2 am): if the pool passes Team search's validation, do not ask: run the optimal
step on real sixes** (`OPTIMAL_SIXES=pool python3 sheetkit/kit.py trick-room-six optimal run --threads N`, then `report`; battles in
`work/optimal_pool`, result `optimal_pool.json`; the most common six real sixes per tab from `pssim/opp_pool.py`, about 72,000 games;
cores coordinated with the other threads as usual). Going over the result with the user before the sheet changes still applies.
**Done so far:** the pool passed (Team search, 4:10 am, 2026-10-06: RMS sim-vs-real 0.29 -> 0.18 by archetype). The model-sixes run was
stopped at 4:05 am (a quarter done; superseded) and the real-sixes run started at 4:06 am on 10 Mac threads on v19 + engine_data_full
(`work/optimal_pool.sh`: drops to 3 threads if someone uses the Mac after 7 am; log `work/optimal_pool.log`; about 72,000 games, done
around 7-8 am). About 6% of real-team games ended early with a fractional score: the recharge turn after Hyper Beam left a side
with no legal action. Battle sim fixed it in champ-battle-v20 (same games otherwise); the run restarted on v20 at 4:19 am, with the 53
finished jobs that had such a game set aside in `work/optimal_pool/screen_8_v19_early/` and replayed. The earlier sheet runs (picks
rerun, guide; v13-v16 with archetype models) had about 1.5% such games; worth replaying those jobs at the next rerun. Battle sim also decided the sheets key
their tabs by core group with the archetype name kept (root HANDOFF); not started, waits for the user.

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
6. **Replay on v23: done 2026-10-09 (5:26-8:07 am, Spain box after the Frankfurt sheets), not yet published.** `cloud/replay.sh` on
   v23 with `--moves healingwish,memento` (5,784 result files), then both-sides-pick rounds. Two kit bugs found on the way and fixed:
   tied fours sorted in a hash order (reordered job lists threw results away), and set-aside matrix cells were not counted (a pick lost
   its strongest answer: one card read 43% instead of 8%). Result: ladder-weighted 48.1% when both sides pick (Version 22: 49.4%),
   70.4% against the usual fours; only Other Sun changes its four (back Torkoal + Kingambit); Indeedee is still never brought, Healing
   Wish or not. Published as Version 23 on 2026-10-09 (the user's go-ahead); sim.json `current` is now v23.
7. **Optional Mega Evolution (asked of Battle sim, 2026-10-09).** The full-battle planner (plan.rs) and the turn-one step (t1sim.js)
   always Mega Evolve a stone holder the first time it moves. The user finds that wrong: base Raichu (Lightning Rod, Fake Out) and base
   Staraptor (cycling Intimidate) are real ladder lines, and with two stones the lead's Mega locks the other out. Waiting on Battle sim
   for no-Mega options and a value feature for an unused Mega; then add the same to t1sim (its scorer folds Megas into the base species).
   No Trick Room Six rerun for it (the user, 2026-10-09: Blastoise's base ability does little and nothing else holds a stone; cycling
   Intimidate is bad against this team, so the opponents' Salamence / Staraptor would not stay base). It matters for the two-stone
   Frankfurt sheets and teams like them.
8. **Mixed brings for the ladder bot (2026-10-11, the user's go-ahead).** `kit.py trick-room-six mix write` put a per-card mix into
   picks.json (`mix`: [{lead, back, p}], sampled per game by Battle sim's bot so Bo3 game 1 reveals nothing): 20 of 32 cards mix,
   48.5% -> 50.2% on the answers every component met (provisional). `mix check` (fill missing cells, play each six's strongest fours
   against the mix, re-solve) is scheduled by `work/mix_at_4am.sh` for 4:00 am on the Mac, 8 threads or fewer (log `work/mix_check.log`);
   after it, commit picks.json and tell Battle sim. The page stays one pick per card.
   Done 4:32 am: 19-20 cards mix, 47.8% mixed. Caveat for every both-sides-pick number: answers are each six's top two fours by a
   4-game screen, so strong answers can be missed and the numbers are a ceiling; a deeper answer search (top 4, or more screen games)
   would lower them further (the mix check alone took the sheet from 48.1% to 45.3%).

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
